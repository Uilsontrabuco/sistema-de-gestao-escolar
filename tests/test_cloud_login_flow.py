"""HTTP/session integration with isolated fixture storage and simulated Auth.

Never connects to Supabase or creates production accounts/sessions.
"""
import contextlib
import hashlib
import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock
from cloud_store import CloudStore
from cloud_runtime import CloudHandler
from server import blank


class CloudLoginFlow(unittest.TestCase):
    def test_auth_response_to_persisted_session_cookie_profile_and_state(self):
        with tempfile.TemporaryDirectory() as folder:
            database=Path(folder)/'isolated.sqlite'
            profiles=Path(folder)/'profiles.sqlite'
            @contextlib.contextmanager
            def db():
                connection=sqlite3.connect(database)
                connection.row_factory=sqlite3.Row
                connection.execute('ATTACH DATABASE ? AS public',(str(profiles),))
                try:
                    yield connection
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
                finally:
                    connection.close()
            with db() as connection:
                connection.executescript('''
                CREATE TABLE public.profiles(id TEXT, nome TEXT,email TEXT,role TEXT,ativo INTEGER);
                CREATE TABLE user_permissions(id TEXT,payload TEXT);
                CREATE TABLE sessions(token TEXT PRIMARY KEY,user_id TEXT,csrf TEXT,expires REAL);
                CREATE TABLE failures(key TEXT PRIMARY KEY,count INTEGER,last REAL);
                CREATE TABLE audit(id INTEGER PRIMARY KEY,payload TEXT);
                CREATE TABLE state(id INTEGER PRIMARY KEY,version INTEGER,payload TEXT);
                CREATE TABLE outbox(id TEXT,payload TEXT);
                ''')
                connection.execute('INSERT INTO public.profiles VALUES(?,?,?,?,?)',('fixture-id','Fixture','fixture@example.invalid','master',1))
                state=blank()
                state['classes']=[{'id':str(i),'name':f'Fixture {i}','students':25 if i==0 else 15,'capacity':30} for i in range(41)]
                connection.execute('INSERT INTO state VALUES(1,1,?)',(json.dumps(state),))
                connection.execute('INSERT INTO audit(payload) VALUES(?)',(json.dumps({'id':'legacy-audit-id','action':'edit','field':'fixture'}),))
            store=object.__new__(CloudStore)
            store.db=db
            store.auth_request=Mock(return_value={'user':{'id':'fixture-id'},'expires_in':3600})
            class Handler(CloudHandler):
                @property
                def store(self):
                    return store
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            try:
                client=http.client.HTTPConnection(*server.server_address)
                client.request('POST','/api/login',json.dumps({'email':'fixture@example.invalid','password':'fixture-only'}),{'Content-Type':'application/json'})
                response=client.getresponse()
                self.assertEqual(response.status,200)
                payload=json.loads(response.read())
                cookie=SimpleCookie(response.getheader('Set-Cookie'))['caj_session']
                self.assertTrue(cookie['secure'])
                self.assertTrue(cookie['httponly'])
                self.assertEqual(cookie['samesite'],'Strict')
                self.assertEqual(cookie['path'],'/')
                self.assertEqual(cookie['domain'],'')
                self.assertTrue(payload['user']['isAdmin'])
                with db() as connection:
                    row=connection.execute('SELECT * FROM sessions').fetchone()
                    self.assertEqual(row['token'],hashlib.sha256(cookie.value.encode()).hexdigest())
                # A fresh HTTP connection reproduces reading persisted session state.
                client.close()
                for endpoint in ('/api/me','/api/state','/api/state'):
                    client=http.client.HTTPConnection(*server.server_address)
                    client.request('GET',endpoint,headers={'Cookie':'caj_session='+cookie.value})
                    response=client.getresponse()
                    self.assertEqual(response.status,200)
                    result=json.loads(response.read())
                    self.assertTrue(result['user']['isAdmin'])
                    if endpoint=='/api/state':
                        self.assertEqual(len(result['state']['classes']),41)
                        self.assertEqual(sum(c['students'] for c in result['state']['classes']),625)
                    client.close()
                store.auth_request.assert_called_once()
                with db() as connection:
                    original=connection.execute('SELECT payload FROM audit WHERE id=1').fetchone()
                    self.assertEqual(json.loads(original['payload'])['id'],'legacy-audit-id')
            finally:
                server.shutdown()
                server.server_close()
                worker.join()
