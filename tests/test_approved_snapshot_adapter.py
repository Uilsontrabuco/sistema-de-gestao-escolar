import hashlib
import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
import approved_pe_snapshot as adapter
from server import serve

class ApprovedSnapshotTests(unittest.TestCase):
    def test_identical_to_frozen_source(self):
        root=Path(__file__).resolve().parents[1]
        frozen=root/'output/PE-2027-FECHAMENTO-TECNICO-APROVADO-2026-09-22/snapshot-41-turmas.json'
        self.assertEqual(adapter.SNAPSHOT_FILE.read_bytes(),frozen.read_bytes())
        self.assertEqual(adapter.load_approved_snapshot(),json.loads(frozen.read_text(encoding='utf-8')))

    def test_missing_and_tampered_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'snapshot.json'
            with patch.object(adapter,'SNAPSHOT_FILE',path):
                with self.assertRaises(FileNotFoundError):adapter.load_approved_snapshot()
                path.write_text('{}')
                with self.assertRaises(adapter.SnapshotIntegrityError):adapter.load_approved_snapshot()

    def test_no_mutation_or_financial_calculation(self):
        with patch('pe_real.ceil_ratio',side_effect=AssertionError('Recalculo proibido')),patch('pe_final_2027.final_view',side_effect=AssertionError('Recalculo proibido')):
            result=adapter.load_approved_snapshot()
            result['rows'][0]['peAlunos']=0
            self.assertEqual(adapter.load_approved_snapshot()['rows'][0]['peAlunos'],17)

    def test_integrity_and_negative_margins(self):
        s=adapter.load_approved_snapshot();r=s['rows']
        self.assertEqual(sum(x['custoTotalCentavos'] for x in r),60564103)
        self.assertEqual(sum(x['capacidade'] for x in r),1103)
        self.assertEqual(sum(x['matriculados'] for x in r),775)
        self.assertEqual(sum(x['vagas'] for x in r),328)
        self.assertEqual(sum(x['margemFisica']<0 for x in r),11)
        self.assertEqual(s['reserveCents'],1582705)

    def test_authenticated_endpoint_is_private_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            server=serve(Path(directory)/'fixture.sqlite3',port=0)
            admin=server.store.create_user('Fixture','snapshot@fixture.invalid','Fixture-only-2027',is_admin=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(server.server_port)
            client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            try:
                with self.assertRaises(urllib.error.HTTPError):client.open(base+'/api/break-even/approved')
                client.open(urllib.request.Request(base+'/api/login',data=json.dumps(dict(email='snapshot@fixture.invalid',password='Fixture-only-2027')).encode(),headers={'Content-Type':'application/json'})).close()
                before=server.store.state()
                with patch('pe_real.load_report',side_effect=AssertionError('Motor antigo chamado')):
                    with client.open(base+'/api/break-even/approved?year=2027') as response:s=json.load(response)
                self.assertEqual(s['rows'],adapter.load_approved_snapshot()['rows'])
                self.assertEqual(server.store.state(),before)
                with self.assertRaises(urllib.error.HTTPError):client.open(base+'/approved_pe_2027_snapshot.json')
                with self.assertRaises(urllib.error.HTTPError):client.open(base+'/api/break-even/approved?year=2026')
                with patch.object(adapter,'SNAPSHOT_SHA256','0'*64):
                    with self.assertRaises(urllib.error.HTTPError) as error:client.open(base+'/api/break-even/approved')
                    self.assertEqual(error.exception.code,409)
                server.store.create_user('Sem financeiro','snapshot-no@fixture.invalid','Fixture-only-2027',{'classes':['view']},actor=admin)
                client.open(urllib.request.Request(base+'/api/login',data=json.dumps(dict(email='snapshot-no@fixture.invalid',password='Fixture-only-2027')).encode(),headers={'Content-Type':'application/json'})).close()
                with self.assertRaises(urllib.error.HTTPError):client.open(base+'/api/break-even/approved')
            finally:server.shutdown();server.server_close();thread.join()
