import json
import unittest
from copy import deepcopy
from pathlib import Path
from approved_residual_allocation_2027 import reconcile, AUTHORIZED

class ApprovedResidualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checkpoint=json.loads((Path(__file__).resolve().parents[1]/'output/forense-saldos-2027/composicao-e-simulacao-conservadora.json').read_text(encoding='utf-8'))

    def test_full_envelope_and_all_classes(self):
        s=reconcile(self.checkpoint)
        self.assertEqual(s['schoolAfterCents'],60564103)
        self.assertEqual(s['reserveCents'],1582705)
        self.assertEqual(len(s['rows']),41)
        self.assertTrue(all(r['pe'] is not None for r in s['rows']))
        self.assertEqual(sum(r['enrolled'] for r in s['rows']),775)
        self.assertEqual(sum(r['capacity'] for r in s['rows']),1103)

    def test_protected_nominals_funded_once_inside_envelope(self):
        s=reconcile(self.checkpoint)
        self.assertEqual(s['nominalCoverageCents'],1197603)
        self.assertEqual(s['globalResidualCents'],11215599)
        for d in s['details']:
            self.assertGreaterEqual(d['costAfterCents'],d['anchorCents'])
            self.assertEqual(d['costAfterCents'],d['anchorCents']+d['inheritedCoverageCents']+sum(d['globalAllocation'].values()))
        eighth=next(d for d in s['details'] if d['name']=='8º C')
        self.assertEqual(eighth['teacherCents'],287865)
        for k,v in AUTHORIZED.items():
            self.assertEqual(s['bridges'][k]['distributedCents'],v)

    def test_capacity_not_enrollment_and_cent_rounding(self):
        changed=deepcopy(self.checkpoint)
        changed['conservativeRows'][0]['enrolled']=0
        first,second=reconcile(self.checkpoint),reconcile(changed)
        for a,b in zip(first['details'],second['details']):
            self.assertEqual(a['costAfterCents'],b['costAfterCents'])
            for k in AUTHORIZED:
                exact=first['bridges'][k]['globalDistributedCents']*a['capacity']/1103
                self.assertLessEqual(abs(a['globalAllocation'][k]-exact),1)

    def test_no_mutation_and_no_extra_nominal_on_existing_coverage(self):
        frozen=deepcopy(self.checkpoint)
        s=reconcile(self.checkpoint)
        self.assertEqual(frozen,self.checkpoint)
        self.assertEqual(sum(any(d['nominalCoverageFromAuthorized'].values()) for d in s['details']),4)
        self.assertEqual(s,reconcile(self.checkpoint))

    def test_changed_pool_is_blocked(self):
        changed=deepcopy(self.checkpoint)
        next(c for c in changed['components'] if c['component']=='payrollCents / saldo')['cents']+=1
        with self.assertRaises(ValueError):
            reconcile(changed)
