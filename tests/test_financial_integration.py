import copy
import unittest
from server import blank
from teaching_cost import load_documentary_costs
from financial_integration import integration_snapshot, consolidate_expenses, break_even_students, structural_ticket_cents, monthly_teaching_base_cents


class FinancialIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.ledger=load_documentary_costs(blank()['classes'])
    def test_closed_weekly_basis_41_classes_50_professors_and_official_monthly_factor(self):
        state=blank();before=copy.deepcopy(state);d=integration_snapshot(state,self.ledger,2027)
        self.assertEqual(state,before)
        self.assertEqual(d['teachingCostWeekly'],25677.35)
        self.assertEqual(sum(r['teachingCostWeeklyCents'] for r in d['classes']),2567735)
        self.assertEqual(len(d['classes']),41)
        self.assertEqual(self.ledger['summary']['reconciled_professors'],50)
        self.assertEqual(d['teachingCostMonthly'],115548.16);self.assertIsNone(d['teachingCostAnnual'])
        self.assertEqual(d['monthlyFactor'],4.5);self.assertEqual(d['monthlyMethod'],'CUSTO_SEMANAL_CONFIRMADO_X_4_5')
        self.assertIsNone(d['breakEvenStudents']);self.assertEqual(d['classBreakEvenCounts']['undetermined'],41)
    def test_tuition_discounts_scholarships_and_enrollment_separate(self):
        state=blank();room=state['classes'][0];room['opening']={'new':1,'re':2}
        state['academicYears'][0]['classifications'][room['id']]={'fixed':{'noDiscount':1,'philanthropic100':1,'philanthropic50':1}}
        row=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(row['netRevenueMonthly'],1396.04)
        self.assertEqual(row['tuitionRevenueAnnual'],15356.44)
        self.assertEqual(row['students'],3)
        self.assertEqual(row['netTicketMonthly'],1396.04/3)
        state['enrollments']['history']=[{'classId':room['id'],'type':'new','quantity':1}]
        row=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(row['students'],4);self.assertIsNone(row['netRevenueMonthly'])
    def test_capacity_and_students_recompute_weekly_metrics_without_changing_cost(self):
        state=blank();before=integration_snapshot(state,self.ledger,2027)['classes'][0]
        state['classes'][0]['capacity']*=2;state['classes'][0]['opening']={'new':0,'re':5}
        after=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(after['teachingCostWeekly'],before['teachingCostWeekly'])
        self.assertEqual(after['teachingCostPerCapacityWeekly'],before['teachingCostPerCapacityWeekly']/2)
        self.assertAlmostEqual(after['teachingCostPerStudentWeekly'],after['teachingCostWeekly']/5)
    def test_no_future_year_fallback(self):
        with self.assertRaises(ValueError):integration_snapshot(blank(),self.ledger,2028)
    def test_corrupt_sum_or_duplicate_class_fails(self):
        ledger=copy.deepcopy(self.ledger);ledger['classes'][0]['weekly_cost']+=.02
        with self.assertRaises(ValueError):integration_snapshot(blank(),ledger,2027)
    def test_embedded_payroll_cannot_be_added_twice(self):
        parts=[dict(id='payroll',amount_cents=100000,contains_teaching=True),dict(id='operating',amount_cents=20000)]
        with self.assertRaises(ValueError):consolidate_expenses(parts,50000)
        self.assertEqual(consolidate_expenses(parts,50000,40000),130000)
        with self.assertRaises(ValueError):consolidate_expenses(parts+parts,50000,40000)
    def test_pe_rounding_and_cost_scenarios(self):
        self.assertEqual(break_even_students(182000,10000),19)
        self.assertEqual(break_even_students(182000+10000+20000,10000),22)
        self.assertEqual(break_even_students(182000,10000,1000),21)
        self.assertIsNone(break_even_students(None,10000))
        self.assertIsNone(break_even_students(10000,0))
    def test_official_total_is_reference_and_never_incremented(self):
        state=blank();state['breakEven']['plans']=[dict(id='p',year=2027,version=1,officialTotals=dict(totalExpensesMonthly=841486.96))]
        d=integration_snapshot(state,self.ledger,2027)
        self.assertEqual(d['totalExpensesMonthly'],841486.96)
        self.assertEqual(d['totalExpensesMonthlyDifference'],0)
        self.assertEqual(d['additionalExpenseCents'],0)
    def test_existing_budget_cost_enables_class_pe_without_monthly_teaching(self):
        state=blank();room=state['classes'][0]
        room['opening']={'new':0,'re':10}
        state['academicYears'][0]['classifications'][room['id']]={'fixed':{'noDiscount':10}}
        state['breakEven']['plans']=[dict(year=2027,version=1,delinquency={'officialPercent':0},structuralTicket={'discountPercent':0,'origin':'fixture'},
            mappings=[dict(operationalClassId=room['id'],status='mapped',costEvidence={'status':'verified'},costMonthly=10000,sourceRowId='b',budgetClassName=room['name'])],
            officialBudget={'classRows':[dict(id='b',className=room['name'],status='recognized')]})]
        d=integration_snapshot(state,self.ledger,2027);r=d['classes'][0]
        self.assertEqual(r['totalCostMonthly'],10000)
        self.assertEqual(r['breakEvenStudents'],11)
        self.assertEqual(r['studentsNeeded'],1)
        self.assertAlmostEqual(r['operatingResultMonthly'],-693.10)
        self.assertEqual(r['teachingCostMonthly'],2397.60)
        self.assertLess(r['safetyMarginStudents'],0)

    def test_structural_pe_does_not_depend_on_current_students_or_classifications(self):
        state=blank();room=state['classes'][0]
        state['breakEven']['plans']=[dict(year=2027,version=1,delinquency={'officialPercent':4.5},
            structuralTicket={'discountPercent':3,'origin':'fixture oficial'},
            mappings=[dict(operationalClassId=room['id'],status='mapped',costEvidence={'status':'verified'},costMonthly=5000,sourceRowId='b',budgetClassName=room['name'])],
            officialBudget={'classRows':[dict(id='b',className=room['name'],status='recognized')]})]
        before=integration_snapshot(state,self.ledger,2027)['classes'][0]
        room['opening']={'new':0,'re':0};room['unclassified']=0
        state['academicYears'][0]['classifications'][room['id']]={'fixed':{}}
        after=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(after['breakEvenStudents'],before['breakEvenStudents'])
        self.assertEqual(after['structuralTicketMonthly'],before['structuralTicketMonthly'])

    def test_capacity_changes_only_structural_percentage_and_physical_margin(self):
        state=blank();room=state['classes'][0]
        state['breakEven']['plans']=[dict(year=2027,version=1,delinquency={'officialPercent':0},structuralTicket={'discountPercent':0,'origin':'fixture'},
            mappings=[dict(operationalClassId=room['id'],status='mapped',costEvidence={'status':'verified'},costMonthly=20000,sourceRowId='b',budgetClassName=room['name'])],
            officialBudget={'classRows':[dict(id='b',className=room['name'],status='recognized')]})]
        before=integration_snapshot(state,self.ledger,2027)['classes'][0];room['capacity']*=2
        after=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(after['breakEvenStudents'],before['breakEvenStudents'])
        self.assertEqual(after['breakEvenPercentCapacity'],before['breakEvenPercentCapacity']/2)
        self.assertEqual(after['physicalMarginStudents']-before['physicalMarginStudents'],before['capacity'])

    def test_proven_cost_and_structural_ticket_change_pe(self):
        self.assertEqual(break_even_students(100000,50000),2)
        self.assertEqual(break_even_students(100001,50000),3)
        self.assertEqual(break_even_students(100000,25000),4)

    def test_unclassified_students_do_not_become_zero_discount_and_unproven_components_stay_explicit(self):
        state=blank();room=state['classes'][0];room['opening']={'new':0,'re':1}
        state['breakEven']['plans']=[dict(year=2027,version=1,delinquency={'officialPercent':0},structuralTicket={'discountPercent':0,'origin':'fixture'})]
        row=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertIsNone(row['netRevenueMonthly']);self.assertEqual(row['totalCostMonthly'],row['teachingCostMonthly'])
        self.assertEqual(row['breakEvenStudents'],3);self.assertIn('outros custos diretos',row['componentPendingReasons'][0])
        self.assertIn('DSR, encargos e hora-atividade não aplicados',row['componentPendingReasons'][1])

    def test_pe_above_capacity_has_explicit_alert(self):
        state=blank();room=state['classes'][0]
        state['breakEven']['plans']=[dict(year=2027,version=1,delinquency={'officialPercent':0},structuralTicket={'discountPercent':0,'origin':'fixture'},
            mappings=[dict(operationalClassId=room['id'],status='mapped',costEvidence={'status':'verified'},costMonthly=999999,sourceRowId='b',budgetClassName=room['name'])],
            officialBudget={'classRows':[dict(id='b',className=room['name'],status='recognized')]})]
        row=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertGreater(row['breakEvenStudents'],row['capacity'])
        self.assertEqual(row['structuralAlert'],'PE acima da capacidade física da turma')

    def test_reconciled_weekly_teaching_cost_reaches_every_pe_row_without_manual_entry(self):
        rows=integration_snapshot(blank(),self.ledger,2027)['classes']
        self.assertEqual(len(rows),41);self.assertTrue(all(row['teachingCostWeekly'] is not None for row in rows))
        self.assertEqual(next(row for row in rows if row['name']=='G2 A')['teachingCostWeekly'],532.80)

    def test_structural_ticket_requires_explicit_discount_premise(self):
        self.assertIsNone(structural_ticket_cents(930.69,None,4.5))
        self.assertEqual(structural_ticket_cents(930.69,3,4.5),86214)

    def test_official_monthly_factor_is_exact_and_adds_no_dsr_or_charges(self):
        self.assertEqual(monthly_teaching_base_cents(53280),239760)
        row=integration_snapshot(blank(),self.ledger,2027)['classes'][0]
        self.assertEqual(row['teachingCostMonthly'],2397.60)
        self.assertEqual(row['dsrStatus'],'NAO_APLICADO_COMPOSICAO_NAO_COMPROVADA')
        self.assertEqual(row['chargesStatus'],'NAO_APLICADOS_COMPOSICAO_NAO_COMPROVADA')
    def test_general_pe_uses_current_complete_revenue_and_existing_expenses(self):
        state=blank()
        for room in state['classes']:
            state['academicYears'][0]['classifications'][room['id']]={'fixed':{'noDiscount':room['students']}}
        state['breakEven']['plans']=[dict(year=2027,version=1,officialTotals={'totalExpensesMonthly':841486.96},delinquency={'officialPercent':0})]
        d=integration_snapshot(state,self.ledger,2027)
        self.assertIsNotNone(d['breakEvenStudents'])
        self.assertEqual(d['totalExpensesMonthly'],841486.96)
        self.assertEqual(d['teachingCostMonthly'],115548.16)
        self.assertEqual(d['additionalExpenseCents'],0)
