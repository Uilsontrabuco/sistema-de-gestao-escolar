import copy
import hashlib
import json
import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import private_runtime_import as runtime


class FakeDB:
    def __init__(self, conn): self.conn = conn
    def execute(self, sql, params=()): return self.conn.execute(sql.replace(' FOR UPDATE',''), params)


class Store:
    def __init__(self, state):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('CREATE TABLE state(id INTEGER,version INTEGER,payload TEXT);CREATE TABLE assets(id TEXT PRIMARY KEY,content BLOB);CREATE TABLE audit(payload TEXT);')
        self.conn.execute('INSERT INTO state VALUES(1,4,?)',(json.dumps(state),)); self.conn.commit()
    @contextmanager
    def db(self):
        with self.conn: yield FakeDB(self.conn)
    def state(self): return json.loads(self.conn.execute('SELECT payload FROM state').fetchone()[0])


class PrivateRuntimeImportTests(unittest.TestCase):
    def setUp(self):
        self.state={'classes':[dict(id='c'+str(i),name='Synthetic '+str(i),capacity=1103 if i==0 else 0,students=775 if i==0 else 0) for i in range(41)],
                    'enrollments':{'new':37,'re':738,'history':[],'students':[]},'benefits':[],
                    'academicDataYear':2027,'breakEven':{'frozen':'synthetic-unchanged'},'academicYears':[]}
        self.source=[dict(id='planned-fixture',sourceKind='planned-2027',year=2027,studentKey='SYNTHETIC STUDENT',studentId='synthetic-id',
                         studentName='Synthetic student',name='Synthetic discount',classId='c0',sourceClass='c0',rate='0.45',grossCents=10000,discountCents=4500,postDiscountCents=5500)]
        raw=json.dumps(self.source);self.body={'artifacts':{'benefits-source.json':raw},'expectedVersion':4}
        self.patcher=patch.object(runtime,'ARTIFACT_SHA256',{'benefits-source.json':hashlib.sha256(raw.encode()).hexdigest()});self.patcher.start();self.addCleanup(self.patcher.stop)
        self.store=Store(self.state);self.addCleanup(self.store.conn.close);self.actor={'active':True,'isAdmin':True}

    def test_preview_is_read_only_and_does_not_activate_aggregate_students(self):
        report=runtime.process_import(self.store,self.body,self.actor)
        self.assertEqual((report['source'],report['inserted'],report['active'],report['waiting']),(1,1,0,1))
        self.assertEqual(self.store.state(),self.state)
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM assets').fetchone()[0],0)

    def test_apply_is_idempotent_and_preserves_academics_and_rollback(self):
        first=runtime.process_import(self.store,self.body,self.actor,True)
        after=self.store.state()
        self.assertEqual({k:v for k,v in after.items() if k!='benefits'},{k:v for k,v in self.state.items() if k!='benefits'})
        backup=json.loads(self.store.conn.execute('SELECT content FROM assets WHERE id=?',(runtime.ROLLBACK_ID,)).fetchone()[0])
        self.assertEqual(backup['benefits'],[])
        second=runtime.process_import(self.store,{**self.body,'expectedVersion':first['version']},self.actor,True)
        self.assertEqual(second['inserted'],0);self.assertEqual(second['version'],first['version']);self.assertEqual(self.store.state(),after)

    def test_tampered_and_stale_inputs_cannot_write(self):
        for body in ({**self.body,'artifacts':{'benefits-source.json':'[]'}},{**self.body,'expectedVersion':3}):
            with self.assertRaises(ValueError):runtime.process_import(self.store,body,self.actor,True)
            self.assertEqual(self.store.state(),self.state)
            self.assertEqual(self.store.conn.execute('SELECT count(*) FROM assets').fetchone()[0],0)

    def test_non_admin_cannot_provision(self):
        with self.assertRaises(PermissionError):runtime.process_import(self.store,self.body,{'active':True,'isAdmin':False},True)

    def test_duplicate_source_id_cannot_be_applied(self):
        with self.assertRaises(ValueError):runtime.propose(self.state,self.source*2)

    def test_deterministic_nominal_link_activates_only_existing_student(self):
        state=copy.deepcopy(self.state)
        state['enrollments']['students']=[dict(id='enrollment-fixture',studentId='synthetic-id',studentName='Synthetic student',classId='c0',year=2027,status='active')]
        updated,report=runtime.propose(state,self.source)
        self.assertEqual(report['active'],1);self.assertEqual(updated['enrollments'],state['enrollments'])

if __name__=='__main__': unittest.main()
