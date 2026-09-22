import importlib.util as _privacy_imports
import unittest as _privacy_tests
if any(_privacy_imports.find_spec(m) is None for m in ['scripts.reconcile_class_coverage']):
    raise _privacy_tests.SkipTest("Requires private audit tools provisioned outside Git")
import unittest,json
from copy import deepcopy
from pathlib import Path
from scripts.reconcile_class_coverage import reconcile

ROOT=Path(__file__).resolve().parents[1]

class ClassCoverageTests(unittest.TestCase):
    def setUp(self):
        paths=['output/pe-administrativo-aprovado-20270922/resultado-administrativo.json',
               'pe_layers_2027_source.json','output/desbloqueio-pe-2027/docencia-reconstruida.json',
               'output/pe-real-2027/reconciliacao-custos.json']
        self.args=[json.loads((ROOT/p).read_text(encoding='utf-8')) for p in paths]

    def test_exclusive_categories_do_not_promote_pool_to_class_cost(self):
        for row in reconcile(*self.args)['rows']:
            self.assertTrue(all(p['category'] in 'ABCD' for p in row['parts']))
            self.assertTrue(all(p['classCents'] is None for p in row['parts'] if p['category']=='C'))
            self.assertIsNone(row['integralCostAfter']);self.assertIsNone(row['peAfter'])
            self.assertFalse(row['closeByLinkOnly'])

    def test_historical_admin_value_is_not_new_salary_or_deduction(self):
        row=reconcile(*self.args)['rows'][-1]
        self.assertEqual(row['historicalAdminOccurrenceCents'],27414)
        self.assertEqual(row['locatedABCents']+27414,row['totalStructuralTeacherCents'])
        self.assertEqual(row['totalStructuralTeacherCents'],315279)

    def test_mapping_cause_and_no_mutation(self):
        before=deepcopy(self.args);result=reconcile(*self.args)
        self.assertEqual(self.args,before)
        self.assertEqual([r['sourceMapProblem'] for r in result['rows']],['LINHA_AUSENTE']*3+['LINHA_ZERADA_EXCLUIDA_POR_FILTRO'])
        self.assertEqual(result['legacyReserveCents'],1582705)
        self.assertEqual(result['addedCostCents'],0)

    def test_repeated_shared_occurrence_is_blocked(self):
        row=next(r for r in self.args[2]['classes'] if r['class_name']=='1º D')
        row['shared_allocations'].append(deepcopy(row['shared_allocations'][0]))
        with self.assertRaises(AssertionError):reconcile(*self.args)

if __name__=='__main__':unittest.main()
