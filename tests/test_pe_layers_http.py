import tempfile,threading,unittest,json,http.cookiejar,urllib.request,urllib.error
from pathlib import Path
from server import serve


class LayersHttpTests(unittest.TestCase):
    def test_permission_read_only_and_static_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            server=serve(Path(directory)/'fixture.sqlite3',port=0)
            admin=server.store.create_user('Fixture','layers@fixture.invalid','Fixture-only-2027',is_admin=True)
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
            base='http://127.0.0.1:'+str(server.server_port)
            client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            try:
                with self.assertRaises(urllib.error.HTTPError):client.open(base+'/api/break-even/layers')
                client.open(urllib.request.Request(base+'/api/login',data=json.dumps(dict(email='layers@fixture.invalid',password='Fixture-only-2027')).encode(),headers={'Content-Type':'application/json'})).close()
                before=server.store.state()
                with client.open(base+'/api/break-even/layers?year=2027') as response:d=json.load(response)
                self.assertEqual(d['rows'][0]['documentary']['pe'],15)
                self.assertEqual(d['rows'][0]['provisional']['pe'],22)
                self.assertEqual(server.store.state(),before)
                with client.open(base+'/') as response:self.assertIn(b'pe_layers.js',response.read())
                with client.open(base+'/pe_layers.js') as response:self.assertEqual(response.status,200)
                with self.assertRaises(urllib.error.HTTPError):client.open(base+'/api/break-even/layers?year=2026')
                with self.assertRaises(urllib.error.HTTPError):client.open(base+'/pe_layers_2027_source.json')
                server.store.create_user('Sem financeiro','no-finance@fixture.invalid','Fixture-only-2027',{'classes':['view']},actor=admin)
                client.open(urllib.request.Request(base+'/api/login',data=json.dumps(dict(email='no-finance@fixture.invalid',password='Fixture-only-2027')).encode(),headers={'Content-Type':'application/json'})).close()
                with self.assertRaises(urllib.error.HTTPError) as denied:client.open(base+'/api/break-even/layers')
                self.assertEqual(denied.exception.code,401)
            finally:server.shutdown();server.server_close();t.join()


if __name__=='__main__':unittest.main()
