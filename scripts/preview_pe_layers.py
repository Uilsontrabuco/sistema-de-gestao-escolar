"""Prévia isolada em banco temporário, sem dados reais ou persistência escolar."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import serve

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='pe-layers-fixture-') as directory:
        server=serve(Path(directory)/'fixture.sqlite3',port=8877)
        server.store.create_user('Verificação local','pe-preview@fixture.invalid','Fixture-only-2027',is_admin=True)
        print('Prévia isolada: http://127.0.0.1:8877',flush=True)
        try:server.serve_forever()
        finally:server.server_close()
