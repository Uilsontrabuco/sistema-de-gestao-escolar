import json,unittest
from copy import deepcopy
from pathlib import Path
from administrative_pe_2027 import administrative_view,balanced_additions,exact_ticket
from personnel_confirmations_2027 import personnel_evidence

ROOT=Path(__file__).resolve().parents[1]

class AdministrativePETests(unittest.TestCase):
    def setUp(self):
        self.before=json.loads((ROOT/'output/pre-publicacao-2027/resultado-final.json').read_text(encoding='utf-8'))
        self.ledger=json.loads((ROOT/'output/pe-real-2027/reconciliacao-custos.json').read_text(encoding='utf-8'))

    def test_balancing_only_moves_twenty_and_respects_capacity(self):
        self.assertEqual(balanced_additions(22,0,35,28,20),(0,20))
        self.assertEqual(balanced_additions(10,10,12,30,20),(2,18))
        with self.assertRaises(ValueError):balanced_additions(22,0,22,19,20)

    def test_school_total_and_negative_vacancies_preserved(self):
        out=administrative_view(self.before,self.ledger,eighth_c_exists=False)
        before=out['administrativeReconciliation']['before'];after=out['administrativeReconciliation']['after']
        self.assertEqual((after['enrolled'],after['new'],after['re']),(775,37,738))
        self.assertEqual((after['classes'],after['capacity'],after['vacancies']),(40,1075,300))
        self.assertEqual(before['enrolled'],after['enrolled'])
        self.assertEqual([r['vacancies'] for r in self.before['rows'] if r['vacancies']<0],
                         [r['vacancies'] for r in out['rows'] if r['vacancies']<0])

    def test_all_costs_pes_and_tickets_unchanged(self):
        out=administrative_view(self.before,self.ledger,eighth_c_exists=False)
        original={r['id']:r for r in self.before['rows']}
        for r in out['rows']:
            for field in ['pe','consideredCostCents','ticketCents','nominalCosts','costs','tuitionCents']:
                self.assertEqual(r[field],original[r['id']][field])
        self.assertEqual(out['administrativeReconciliation']['after']['peMissing'],3)

    def test_archive_not_active_and_revenue_not_cash(self):
        out=administrative_view(self.before,self.ledger,eighth_c_exists=False)
        self.assertNotIn('8º C',[r['name'] for r in out['rows']])
        self.assertEqual(out['archivedRows'][0]['enrolled'],20)
        b=next(r for r in out['rows'] if r['name']=='8º B')
        self.assertEqual((b['enrolled'],b['vacancies'],b['distanceToPE']),(20,8,-12))
        self.assertIsNone(b['currentRevenueCents']);self.assertFalse(b['currentRevenueComplete'])

    def test_input_and_reapplication_are_safe(self):
        before=deepcopy(self.before);ledger=deepcopy(self.ledger)
        out=administrative_view(self.before,self.ledger,eighth_c_exists=False)
        self.assertEqual(self.before,before);self.assertEqual(self.ledger,ledger)
        self.assertEqual(out,administrative_view(out,self.ledger,eighth_c_exists=False))

    def test_changed_source_count_is_not_silently_moved(self):
        next(r for r in self.before['rows'] if r['name']=='8º C')['enrolled']=21
        with self.assertRaises(ValueError):administrative_view(self.before,self.ledger,eighth_c_exists=False)

    def test_existing_class_cost_prevents_unreconciled_removal(self):
        next(r for r in self.before['rows'] if r['name']=='8º C')['consideredCostCents']=1
        with self.assertRaises(ValueError):administrative_view(self.before,self.ledger,eighth_c_exists=False)

    def test_duplicate_cost_destination_blocks(self):
        self.ledger['allocations'].append(deepcopy(self.ledger['allocations'][0]))
        with self.assertRaises(ValueError):administrative_view(self.before,self.ledger,eighth_c_exists=False)

    def test_cost_absorption_or_formula_mismatch_blocks(self):
        next(r for r in self.before['rows'] if r['name']=='7º A')['consideredCostCents']+=1582705
        with self.assertRaises(ValueError):administrative_view(self.before,self.ledger,eighth_c_exists=False)

    def test_repeated_pcld_deduction_blocks(self):
        self.ledger['allocations'][0]['pcldRemovedCents']*=2
        with self.assertRaises(ValueError):administrative_view(self.before,self.ledger,eighth_c_exists=False)

    def test_hours_confirmed_without_imaginary_charges(self):
        for p in personnel_evidence()['rows']:
            self.assertEqual(p['weeklyHours'],44)
            self.assertEqual(p['monthlySalaryCents'],169050)
            self.assertIsNone(p['totalEmployerCostCents'])
            self.assertEqual(p['appliedAdditionalCostCents'],0)

    def test_latest_correction_keeps_eighth_c_and_all_original_rows(self):
        out=administrative_view(self.before,self.ledger)
        self.assertEqual(out['rows'],self.before['rows'])
        self.assertEqual(out['archivedRows'],[])
        self.assertEqual(out['administrativeReconciliation']['after']['classes'],41)
        self.assertEqual(out['administrativeReconciliation']['after']['capacity'],1103)
        self.assertEqual(out['administrativeReconciliation']['redistributedStudents'],0)
        self.assertEqual(out,administrative_view(out,self.ledger))

    def test_corrected_structure_does_not_reuse_superseded_scenario(self):
        superseded=administrative_view(self.before,self.ledger,eighth_c_exists=False)
        with self.assertRaises(ValueError):administrative_view(superseded,self.ledger)

if __name__=='__main__':unittest.main()
