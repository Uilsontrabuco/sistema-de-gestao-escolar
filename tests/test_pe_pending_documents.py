import copy
import json
import unittest
from pathlib import Path
from scripts.reconcile_pe_pending import reconcile, payroll_records, SOURCES, report
from scripts.generate_approved_pe_2027_preview import build_preview
from pe_full_audit import full_cost_audit


class PendingDocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=reconcile()

    def test_all_payroll_people_events_and_printed_totals_reconcile(self):
        self.assertEqual(self.result['payrollTotals'],dict(people=125,events=2131,printedTotalCents=35944898))
        for person in self.result['payroll']:
            self.assertEqual(sum(e['valueCents'] for e in person['events']),person['printedTotalCents'])
            self.assertEqual(len(person['events']),person['printedEventCount'])

    def test_no_total_or_salary_base_is_misread_as_employee_cost(self):
        lohana=next(p for p in self.result['payroll'] if p['code']=='516')
        self.assertEqual(lohana['printedTotalCents'],247644)
        self.assertEqual(lohana['priorEconomicCostCents'],274613)
        base=next(e for e in lohana['events'] if e['code']=='94700')
        self.assertEqual(base['valueCents'],0)
        self.assertFalse(base['includedInPriorEconomicBasis'])

    def test_no_personal_deductions_or_duplicate_vacation_provision_in_cost(self):
        for person in self.result['payroll']:
            for event in person['events']:
                if event['valueCents']<=0 or event['code'] in ('92200','15000','15500','16300','94700'):
                    self.assertFalse(event['includedInPriorEconomicBasis'])

    def test_paula_position_known_but_cost_and_budget_coverage_unknown(self):
        p=self.result['paula']
        self.assertEqual((p['code'],p['confirmedClass'],p['role']),('955','G3 B','Estagiário(a)'))
        self.assertTrue(p['additionalPosition'])
        self.assertIsNone(p['monthlyCostCents'])
        self.assertIsNone(p['historicalCostCents'])
        self.assertEqual(p['budgetInclusion'],'NAO_COMPROVADA')
        self.assertEqual(p['addedExpenseCents'],0)
        self.assertNotIn('955',{p['code'] for p in self.result['payroll']})

    def test_substitution_does_not_copy_romilton_salary_to_jailane(self):
        people={p['code']:p for p in self.result['people']}
        self.assertIsNone(people['952']['historicalCostCents'])
        self.assertIsNone(people['953']['historicalCostCents'])
        self.assertNotIn('679',people)
        old=next(p for p in self.result['payroll'] if p['code']=='679')
        self.assertEqual(old['priorEconomicCostCents'],253077)

    def test_institutional_historical_controls_match_prior_approved_totals(self):
        expected={'C27':6843320,'C28':3927917,'C29':2115543,'C30':2527588,'C02':1489591}
        self.assertEqual({k:g['totalCents'] for k,g in self.result['groups'].items()},expected)
        b=self.result['institutionalBridge']
        self.assertEqual(b['historicalAdministrativeControlsCents'],11555179)
        self.assertEqual(b['unbridgedDifferenceCents'],8674425)
        self.assertEqual(b['historicalAdministrativeControlsCents']+b['unbridgedDifferenceCents'],20229604)
        self.assertIsNone(b['nominalBudget2027ReconciledCents'])

    def test_lohana_only_coordination_and_marcelo_not_in_payroll_roster(self):
        p=next(p for p in self.result['people'] if p['code']=='516')
        self.assertEqual((p['role'],p['department'],p['classGroup']),
                         ('Auxiliar de Coordenação','CAJ - Coordenação Pedagógica','C28'))
        self.assertFalse(any('Marcelo Rodrigues'==p['person'] for p in self.result['people']))
        self.assertFalse(any('Marcelo Rodrigues'==p['person'] for p in self.result['payroll']))

    def test_g2_both_residuals_are_traced_without_nominal_invention(self):
        for g,amount in zip(self.result['g2'],(387433,389746)):
            self.assertEqual(g['payrollResidualCents'],amount)
            self.assertEqual(g['teacherCapturedCents']+amount,627193)
            self.assertEqual(sum(p['monthlyCents'] for p in g['capturedTeachers']),g['teacherCapturedCents'])
            self.assertEqual(g['supportResidualCents'],68165)
            self.assertEqual(g['internCapturedCents']+g['supportResidualCents'],152000)
            self.assertEqual(g['nominallyIdentifiedResidualCents'],0)
            self.assertFalse(g['directEconomicEvidence'])

    def test_discounts_are_distinct_from_commercial_revenue_deduction(self):
        entries=self.result['discounts']
        self.assertEqual({a['code']:a['monthlyCents'] for a in entries},{'4126005':4838820,'4126007':12951288})
        self.assertEqual(sum(a['monthlyCents'] for a in entries),17790108)
        self.assertEqual(sum(a['annualCents'] for a in entries),213481290)
        commercial=self.result['commercialDiscountRevenueAccount']
        self.assertEqual(commercial['code'],'3149026')
        self.assertEqual(commercial['monthlyCents'],-3464632)
        self.assertFalse(self.result['discountImportGate']['ready'])

    def test_all_five_tuitions_match_official_source(self):
        expected=[93069,96467,123981,142559,146105]
        self.assertEqual([t['tuitionCents'] for t in self.result['tuition']],expected)
        text=(SOURCES/'Orçamento COLEGIO ADVENTISTA DE JUAZEIRO 2027 (1).pdf.txt').read_text(encoding='utf-8')
        page2=text.split('PÁGINA 2\n',1)[1].split('PÁGINA 3',1)[0]
        for amount in ('930,69','964,67','1.239,81','1.425,59','1.461,05'):
            self.assertIn(amount,page2)

    def test_five_deficits_explained_by_exact_component_sum_without_forcing_capacity(self):
        expected={'G2 A':(22,320305),'G2 B':(22,320305),'G4 B':(29,192127),'G5 A':(22,56797),'G5 B':(19,37808)}
        for t in self.result['targetClasses']:
            self.assertEqual((t['pe'],t['deficitCents']),expected[t['className']])
            self.assertEqual(sum(p['monthlyCents'] for p in t['components']),t['costCents'])
            self.assertEqual(t['costCents']-t['capacityRevenueCents'],t['deficitCents'])
            self.assertGreater(t['pe'],t['capacity'])
            self.assertLessEqual(t['costCents']-t['institutionalAllocationCents'],t['capacityRevenueCents'])

    def test_previous_audit_values_and_source_roster_are_unchanged(self):
        self.assertEqual(self.result['fullAudit'],full_cost_audit())
        approved=build_preview()
        self.assertEqual(approved['summary']['classAttributedMonthly'],597073.12)
        self.assertEqual(len(self.result['people']),127)
        self.assertEqual(len({p['code'] for p in self.result['people']}),127)

    def test_report_does_not_declare_documentary_closure(self):
        text=report(self.result)
        self.assertIn('AINDA NÃO FECHADO DOCUMENTALMENTE',text)
        self.assertIn('R$ 86.744,25',text)
        self.assertIn('Lista única final',text)


if __name__=='__main__':unittest.main()
