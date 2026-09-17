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
        self.assertEqual(ledger['validated_cost_cents'],2567735)
        data=integration_snapshot(blank(),ledger,2027)
        self.assertEqual(data['contractVersion'],'pe-2027-v1')
        self.assertEqual(data['integrationStatus'],'loaded')
        self.assertEqual(len(data['classes']),41)
        self.assertTrue(all(row['breakEvenStudents'] is not None for row in data['classes']))
        g2=next(row for row in data['classes'] if row['name']=='G2 A')
        self.assertEqual(g2['teachingCostWeekly'],532.80)
        self.assertEqual(g2['teachingCostMonthly'],2397.60)
        self.assertEqual(g2['componentContracts']['teachingMonthly']['status'],'loaded')
        self.assertEqual(g2['componentContracts']['otherDirect']['status'],'zero_real')
        self.assertEqual(data['expenseReconciliation']['official'],841486.96)
        self.assertEqual(data['expenseReconciliation']['difference'],0)

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
