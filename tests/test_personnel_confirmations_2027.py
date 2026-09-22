import unittest
from personnel_confirmations_2027 import personnel_evidence, personnel_note


class PersonnelConfirmationTests(unittest.TestCase):
    def test_confirmed_salary_is_not_total_cost_or_budget_addition(self):
        data = personnel_evidence()
        self.assertEqual(data['salarySumCents'], 507150)
        for row in data['rows']:
            self.assertEqual(row['monthlySalaryCents'], 169050)
            self.assertEqual(row['role'], 'Auxiliar de Serviços Gerais')
            self.assertIsNone(row['totalEmployerCostCents'])
            self.assertIsNone(row['budgetCoverageCents'])
            self.assertEqual(row['appliedAdditionalCostCents'], 0)

    def test_replacement_and_lotation_do_not_invent_posts(self):
        rows = {r['employeeId']: r for r in personnel_evidence()['rows']}
        self.assertEqual(set(rows), {'952', '953', '955'})
        self.assertEqual(rows['952']['replacesEmployeeId'], '679')
        self.assertIsNone(rows['952']['className'])
        self.assertIsNone(rows['953']['className'])
        self.assertEqual(rows['955']['className'], 'G3 B')

    def test_evidence_cannot_mutate_subsequent_reports(self):
        a = personnel_evidence()
        a['rows'][0]['monthlySalaryCents'] = 0
        self.assertEqual(personnel_evidence()['rows'][0]['monthlySalaryCents'], 169050)
        self.assertIn('21/09/2026', personnel_note())


if __name__ == '__main__':
    unittest.main()
