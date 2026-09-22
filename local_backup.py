from contextlib import closing
"""Backup local completo, sem rede. Restauração só em diretório novo."""
import hashlib,json,sqlite3,tempfile,zipfile,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def build_backup(destination, database=None, root=ROOT):
    root=Path(root);database=Path(database or root/'data/caj.sqlite3');destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():raise ValueError('Backup existente não será sobrescrito')
    excluded={'.git','node_modules','.venv','tmp','recovery','.codex','.agents','.vercel','backups','__pycache__','pre-publicacao-2027'}
    manifest={}
    with tempfile.TemporaryDirectory() as tmp:
        snap=Path(tmp)/'caj.sqlite3'
        with closing(sqlite3.connect(f'file:{database.as_posix()}?mode=ro',uri=True)) as source,closing(sqlite3.connect(snap)) as target:
            source.backup(target)
            assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED) as z:
            def put(name,data):z.writestr(name,data);manifest[name]=hashlib.sha256(data).hexdigest()
            put('data/caj.sqlite3',snap.read_bytes())
            for base,dirs,files in os.walk(root):
                dirs[:]=[d for d in dirs if d not in excluded]
                for name in files:
                    p=Path(base)/name;rel=p.relative_to(root).as_posix()
                    if p.resolve()==destination.resolve() or name.startswith('.env') or p.suffix.lower() in ('.sqlite3','.sqlite','.db','.zip','.pyc','.log'):continue
                    if p.suffix.lower() in ('.py','.js','.cjs','.json','.md','.txt','.html','.css','.sql','.png','.pdf'):
                        put(rel,p.read_bytes())
            put('BACKUP-MANIFEST.json',json.dumps(manifest,indent=2).encode())
    return dict(path=str(destination),files=len(manifest),sha256=hashlib.sha256(destination.read_bytes()).hexdigest())

def restore_new(archive,destination):
    target=Path(destination)
    if target.exists():raise ValueError('Restauração exige diretório inexistente; base principal protegida')
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read('BACKUP-MANIFEST.json'))
        for name,digest in manifest.items():
            out=(target/name).resolve()
            if not out.is_relative_to(target.resolve()):raise ValueError('Caminho inválido no backup')
            if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise ValueError('Hash divergente')
        target.mkdir(parents=True)
        for name in manifest:
            out=target/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(name))
    with closing(sqlite3.connect(f'file:{(target/"data/caj.sqlite3").as_posix()}?mode=ro',uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Banco inválido')
    return manifest

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('destination');a=p.parse_args()
    print(json.dumps(build_backup(a.destination)))
