"""Servidor exclusivamente de QA: banco temporário, removido ao encerrar.
Nunca usa data/caj.sqlite3. Credenciais de fixture são somente para localhost:8877.
"""
import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import serve
with tempfile.TemporaryDirectory(prefix='caj-visual-') as directory:
    app=serve(Path(directory)/'qa.sqlite3',port=8877)
    app.store.create_user('Administrador de teste isolado','qa@fixture.invalid','Teste-isolado-2026!',is_admin=True)
    try:app.serve_forever()
    except KeyboardInterrupt:pass
    finally:app.server_close()
