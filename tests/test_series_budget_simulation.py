import json,unittest
from pathlib import Path
from copy import deepcopy
from series_budget_simulation import simulate,distribute

ROOT=Path(__file__).resolve().parents[1]
class SeriesSimulationTests(unittest.TestCase):
    def setUp(self):
        self.r=json.loads((ROOT/'output/pe-administrativo-aprovado-20270922/resultado-administrativo.json').read_text(encoding='utf-8'))
        self.l=json.loads((ROOT/'output/pe-real-2027/reconciliacao-custos.json').read_text(encoding='utf-8'))

    def test_cent_exact_blocks_series_and_school(self):
        s=simulate(self.r,self.l)
        for g in s['series']:
            self.assertEqual(g['budgetBeforeCents'],g['budgetAfterCents'])
            self.assertEqual(sum(p['deltaFromPreviouslyAllocatedCents'] for p in g['proposals']),0)
            for block,key in [('payroll','payrollCents'),('support','supportCents'),('generalNet','generalNetCents')]:
                self.assertEqual(sum(p[key] for p in g['proposals']),g['pools'][block])
        self.assertEqual(sum(r['consideredCostCents'] for r in s['rows']),60564103)
        self.assertEqual(s['reserveAfterCents'],1582705)

    def test_anchors_and_historical_control_are_not_added_again(self):
        s=simulate(self.r,self.l)
        for g in s['series']:
            for p in g['proposals']:
                self.assertGreaterEqual(p['payrollCents'],p['teacherAnchorCents'])
                self.assertGreaterEqual(p['supportCents'],p['otherNominalAnchorCents'])
                self.assertEqual(p['costAfterCents'],p['payrollCents']+p['supportCents']+p['generalNetCents'])
                if p['name']=='8º C':
                    self.assertEqual(p['teacherAnchorCents'],287865)
                    self.assertEqual(p['historicalNonAdditiveControlCents'],27414)

    def test_no_input_mutation_and_other_26_unchanged(self):
        before=deepcopy(self.r);ledger=deepcopy(self.l);s=simulate(self.r,self.l)
        self.assertEqual(before,self.r);self.assertEqual(ledger,self.l)
        affected={p['id'] for g in s['series'] for p in g['proposals']}
        self.assertEqual(len(affected),15)
        for a,b in zip(before['rows'],s['rows']):
            if a['id'] not in affected:self.assertEqual(a,b)
            for key in ('capacity','enrolled','vacancies','newStudents','reenrolled','ticketCents'):
                self.assertEqual(a[key],b[key])

    def test_only_simulation_pe_and_no_false_documentary_closure(self):
        s=simulate(self.r,self.l)
        self.assertFalse(s['integralDocumentaryClosure'])
        expected={'1º D':14,'2º D':21,'3º D':19,'8º C':11}
        for r in s['rows']:
            if r['name'] in expected:
                self.assertEqual(r['pe'],expected[r['name']])
                self.assertEqual(sum(p['cents'] for p in r['costs']),r['consideredCostCents'])
                self.assertIsNone(r['verifiedCostCents'])

    def test_capacity_driver_independent_of_enrollment(self):
        original=simulate(self.r,self.l)
        next(r for r in self.r['rows'] if r['name']=='1º D')['enrolled']=18
        changed=simulate(self.r,self.l)
        self.assertEqual([r['consideredCostCents'] for r in original['rows']],[r['consideredCostCents'] for r in changed['rows']])

    def test_insufficient_rubric_blocks_instead_of_erasing_anchor(self):
        next(r for r in self.r['rows'] if r['name']=='1º D')['teacherCents']=100000000
        with self.assertRaises(ValueError):simulate(self.r,self.l)

    def test_integer_remainder_deterministic_without_losing_cent(self):
        self.assertEqual(distribute(5,[('b',1),('a',1)]),{'b':2,'a':3})
        with self.assertRaises(ValueError):distribute(-1,[('a',1)])

if __name__=='__main__':unittest.main()
