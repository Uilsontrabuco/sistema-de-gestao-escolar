import json
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from server import blank, recalculate, Store
from pe_real import AUDIT
from benefits_2027 import import_benefits, sync_benefits, summarize, apply_benefit_view
from enrollment_2027 import apply_snapshot_to_state


class PlannedBenefitsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records=json.loads((AUDIT/'registros-saneados-locais.json').read_text(encoding='utf-8'))

    def state(self):return import_benefits(apply_snapshot_to_state(blank()),self.records)

    def enroll(self,s,index=0,**extra):
        b=s['benefits'][index]
        s['enrollments']['students']=[dict(id='nominal-1',studentName=b['studentName'],classId=b['classId'],year=2027,status='active',**extra)]
        return b

    def test_forecast_persistable_without_enrollment(self):
        s=self.state();v=summarize(s)
        self.assertEqual((v['total'],v['active'],v['waiting'],v['pending']),(1016,0,902,114))

    def test_forecast_never_creates_enrollment_or_occupancy(self):
        before=apply_snapshot_to_state(blank());after=import_benefits(before,self.records)
        self.assertEqual(before['classes'],after['classes']);self.assertEqual(before['enrollments'],after['enrollments'])
        self.assertEqual(sum(c['students'] for c in after['classes']),775)
        self.assertEqual(sum(c['capacity'] for c in after['classes']),1103)

    def test_future_exact_name_activates_once(self):
        s=self.state();b=self.enroll(s);recalculate(s)
        self.assertEqual(b['state'],'ATIVO');self.assertEqual(len(s['benefits']),1016)
        before=deepcopy(s);recalculate(s);self.assertEqual(before,s)

    def test_exact_id_preferred_over_changed_name(self):
        s=self.state();b=s['benefits'][0];b['studentId']='ID1'
        self.enroll(s,studentId='ID1');s['enrollments']['students'][0]['studentName']='Nome com grafia diferente'
        sync_benefits(s);self.assertEqual(b['state'],'ATIVO')

    def test_conflicting_id_never_matches_same_name(self):
        s=self.state();b=s['benefits'][0];b['studentId']='ID1';self.enroll(s,studentId='ID2')
        sync_benefits(s);self.assertEqual(b['state'],'PREVISTO')

    def test_similar_name_not_matched(self):
        s=self.state();b=self.enroll(s);s['enrollments']['students'][0]['studentName']+=' Filho'
        sync_benefits(s);self.assertEqual(b['state'],'PREVISTO')

    def test_homonyms_pending(self):
        s=self.state();b=self.enroll(s)
        s['enrollments']['students'].append(dict(s['enrollments']['students'][0],id='outro'))
        sync_benefits(s);self.assertEqual(b['linkStatus'],'IDENTIDADE_AMBIGUA')

    def test_wrong_class_no_transfer(self):
        s=self.state();b=self.enroll(s);s['enrollments']['students'][0]['classId']=s['classes'][0]['id']
        sync_benefits(s);self.assertEqual(b['linkStatus'],'TURMA_DIVERGENTE')

    def test_import_is_idempotent(self):
        s=self.state();self.assertEqual(import_benefits(s,self.records),s)

    def test_all_benefits_retained_but_invalid_classes_quarantined(self):
        s=self.state();self.assertEqual(len(s['benefits']),1016)
        self.assertEqual(sum(b['linkStatus']=='TURMA_INVALIDA' for b in s['benefits']),114)
        self.assertEqual({b['sourceClass'] for b in s['benefits']},{r['sourceClass'] for r in self.records})

    def test_rates_45_50_95_once(self):
        s=self.state()
        for row,rate in ((275,'0.45'),(276,'0.45'),(697,'0.5'),(482,'0.95')):
            b=next(b for b in s['benefits'] if b['sourceRow']==row)
            self.assertEqual(b['rate'],rate);self.assertEqual(b['grossCents']-b['discountCents'],b['postDiscountCents'])

    def test_planned_ticket_uses_all_future_members(self):
        s=self.state();a=summarize(s);self.enroll(s);sync_benefits(s);b=summarize(s)
        self.assertEqual([x['planned'] for x in a['rows']],[x['planned'] for x in b['rows']])
        self.assertEqual(sum(x['activeCount'] for x in b['rows']),1)

    def test_current_ticket_only_active_full_coverage(self):
        s=self.state();b=self.enroll(s);s['classes'][2]['students']=1;sync_benefits(s)
        r=next(r for r in summarize(s)['rows'] if r['classId']==b['classId'])
        self.assertEqual(r['activeCount'],1);self.assertIsNotNone(r['currentTicketCents'])
        self.assertEqual(r['currentRevenueCents'],r['active']['netCents'])

    def test_partial_active_coverage_not_extrapolated(self):
        s=self.state();b=self.enroll(s);sync_benefits(s)
        r=next(r for r in summarize(s)['rows'] if r['classId']==b['classId'])
        self.assertIsNone(r['currentRevenueCents']);self.assertIsNone(r['currentTicketCents'])
        self.assertIsNotNone(r['active']['netCents'])

    def test_pe_uses_forecast_not_activation(self):
        s=self.state();report=json.loads((AUDIT/'resultado.json').read_text(encoding='utf-8'))
        a=apply_benefit_view(report,s);self.enroll(s);sync_benefits(s);b=apply_benefit_view(report,s)
        self.assertEqual([r['pe'] for r in a['rows']],[r['pe'] for r in b['rows']])
        self.assertTrue(all(r['currentRevenueCents'] is None or r['enrolled']==0 for r in a['rows']))

    def test_cancellation_preserves_forecast(self):
        s=self.state();b=self.enroll(s);sync_benefits(s)
        s['enrollments']['students'][0]['status']='cancelled';sync_benefits(s)
        self.assertEqual(b['state'],'PREVISTO');self.assertEqual(len(s['benefits']),1016)

    def test_cancelled_roster_does_not_reactivate_from_old_history(self):
        s=self.state();b=self.enroll(s,studentId='ID1');b['studentId']='ID1'
        s['enrollments']['history']=[dict(id='hist',studentId='ID1',classId=b['classId'],quantity=1,type='new',date='2026-09-21',year=2027)]
        sync_benefits(s);self.assertEqual(b['state'],'ATIVO')
        s['enrollments']['students'][0]['status']='cancelled';sync_benefits(s)
        self.assertEqual(b['state'],'PREVISTO')

    def test_store_patch_auto_activation_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'test.db');user=store.create_user('Fixture','future@fixture.invalid','Fixture-only-2027',is_admin=True)
            s=self.state()
            with store.db() as db:db.execute('UPDATE state SET payload=? WHERE id=1',(json.dumps(s),))
            before=deepcopy(s);b=self.enroll(s)
            store.patch(user,{'enrollments':s['enrollments']},store.state()[1],'enrollments')
            actual,version=store.state();self.assertEqual(actual['benefits'][0]['state'],'ATIVO')
            self.assertEqual(actual['classes'],before['classes']);self.assertEqual(actual['enrollments']['new'],37)
            store.patch(user,{'enrollments':s['enrollments']},version,'enrollments')
            self.assertEqual(actual['benefits'],store.state()[0]['benefits'])

    def test_view_only_cannot_activate_by_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'test.db');admin=store.create_user('Fixture','admin@fixture.invalid','Fixture-only-2027',is_admin=True)
            user=store.create_user('Consulta','view@fixture.invalid','Fixture-only-2027',{'enrollments':['view']},actor=admin)
            s=self.state();self.enroll(s)
            with self.assertRaises(PermissionError):store.patch(user,{'enrollments':s['enrollments']},store.state()[1],'enrollments')


if __name__=='__main__':unittest.main()
