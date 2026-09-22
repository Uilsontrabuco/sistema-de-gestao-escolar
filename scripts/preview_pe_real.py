"""Verificação local com fotografia 775 em banco descartável; não usa usuários reais."""
import sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import serve
from enrollment_2027 import apply_snapshot_to_state

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='pe-real-fixture-') as directory:
        app=serve(Path(directory)/'fixture.sqlite3',port=8877)
        app.store.create_user('Verificação local','pe-preview@fixture.invalid','Fixture-only-2027',is_admin=True)
        with app.store.db() as db:
            state,version=app.store.state(db)
            from benefits_2027 import import_benefits
            from pe_real import AUDIT
            records=json.loads((AUDIT/'registros-saneados-locais.json').read_text(encoding='utf-8'))
            db.execute('UPDATE state SET payload=? WHERE id=1',(json.dumps(import_benefits(apply_snapshot_to_state(state),records)),))
        print('Prévia isolada 775: http://127.0.0.1:8877',flush=True)
        try:app.serve_forever()
        finally:app.server_close()
