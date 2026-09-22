import json,unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from benefits_2027 import apply_benefit_view,import_benefits
from enrollment_2027 import apply_snapshot_to_state,project_current
from server import blank
from pe_real import AUDIT

class G2PlanningTests(unittest.TestCase):
    def setUp(self):
        self.report=json.loads((AUDIT/'resultado.json').read_text(encoding='utf-8'))
        records=json.loads((AUDIT/'registros-saneados-locais.json').read_text(encoding='utf-8'))
        self.state=import_benefits(apply_snapshot_to_state(blank()),records)

    def test_exact_ticket_and_ceiling(self):
        d=apply_benefit_view(self.report,self.state)
        for r in d['rows'][:2]:
            self.assertEqual(Decimal(r['planningAssumption']['ticketExactCents']),Decimal('78215.1876'))
            self.assertEqual((r['consideredCostCents'],r['pe'],r['historicalDocumentaryPE']),(1075530,14,15))
            self.assertEqual(r['plannedBenefitCount'],0)

    def test_individual_mix_replaces_twelve_percent(self):
        s=self.state;b=deepcopy(s['benefits'][0]);b.update(id='fixture-g2',classId=self.report['rows'][0]['id'],grossCents=93069,discountCents=46535,rate='0.5')
        s['benefits'].append(b)
        r=apply_benefit_view(self.report,s)['rows'][0]
        self.assertNotIn('planningAssumption',r)
        self.assertEqual(r['ticketCents'],44440)
        self.assertEqual(r['pe'],25)

    def test_repeated_application_is_idempotent(self):
        a=apply_benefit_view(self.report,self.state)
        self.assertEqual(a,apply_benefit_view(a,self.state))

    def test_other_39_classes_unchanged(self):
        d=apply_benefit_view(self.report,self.state)
        self.assertEqual(self.report['rows'][2:],d['rows'][2:])

    def test_projection_not_nominal_cash(self):
        d=apply_benefit_view(self.report,self.state)
        self.assertEqual([r['distanceToPE'] for r in d['rows'][:2]],[-2,-14])
        self.assertEqual([r['projectedRevenueCents'] for r in d['rows'][:2]],[938582,0])
        self.assertEqual([r['currentRevenueCents'] for r in d['rows'][:2]],[None,0])
        self.assertEqual(project_current(d)['rows'][0]['projectedRevenueCents'],938582)

    def test_enrollment_does_not_change_pe_or_create_benefits(self):
        before=deepcopy(self.state)
        self.state['classes'][0]['students']=0
        d=apply_benefit_view(self.report,self.state)
        self.assertEqual(d['rows'][0]['pe'],14)
        self.assertEqual(self.state['benefits'],before['benefits'])
        self.assertEqual(d['summary']['pcldExpenseCents'],0)

if __name__=='__main__':unittest.main()
