from contextlib import closing
import json,unittest,tempfile,sqlite3,io
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from scripts.prepublication_2027 import collect
from local_backup import build_backup,restore_new
from server import blank,Handler
from benefits_2027 import import_benefits
from enrollment_2027 import apply_snapshot_to_state
from pe_real import AUDIT,load_report

class PrepublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.d=collect();cls.r=cls.d['report'];cls.c=cls.r['costReconciliation']
    def test_reserve_every_cent_and_no_invented_destination(self):
        self.assertEqual(sum(x['valueCents'] for x in self.d['parts']),1582705)
        self.assertTrue(all(x['classification']=='E' and x['className'] is None for x in self.d['parts']))
    def test_reprocess_114_and_all_1016_preserved(self):
        self.assertEqual(self.d['benefits'],dict(ATIVOS=0,PREVISTOS=902,PENDENTES_DE_TURMA=114,AMBIGUOS=0))
    def test_pcld_not_added_to_delinquency(self):
        self.assertEqual(self.r['summary']['pcldExpenseCents'],0)
        self.assertEqual(sum(x['pcldRemovedCents'] for x in self.c['allocations']),4211780)
    def test_4126005_not_added_to_individual_discount(self):
        a=next(x for x in self.c['accounts'] if x['code']=='4126005')
        self.assertEqual(a['monthlyCents'],4838820);self.assertIn('SUBSTITUIDA',a['treatment'])
    def test_4126007_not_added_to_individual_discount(self):
        a=next(x for x in self.c['accounts'] if x['code']=='4126007')
        self.assertEqual(a['monthlyCents'],12951288);self.assertIn('SUBSTITUIDA',a['treatment'])
    def test_commercial_and_scholarship_one_economic_reduction(self):
        for r in self.r['rows']:
            if r['acceptedStudentCount']:
                self.assertEqual(r['grossCents']-r['discountCents'],r['postDiscountCents'])
        self.assertEqual(sum(x['discountReclassifiedCents'] for x in self.c['allocations']),17790108)
    def test_shared_allocation_and_interns_not_added_twice(self):
        for r in self.r['rows']:
            if r.get('costBridge'):
                self.assertEqual(sum(x['cents'] for x in r['costs']),r['consideredCostCents'])
        self.assertEqual(sum(x['costCents'] for x in self.c['allocations']),62146808)
    def test_replacement_is_one_post(self):
        people=self.c['historicalPayroll']
        self.assertEqual(sum('Jailane' in x['person'] for x in people),1)
        self.assertEqual(sum('Romilton' in x['person'] for x in people),0)
    def test_institutional_revenue_not_counted_twice(self):
        for r in self.r['rows']:
            if r['acceptedStudentCount']:
                from pe_real import money
                from decimal import Decimal
                self.assertEqual(r['netRevenueCents'],money(Decimal(r['postDiscountCents'])*Decimal('.955')))
    def test_cost_without_source_never_confirmed(self):
        self.assertTrue(all(r['status']!='COMPROVADO' for r in self.r['rows']))
        for r in self.r['rows']:
            if r['consideredCostCents'] is None:self.assertIsNone(r['pe'])
    def test_materiality_has_unknown_limit_not_fake_zero(self):
        x=next(x for x in self.d['bounds'] if x['name']=='8º C')
        self.assertIsNone(x['maximumIncrement'])
    def test_negative_upload_length_rejected(self):
        h=object.__new__(Handler);h.headers={'Content-Length':'-1'};h.rfile=io.BytesIO(b'{}')
        with self.assertRaises(ValueError):h.body()
    def test_packaged_runtime_without_ignored_output(self):
        with tempfile.TemporaryDirectory() as tmp,patch('pe_real.AUDIT',Path(tmp)):
            r=load_report()
        self.assertTrue(r['packagedRuntime']);self.assertEqual([x['pe'] for x in r['rows'][:2]],[14,14])
        self.assertNotIn('historicalPayroll',r['costReconciliation']);self.assertNotIn('sanitation',r)
    def test_cloud_adapter_uses_store_without_network(self):
        from cloud_runtime import CloudHandler
        records=json.loads((AUDIT/'registros-saneados-locais.json').read_text(encoding='utf-8'))
        s=import_benefits(apply_snapshot_to_state(blank()),records)
        h=object.__new__(CloudHandler);h.path='/api/break-even/real?year=2027'
        h._cloud_store=SimpleNamespace(state=lambda:(s,2));h.current=lambda:{'isAdmin':True,'active':True};h.respond=lambda status,data:(status,data)
        with tempfile.TemporaryDirectory() as tmp,patch('pe_real.AUDIT',Path(tmp)):
            code,d=h.do_GET();self.assertEqual(code,200,d);self.assertEqual(d['rows'][0]['pe'],14)
            s['benefits']=[];code,d=h.do_GET();self.assertEqual(code,409,d)
    def test_backup_restores_only_to_new_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();(root/'data').mkdir()
            with closing(sqlite3.connect(root/'data/caj.sqlite3')) as db:
                db.execute('CREATE TABLE state(payload TEXT)');db.execute('INSERT INTO state VALUES(?)',(json.dumps({'benefits':[{'id':'fixture'}]}),));db.commit()
            (root/'pe_real_2027_snapshot.json').write_text('{"pe":14}')
            archive=Path(tmp)/'backup.zip';build_backup(archive,root=root)
            restore_new(archive,Path(tmp)/'restored')
            self.assertEqual((Path(tmp)/'restored/pe_real_2027_snapshot.json').read_text(),'{"pe":14}')
            with self.assertRaises(ValueError):restore_new(archive,root)
            with self.assertRaises(ValueError):build_backup(archive,root=root)

if __name__=='__main__':unittest.main()
