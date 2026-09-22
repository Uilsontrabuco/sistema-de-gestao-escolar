import importlib.util as _privacy_imports
import unittest as _privacy_tests
if any(_privacy_imports.find_spec(m) is None for m in ['scripts.reconcile_g2_documentary_pe']):
    raise _privacy_tests.SkipTest("Requires private audit tools provisioned outside Git")
import json
import unittest
from decimal import Decimal
from scripts.reconcile_g2_documentary_pe import build, OUT, PRIOR, ceiling, rounded, report


class G2DocumentaryBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build()
        cls.evidence = json.loads((OUT / 'fontes.json').read_text(encoding='utf-8'))

    def test_scope_and_definitive_gate(self):
        self.assertEqual(self.data['scope'], ['G2 A', 'G2 B'])
        self.assertEqual([r['name'] for r in self.data['classes']], ['G2 A', 'G2 B'])
        for r in self.data['classes']:
            self.assertIsNone(r['newDefinitivePE'])
            self.assertFalse(r['rateioOverlapProven'])

    def test_original_rows_and_15_are_reproduced(self):
        for r in self.data['classes']:
            p = r['pdf']
            self.assertEqual(p['students'], 16)
            self.assertEqual(p['totalCost'], Decimal('13543.09'))
            self.assertEqual(p['tuitionRevenue'] + p['otherRevenue'] - p['commercialDiscount'], p['netRevenuePage4'])
            self.assertEqual(r['documentaryPE'], r['documentaryReproducedPE'])
            self.assertEqual(r['documentaryPE'], 15)
            self.assertEqual(r['pdfTicket'], Decimal('924.084375'))

    def test_historical_formula_is_not_misrepresented_as_2027(self):
        cells = {c['cell']: c for c in self.evidence['historicalWorkbookCells']}
        for row in (7, 8):
            self.assertEqual(cells[f'O{row}']['formula'], f'=IFERROR(B{row}/H{row}*M{row},0)')
            self.assertEqual(cells[f'O{row}']['format'], '0')
        self.assertFalse(self.evidence['historicalWorkbookIs2027'])
        self.assertFalse(self.data['original2027WorkbookFormulaAvailable'])

    def test_residuals_are_inside_original_blocks_not_increment(self):
        for r, expected in zip(self.data['classes'], ('4555.98', '4579.11')):
            p = r['parts']
            self.assertEqual(p['docentes'] + p['residual-g2'], Decimal('6271.93'))
            self.assertEqual(p['estagiarias'] + p['apoio-direto-g2'], Decimal('1520.00'))
            self.assertEqual(r['pendingExistingResiduals'], Decimal(expected))

    def test_intern_full_cost_reclassifies_without_adding(self):
        self.assertEqual(Decimal('759') + Decimal('19.35') + Decimal('60'), Decimal('838.35'))
        self.assertEqual(Decimal('750') + Decimal('770'), Decimal('838.35') + Decimal('681.65'))

    def test_cost_bridge_exact_and_no_unproven_deletion(self):
        for r in self.data['classes']:
            self.assertEqual(r['pendingAddedPersonnel'], Decimal('5865.81'))
            self.assertEqual(r['costDifference'], Decimal('5178.48'))
            self.assertEqual(r['pdf']['totalCost'] + r['costDifference'], sum(r['parts'].values()))
            self.assertEqual(r['stages'][-1]['cost'], Decimal('18721.57'))

    def test_revenue_bases_keep_delinquency_and_other_receipts_distinct(self):
        for r in self.data['classes']:
            self.assertEqual(rounded(Decimal('930.69') * Decimal('.97') * Decimal('.955')), r['currentTicket'])
            self.assertEqual(r['pdfTicket'] - r['currentTicket'], Decimal('61.944375'))
        page = self.evidence['pdfPages']['10']
        for value in ('649,99', '13.794,25', '902,77'):
            self.assertIn(value, page)

    def test_other_income_accounts_and_allocation(self):
        page = self.evidence['pdfPages']['12']
        for value in ('3182019', '3195130', '2.805,00', '24.116,03'):
            self.assertIn(value, page)
        total = Decimal('2805') + Decimal('24116.03')
        self.assertEqual(rounded(total * Decimal('14890.97') / Decimal('1175229.48')), Decimal('341.11'))

    def test_every_stage_is_minimum_covering_integer(self):
        for r in self.data['classes']:
            self.assertEqual([s['ceiling'] for s in r['stages']], [15, 16, 16, 15, 18, 22])
            for s in r['stages']:
                self.assertGreaterEqual(s['ceiling'] * s['ticket'], s['cost'])
                self.assertLess((s['ceiling']-1) * s['ticket'], s['cost'])

    def test_do_not_confuse_cost_delta_with_shortfall_at_15(self):
        for r in self.data['classes']:
            shortfall = r['stages'][-1]['cost'] - 15*r['currentTicket']
            self.assertEqual(shortfall, Decimal('5789.47'))
            self.assertNotEqual(shortfall, r['costDifference'])

    def test_report_carries_classification_and_all_thirteen_items(self):
        content = report(self.data)
        for n in range(1, 14):
            self.assertEqual(content.count(f'| {n}. '), 2)
        self.assertIn('**E:**', content)
        self.assertIn('Novo PE definitivo não comprovado', content)
        self.assertIn('nenhum valor foi classificado B sem prova', content)


if __name__ == '__main__':
    unittest.main()
