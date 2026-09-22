import unittest,json,sqlite3
from copy import deepcopy
from pathlib import Path
from pe_real import AUDIT
from scripts.reconcile_pe_real_costs import reconcile,apply_costs
from enrollment_2027 import snapshot,project_current,apply_snapshot_to_state
from server import blank


class CostEnrollmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.costs=reconcile();cls.data=json.loads((AUDIT/'resultado.json').read_text(encoding='utf-8'));cls.enrollment=snapshot()

    def test_personnel_accounts_exact(self):
        self.assertEqual(sum(a['monthlyCents'] for a in self.costs['accounts'] if a['code'].startswith('411')),38759193)

    def test_initial_pending_is_fully_decomposed(self):
        s=self.costs['summary']
        self.assertEqual(s['personnelPendingBeforeCents']+s['generalPendingBeforeCents'],62320836)
        self.assertEqual(s['initialPendingCents']-s['newlyResolvedNetCents']-s['discountsReclassifiedCents'],1582705)

    def test_source_blocks_and_payroll_criteria(self):
        self.assertTrue(all(x['verified'] for x in self.costs['blockTests'].values()))
        self.assertTrue(all(x['verified'] for x in self.costs['payrollTests'].values()))

    def test_every_segment_allocation_closes(self):
        for a in self.costs['accounts']:
            if a['segmentAllocationCents']:
                self.assertEqual(sum(a['segmentAllocationCents'].values()),a['monthlyCents'])
                self.assertLessEqual(a['criterionTestMaximumAnnualCents']['receita_prevista'],1)

    def test_no_matching_by_amount_alone_for_cal(self):
        a=next(a for a in self.costs['accounts'] if a['code']=='4129103')
        self.assertEqual(a['criterion'],'BLOCO_GERAL_P4')

    def test_all_class_allocations_close(self):
        a=self.costs['allocations']
        self.assertEqual(sum(x['payrollCents'] for x in a),26763016)
        self.assertEqual(sum(x['supportCents'] for x in a),11996177)
        self.assertEqual(sum(x['generalCents'] for x in a),45389503)
        self.assertEqual(sum(x['costCents'] for x in a),62146808)

    def test_unknown_destination_is_not_redistributed(self):
        reserved=[r for r in self.costs['allocations'] if not r['classId']]
        self.assertEqual(len(reserved),1);self.assertEqual(reserved[0]['sourceName'],'7º Ano C')
        self.assertEqual(reserved[0]['costCents'],1582705)

    def test_discounts_and_pcld_only_once(self):
        a=self.costs['allocations']
        self.assertEqual(sum(x['pcldRemovedCents'] for x in a),4211780)
        self.assertEqual(sum(x['discountReclassifiedCents'] for x in a),17790108)
        self.assertEqual(84148696-4211780-17790108,62146808)

    def test_paula_not_zero_or_standard_salary(self):
        r=next(r for r in self.data['rows'] if r['name']=='G3 B')
        self.assertIsNone(r['pendingCostCents']);self.assertTrue(r['unknownCosts'])
        self.assertEqual(self.costs['internUnidentifiedCents'],286357)

    def test_idempotent_cost_reclassification(self):
        d=deepcopy(self.data);a=apply_costs(d,self.costs);b=apply_costs(deepcopy(a),self.costs)
        self.assertEqual(a,b)

    def test_enrollment_source_all_control_totals(self):
        self.assertEqual(len(self.enrollment['rows']),41)
        self.assertEqual(self.enrollment['totals'],dict(capacity=1103,students=775,new=37,re=738,vacancies=328))

    def test_overcapacity_negative_vacancies(self):
        r={r['name']:r for r in self.enrollment['rows']}
        self.assertEqual(r['G4 A']['vacancies'],-6);self.assertEqual(r['7º A']['vacancies'],-18)
        self.assertEqual(r['4º B']['vacancies'],-7)

    def test_enrollment_does_not_modify_cost_or_pe(self):
        a=project_current(self.data,data=self.enrollment);other=deepcopy(self.enrollment)
        for r in other['rows']:r['students']+=10;r['new']+=10
        b=project_current(self.data,data=other)
        self.assertEqual([(r['pe'],r['consideredCostCents']) for r in a['rows']],[(r['pe'],r['consideredCostCents']) for r in b['rows']])

    def test_distance_sign_and_projected_revenue(self):
        d=project_current(self.data,data=self.enrollment)
        for r in d['rows']:
            if r['pe'] is not None:self.assertEqual(r['distanceToPE'],r['enrolled']-r['pe'])
            if r['projectedResultCents'] is not None:self.assertEqual(r['projectedResultCents'],r['projectedRevenueCents']-r['consideredCostCents'])

    def test_zero_enrollment_revenue_is_zero_not_zero_ticket(self):
        r=project_current(self.data,data=self.enrollment)['rows'][1]
        self.assertEqual(r['projectedRevenueCents'],0);self.assertEqual(r['ticketCents'],78215.1876);self.assertEqual(r['pe'],14)

    def test_import_preserves_unrelated_state_and_history(self):
        state=blank();before=deepcopy(state);after=apply_snapshot_to_state(state,self.enrollment)
        self.assertEqual(state,before)
        for k in state:
            if k not in ('classes','enrollments'):self.assertEqual(state[k],after[k])
        self.assertEqual(state['enrollments']['history'],after['enrollments']['history'])
        self.assertEqual(sum(c['students'] for c in after['classes']),775)

    def test_snapshot_repeat_does_not_double_enrollment(self):
        a=apply_snapshot_to_state(blank(),self.enrollment)
        self.assertEqual(a,apply_snapshot_to_state(a,self.enrollment))

    def test_unmatched_cost_is_not_zero(self):
        r=next(r for r in self.data['rows'] if r['name']=='1º D')
        self.assertIsNone(r['consideredCostCents']);self.assertIsNone(r['pe'])
        self.assertGreater(r['previousPartialCostCents'],0)
