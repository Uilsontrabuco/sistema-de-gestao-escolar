import copy
import unittest
from server import blank
from teaching_cost import load_documentary_costs
from financial_integration import integration_snapshot, consolidate_expenses, break_even_students


class FinancialIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.ledger=load_documentary_costs(blank()['classes'])
    def test_closed_weekly_basis_41_classes_50_professors_and_no_monthly_guess(self):
        state=blank();before=copy.deepcopy(state);d=integration_snapshot(state,self.ledger,2027)
        self.assertEqual(state,before)
        self.assertEqual(d['teachingCostWeekly'],25677.35)
        self.assertEqual(sum(r['teachingCostWeeklyCents'] for r in d['classes']),2567735)
        self.assertEqual(len(d['classes']),41)
        self.assertEqual(self.ledger['summary']['reconciled_professors'],50)
        self.assertIsNone(d['teachingCostMonthly']);self.assertIsNone(d['teachingCostAnnual'])
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
        state['breakEven']['plans']=[dict(year=2027,version=1,delinquency={'officialPercent':0},
            mappings=[dict(operationalClassId=room['id'],status='mapped',costEvidence={'status':'verified'},costMonthly=10000,sourceRowId='b',budgetClassName=room['name'])],
            officialBudget={'classRows':[dict(id='b',className=room['name'],status='recognized')]})]
        d=integration_snapshot(state,self.ledger,2027);r=d['classes'][0]
        self.assertEqual(r['totalCostMonthly'],10000)
        self.assertEqual(r['breakEvenStudents'],11)
        self.assertEqual(r['studentsNeeded'],1)
        self.assertAlmostEqual(r['operatingResultMonthly'],-693.10)
        self.assertIsNone(r['teachingCostMonthly'])
        self.assertEqual(d['classBreakEvenCounts']['below'],1)
    def test_general_pe_uses_current_complete_revenue_and_existing_expenses(self):
        state=blank()
        for room in state['classes']:
            state['academicYears'][0]['classifications'][room['id']]={'fixed':{'noDiscount':room['students']}}
        state['breakEven']['plans']=[dict(year=2027,version=1,officialTotals={'totalExpensesMonthly':841486.96},delinquency={'officialPercent':0})]
        d=integration_snapshot(state,self.ledger,2027)
        self.assertIsNotNone(d['breakEvenStudents'])
        self.assertEqual(d['totalExpensesMonthly'],841486.96)
        self.assertIsNone(d['teachingCostMonthly'])
        self.assertEqual(d['additionalExpenseCents'],0)
