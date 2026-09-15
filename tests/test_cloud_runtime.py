import io
import json
import unittest
from unittest.mock import patch

import cloud_store
from cloud_runtime import CloudHandler


class CloudRuntimeTests(unittest.TestCase):
    def test_recovery_requires_verified_master_and_changes_only_password(self):
        from contextlib import nullcontext
        from unittest.mock import Mock
        store=object.__new__(cloud_store.CloudStore)
        db=Mock()
        master={'id':'fixture-id','active':True,'isAdmin':True,'deleted':False}
        with patch.object(store,'db',return_value=nullcontext(db)), patch.object(store,'users',return_value=[master]), patch.object(store,'auth_request',side_effect=[{'id':'fixture-id'},{}]) as auth:
            self.assertTrue(store.recover_master_password('fixture-token','fixture-password'))
            self.assertEqual(auth.call_args.kwargs,{'method':'PUT','user_token':'fixture-token'})
            self.assertEqual(auth.call_args.args,('user',{'password':'fixture-password'}))
            db.execute.assert_called_once_with('DELETE FROM sessions WHERE user_id=?',('fixture-id',))
        db.reset_mock()
        with patch.object(store,'db',return_value=nullcontext(db)), patch.object(store,'users',return_value=[master]), patch.object(store,'auth_request',return_value={'id':'another-id'}) as auth:
            with self.assertRaises(PermissionError):
                store.recover_master_password('fixture-token','fixture-password')
            self.assertEqual(auth.call_count,1)
            db.execute.assert_not_called()

    def test_pooler_only_routes_the_verified_official_direct_host(self):
        options = cloud_store.connection_options(f'postgresql://postgres@db.{cloud_store.PROJECT}.supabase.co:5432/postgres')
        self.assertEqual(options['user'], f'postgres.{cloud_store.PROJECT}')
        self.assertEqual(options['port'], 6543)
        self.assertNotIn('password', options)
        self.assertEqual(cloud_store.connection_options('postgresql://postgres@db.other.supabase.co/postgres'), {})

    def test_direct_configuration_never_mixes_marketplace_credentials(self):
        env = {'SEVEN7_DATABASE_URL':'postgres://example/db',
               'SEVEN7_SUPABASE_SECRET_KEY':'official-fixture',
               'SUPABASE_SECRET_KEY':'other-fixture',
               'SUPABASE_URL':'https://wrong.supabase.co'}
        self.assertEqual(cloud_store.configuration(env),
                         ('postgres://example/db', f'https://{cloud_store.PROJECT}.supabase.co', 'official-fixture'))
        del env['SEVEN7_SUPABASE_SECRET_KEY']
        with self.assertRaises(RuntimeError):
            cloud_store.configuration(env)

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
