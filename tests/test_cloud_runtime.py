import io
import json
import unittest
from unittest.mock import patch

import cloud_store
from cloud_runtime import CloudHandler


class CloudRuntimeTests(unittest.TestCase):
    def test_missing_configuration_never_uses_local_database(self):
        with self.assertRaisesRegex(RuntimeError, 'não configurada'):
            cloud_store.configuration({})

    def test_wrong_supabase_project_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'diferente'):
            cloud_store.configuration({'POSTGRES_URL':'postgres://example/db',
                'SUPABASE_SECRET_KEY':'fixture-only', 'SUPABASE_URL':'https://wrong.supabase.co'})

    def test_bad_dsn_does_not_leak_value(self):
        with self.assertRaises(RuntimeError) as raised:
            cloud_store.configuration({'POSTGRES_URL':'sensitive-invalid-value', 'SUPABASE_SECRET_KEY':'fixture-only'})
        self.assertNotIn('sensitive', str(raised.exception))

    def test_configuration_accepts_existing_names(self):
        dsn,url,key = cloud_store.configuration({'POSTGRES_URL':'postgres://example/db','SUPABASE_SECRET_KEY':'fixture-only'})
        self.assertEqual(url,'https://pvsdlqspxfbfeepylfxc.supabase.co')
        self.assertEqual(dsn,'postgres://example/db')

    def test_parameters_remain_bound(self):
        self.assertEqual(cloud_store.translate('SELECT * FROM sessions WHERE token=?'),
                         'SELECT * FROM sessions WHERE token=%s')

    def test_outbox_is_idempotent_without_replacement(self):
        query = cloud_store.translate('INSERT OR IGNORE INTO outbox VALUES(?,?)')
        self.assertIn('ON CONFLICT (id) DO NOTHING', query)
        self.assertNotIn('REPLACE', query)

    def test_unsupported_sql_is_rejected(self):
        with self.assertRaises(ValueError):
            cloud_store.translate('INSERT OR REPLACE INTO users VALUES(?,?,?)')

    def test_empty_session_never_connects(self):
        store = object.__new__(cloud_store.CloudStore)
        with patch.object(store, 'db', side_effect=AssertionError('unexpected connection')):
            self.assertEqual(store.session(''), (None,None))

    def test_auth_provider_error_does_not_leak_response(self):
        from urllib.error import HTTPError
        store = object.__new__(cloud_store.CloudStore)
        store.auth_url='https://example.invalid'
        store.auth_key='fixture-only'
        with patch('cloud_store.urlopen',side_effect=HTTPError('private-url',401,'private-token',{},None)):
            with self.assertRaises(PermissionError) as raised:
                store.auth_request('token', {'password':'fixture-only'})
        self.assertNotIn('private', str(raised.exception))

    def test_promotora_has_no_financial_or_admin_access(self):
        self.assertNotIn('financial', cloud_store.PROMOTORA)
        self.assertNotIn('users', cloud_store.PROMOTORA)
        self.assertIn('edit', cloud_store.PROMOTORA['enrollments'])

    def test_dashboard_does_not_grant_private_details(self):
        store=object.__new__(cloud_store.CloudStore)
        payload={'state':{'budget':[{'private':True}], 'imports':[1], 'recoveredLegacy':{'private':True}, 'benefits':[1], 'guardians':[1], 'breakEven':{}, 'revenuePlanning':{}, 'teachingLoad':{}},'version':1}
        with patch.object(cloud_store.Store,'snapshot',return_value=payload):
            result=store.snapshot({'id':'fixture','isAdmin':False,'access':{'dashboard':['view']}})
        self.assertEqual(result['state']['budget'],[])
        self.assertEqual(result['state']['recoveredLegacy'],{})

    def test_runtime_handler_blocks_initial_migration(self):
        handler=object.__new__(CloudHandler)
        handler.path='/api/migrate'
        with patch.object(handler,'respond') as respond:
            handler.do_POST()
        self.assertEqual(respond.call_args.args[0],403)


if __name__ == '__main__':
    unittest.main()
