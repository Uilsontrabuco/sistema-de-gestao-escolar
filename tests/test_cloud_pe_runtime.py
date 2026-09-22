import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import blank
import teaching_cost
from financial_integration import integration_snapshot


class CloudPeRuntimeTests(unittest.TestCase):
    def test_clean_runtime_without_ignored_output_loads_41_classes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(teaching_cost, 'ROOT', Path(directory)):
            ledger=teaching_cost.load_documentary_costs(blank()['classes'])
        self.assertEqual(ledger['runtime_source'],'PACKAGED_SANITIZED_RECONCILED_SNAPSHOT')
        self.assertEqual(ledger['extraction_sha256'],teaching_cost.SOURCE_HASH)
        self.assertEqual(len(ledger['classes']),41)
        self.assertEqual(ledger['validated_cost_cents'],2726065)
        data=integration_snapshot(blank(),ledger,2027)
        self.assertEqual(data['contractVersion'],'pe-2027-v1')
        self.assertEqual(data['integrationStatus'],'loaded')
        self.assertEqual(len(data['classes']),41)
        self.assertTrue(all(row['breakEvenStudents'] is not None for row in data['classes']))
        g2=next(row for row in data['classes'] if row['name']=='G2 A')
        self.assertEqual(g2['teachingCostWeekly'],532.80)
        self.assertEqual(g2['teachingCostMonthly'],2397.60)
        self.assertEqual(ledger['source_year'],2026)
        self.assertEqual(ledger['basis_status'],'CONCILIADO_PROJECAO_2026')
        self.assertEqual(g2['componentContracts']['teachingMonthly']['status'],'loaded')
        self.assertEqual(data['projectionLabel'],'Projeção 2027 — base estrutural: Carga Horária Oficial 2026')
        g3=next(row for row in data['classes'] if row['name']=='G3 A')
        self.assertEqual(g3['teachingCostWeekly'],518.40)
        self.assertEqual(g3['teachingCostMonthly'],2332.80)
        third=next(row for row in data['classes'] if row['name']=='3º A')
        self.assertEqual((third['teachingCostWeekly'],third['teachingCostMonthly']),(502.20,2259.90))
        g5c=next(row for row in data['classes'] if row['name']=='G5 C')
        self.assertEqual((g5c['teachingCostWeekly'],g5c['teachingCostMonthly']),(723.35,3255.08))
        self.assertEqual(g5c['componentContracts']['teachingWeekly']['status'],'loaded')
        self.assertEqual(sum(row['componentContracts']['teachingWeekly']['status']=='loaded' for row in data['classes']),41)
        source_row=next(row for row in ledger['classes'] if row['class_name']=='G5 C')
        self.assertIn('Confirmação operacional CAJ',source_row['projection_equivalence_source'])
        self.assertEqual(source_row['teacher_identity_status'],'NAO_INFERIDA_NEM_COPIADA')
        self.assertEqual(g2['componentContracts']['otherDirect']['status'],'loaded')
        self.assertEqual(g2['otherDirectCostsMonthly'],750)
        self.assertEqual(g2['indirectExpensesMonthly'],10395.49)
        self.assertEqual(g2['totalCostMonthly'],13543.09)
        self.assertEqual(data['expenseReconciliation']['official'],841486.96)
        self.assertEqual(data['expenseReconciliation']['difference'],0)
        self.assertEqual(data['expenseReconciliation']['pendingClassification'],0)

    def test_packaged_snapshot_contains_no_personal_teacher_records(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(teaching_cost, 'ROOT', Path(directory)):
            ledger=teaching_cost.load_documentary_costs(blank()['classes'])
        self.assertEqual(ledger['professors'],[])
        self.assertEqual(ledger['operational_allocations'],[])

    def test_snapshot_uses_canonical_class_name_not_local_fixture_id(self):
        classes=blank()['classes']
        for index,room in enumerate(classes):room['id']=f'id-migrado-{index}'
        ledger=__import__('teaching_cost_snapshot').packaged_ledger(classes)
        self.assertEqual(len(ledger['classes']),41)
        self.assertEqual(ledger['classes'][0]['class_id'],'id-migrado-0')


if __name__=='__main__':
    unittest.main()
