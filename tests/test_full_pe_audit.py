import copy
import unittest
from decimal import Decimal, ROUND_HALF_UP
from unittest.mock import patch

from budget_2027_snapshot import allocate_by_capacity
from financial_integration import cents
from pe_full_audit import full_cost_audit, project_real_discounts, validate_full_audit
from scripts.audit_full_pe_2027 import budget_accounts
from scripts.generate_approved_pe_2027_preview import build_preview
from server import blank
from teaching_cost import load_documentary_costs


class FullPEAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preview = build_preview()
        cls.data = full_cost_audit(cls.preview)
        cls.rows = {r['class']: r for r in cls.data['classes']}

    def test_previous_approved_values_and_inputs_are_preserved(self):
        before = copy.deepcopy(self.preview)
        full_cost_audit(self.preview)
        self.assertEqual(before, self.preview)
        self.assertEqual(self.preview['summary']['classAttributedMonthly'], 597073.12)
        self.assertEqual(sum(r['breakEvenStudents'] for r in self.preview['classes']), 626)
        for row in self.data['classes']:
            self.assertEqual(round((row['totalCostMonthly']-row['previousTotalCostMonthly'])*100),
                             cents(row['institutionalAllocationMonthly']))

    def test_exact_class_capacity_manifest(self):
        source = blank()['classes']
        actual = {r['classId']:(r['class'],r['capacity']) for r in self.data['classes']}
        self.assertEqual(actual, {r['id']:(r['name'],r['capacity']) for r in source})
        self.assertEqual(len(actual),41)
        self.assertEqual(sum(c for _,c in actual.values()),1103)

    def test_duplicate_classes_and_changed_capacity_fail(self):
        for change in ('duplicate','capacity'):
            data=copy.deepcopy(self.preview)
            if change=='duplicate':data['classes'][-1]=copy.deepcopy(data['classes'][0])
            else:data['classes'][0]['capacity']+=1
            with self.assertRaises(ValueError):full_cost_audit(data)

    def test_every_cent_of_institutional_balance_is_distributed(self):
        rows=self.data['classes']
        self.assertEqual(sum(cents(r['institutionalAllocationMonthly']) for r in rows),20229604)
        for r in rows:
            exact=Decimal(20229604)*r['capacity']/1103
            self.assertLess(abs(cents(r['institutionalAllocationMonthly'])-exact),1)

    def test_each_shared_block_closes_once(self):
        expected={'docentes':12267300,'estagiarias':1489591,'auxiliar-direta':263843,
                  'residual-g2':777179,'apoio-direto-g2':136330,'auxiliares-segmento':1851700,
                  'coordenacao-segmento':1743646,'gerais-liquidos-pcld':41177723,
                  'pessoal-institucional':20229604}
        for component, total in expected.items():
            self.assertEqual(sum(a['monthlyCents'] for a in self.data['expenseLedger']
                                 if a['component']==component),total)
        self.assertEqual(sum(expected.values()),79936916)

    def test_cent_remainder_is_not_lost(self):
        self.assertEqual(allocate_by_capacity(2,[{'id':'a','capacity':1},{'id':'b','capacity':1},{'id':'c','capacity':1}]),
                         {'a':1,'b':1,'c':0})

    def test_no_disappearing_or_duplicated_expense(self):
        for change in ('delete','duplicate','unlink'):
            d=copy.deepcopy(self.data)
            if change=='delete':d['expenseLedger'].pop(0)
            elif change=='duplicate':d['expenseLedger'].append(copy.deepcopy(d['expenseLedger'][0]))
            else:d['expenseLedger'][0]['classId']='unknown'
            with self.assertRaises(ValueError):validate_full_audit(d)

    def test_pcld_budget_and_personnel_envelope(self):
        s=self.data['summary']
        self.assertEqual(cents(s['classAttributedMonthly'])+4211780,84148696)
        self.assertEqual(s['unallocatedMonthly'],0)
        self.assertEqual(s['doubleCountProtection']['additionalPersonnelAdded'],0)
        self.assertEqual(sum(cents(r['pcldNeutralizedMonthly']) for r in self.data['classes']),4211780)

    def test_tuition_ticket_and_single_delinquency(self):
        expected={'G2 A':(93069,86214),'1º A':(96467,89362),'6º A':(123981,114850),
                  '1º EM':(142559,132060),'2º EM':(142559,132060),'3º EM':(146105,135344)}
        for name,(tuition,ticket) in expected.items():
            self.assertEqual(cents(self.rows[name]['grossTuition']),tuition)
            self.assertEqual(cents(self.rows[name]['netTicket']),ticket)

    def test_teaching_base_matches_validated_source_and_factor(self):
        ledger=load_documentary_costs(blank()['classes'])
        self.assertEqual(ledger['validated_cost_cents'],2726065)
        self.assertEqual(ledger['conflicted_cost_cents']+ledger['unassigned_cost_cents'],0)
        by_id={r['classId']:r for r in self.data['classes']}
        for r in ledger['classes']:
            monthly=int((Decimal(cents(r['weekly_cost']))*Decimal('4.5')).quantize(Decimal(1),rounding=ROUND_HALF_UP))
            self.assertEqual(cents(by_id[r['class_id']]['teachingCostMonthly']),monthly)
        self.assertEqual(sum(cents(r['teachingCostMonthly']) for r in by_id.values()),12267300)
        self.assertEqual({p['hour_aula_rate_2027'] for p in ledger['operational_allocations']},{16.2,26.11,38.5})

    def test_fifty_unique_teachers_and_approved_personnel(self):
        teachers=self.data['teacherProjection2027']
        self.assertEqual(len({t['name'] for t in teachers}),50)
        self.assertTrue(any(t['name'].startswith('Telma') for t in teachers))
        self.assertTrue(any(t['name'].startswith('Julianne') for t in teachers))
        self.assertFalse(any(t['name'].startswith(('Marcelo','Lohana')) for t in teachers))
        self.assertEqual(self.rows['G2 A']['internDetails'][0]['person'],'Joyce dos Santos Pereira')
        self.assertEqual(self.rows['G2 B']['internDetails'][0]['person'],'Larissa Lorrana Miranda de Jesus')
        self.assertEqual(self.rows['G4 B']['otherDirectCostsMonthly'],2638.43)
        self.assertEqual(self.data['personnelDecisions'][0]['decision'],'SUBSTITUI_ROMILTON_MESMO_POSTO')
        self.assertEqual(self.data['personnelDecisions'][1]['decision'],'VAGA_NOVA')

    def test_pe_is_minimum_integer_and_capacity_formulas(self):
        for r in self.data['classes']:
            cost,ticket,pe=cents(r['totalCostMonthly']),cents(r['netTicket']),r['breakEvenStudents']
            self.assertGreaterEqual(pe*ticket,cost)
            self.assertLess((pe-1)*ticket,cost)
            self.assertEqual(r['physicalMarginStudents'],r['capacity']-pe)
            self.assertAlmostEqual(r['breakEvenPercentCapacity'],100*pe/r['capacity'],places=10)
            self.assertEqual(cents(r['capacityRevenueMonthly']),r['capacity']*ticket)
            self.assertEqual(round(r['capacityResultMonthly']*100),r['capacity']*ticket-cost)

    def test_zero_and_large_enrollments_do_not_change_structural_pe(self):
        for count in (0,999):
            s=blank()
            for room in s['classes']:
                room['opening']={'new':count,'re':0};room['students']=count;room['unclassified']=0
            with patch('scripts.generate_approved_pe_2027_preview.blank',return_value=s):
                result=full_cost_audit()
            self.assertEqual(result['classes'],self.data['classes'])

    def test_annual_cost_is_twelve_months_tuition_is_eleven(self):
        self.assertEqual(self.data['summary']['managerialAnnual'],9592429.92)
        self.assertEqual(self.data['summary']['annualRoundingDifferenceCents'],5)
        self.assertEqual(self.data['revenueCalendar']['tuitionMonths'],list(range(2,13)))
        self.assertEqual(self.data['revenueCalendar']['enrollmentTreatment'],'SEPARATE_NOT_AMORTIZED')
        for r in self.data['classes']:
            self.assertEqual(cents(r['tuitionRevenue11MonthsCapacity']),cents(r['capacityRevenueMonthly'])*11)
            self.assertEqual(cents(r['costAnnual']),cents(r['totalCostMonthly'])*12)

    def test_documentary_accounts_all_preserved_without_parent_duplication(self):
        accounts=budget_accounts()
        self.assertEqual(len(accounts),112)
        self.assertEqual(len({a['id'] for a in accounts}),112)
        leaf=[a for a in accounts if not a['isParent'] and a['code'].startswith('4')]
        self.assertEqual(sum(a['monthlyCents'] for a in leaf if a['code'].startswith('411')),38759193)
        self.assertEqual(sum(a['monthlyCents'] for a in leaf if not a['code'].startswith('411')),45389507)
        self.assertEqual(sum(a['monthlyCents'] for a in leaf if a['category']=='F'),17790108)
        self.assertEqual(sum(a['monthlyCents'] for a in accounts if a['code'].startswith('3')),90515216)
        self.assertEqual(sum(a['annualCents'] or 0 for a in leaf),1009784357)
        self.assertEqual(sum(a['code']=='3195130' for a in accounts),2)
        self.assertTrue(all(a['category']=='E' for a in accounts if a['code'].startswith('3')))

    def test_pending_documents_prevent_false_closure(self):
        self.assertFalse(self.data['readyForOfficialDiscountImport'])
        self.assertTrue(all(r['auditStatus'].startswith('PROVISORIO') for r in self.data['classes']))
        paula=[r for r in self.rows['G3 B']['internDetails'] if r['person'].startswith('Paula')]
        self.assertIsNone(paula[0]['amount'])
        self.assertEqual(self.data['financialAccountReview']['classification'],'F')

    def test_excluded_historical_people_are_not_projected_as_teachers(self):
        review=self.data['teachingIdentityReview']
        self.assertEqual(len(review),15)
        self.assertTrue(all(r['projectedTeacher'] is None for r in review))
        self.assertEqual(sum(cents(r['preservedWeeklyCost']) for r in review
                                 if r['historicalPerson'].startswith('Lohana')),36554)
        self.assertEqual(sum(cents(r['preservedWeeklyCost']) for r in review
                                 if r['historicalPerson'].startswith('Marcelo')),7833)

    def test_future_real_discounts_replace_structural_discount_without_changing_pe(self):
        before=copy.deepcopy(self.data);cid=self.rows['G2 A']['classId']
        students=[dict(studentId='a',classId=cid,discountPercent=10)]
        result=next(r for r in project_real_discounts(self.data,students,complete=True) if r['classId']==cid)
        self.assertEqual(result['projectedRevenueMonthly'],799.93)
        self.assertEqual(result['realDiscountImpactMonthly'],93.07)
        self.assertEqual(result['enrollmentCount'],1)
        self.assertEqual(result['structuralBreakEvenStudents'],self.rows['G2 A']['breakEvenStudents'])
        self.assertEqual(before,self.data)

    def test_no_import_means_unknown_not_zero_revenue(self):
        self.assertTrue(all(r['projectedRevenueMonthly'] is None for r in project_real_discounts(self.data)))
        with self.assertRaises(ValueError):project_real_discounts(self.data,complete=True)

    def test_empty_complete_import_and_total_discount(self):
        self.assertTrue(all(r['projectedRevenueMonthly']==0 and r['projectedTicket'] is None
                            for r in project_real_discounts(self.data,[],complete=True)))
        cid=self.rows['G2 A']['classId']
        result=project_real_discounts(self.data,[dict(studentId='a',classId=cid,discountPercent=100)],complete=True)
        self.assertEqual(next(r for r in result if r['classId']==cid)['projectedRevenueMonthly'],0)

    def test_import_rejects_duplicates_unknown_classes_and_bad_discounts(self):
        item=dict(studentId='a',classId=self.rows['G2 A']['classId'],discountPercent=10)
        cases=[[item,item],[dict(item,classId='unknown')]]
        cases += [[dict(item,discountPercent=v)] for v in (-1,101,'NaN','Infinity')]
        for records in cases:
            with self.assertRaises(ValueError):project_real_discounts(self.data,records,complete=True)


if __name__=='__main__':
    unittest.main()
