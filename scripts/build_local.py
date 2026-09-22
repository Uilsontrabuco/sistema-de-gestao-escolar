"""Build offline do pacote Python: valida requisitos e entrada sem conexão remota."""
import ast
import hashlib
import importlib.metadata as metadata
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
try:
    from packaging.requirements import Requirement
except ImportError:
    # O venv offline inclui pip/ensurepip; apenas o verificador de build usa
    # seu parser de requisitos, sem adicionar dependência à aplicação.
    from pip._vendor.packaging.requirements import Requirement

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    requirements=(ROOT/'requirements.txt').read_text().splitlines()
    versions={}
    for text in requirements:
        if not text.strip() or text.lstrip().startswith('#'):continue
        req=Requirement(text);version=metadata.version(req.name)
        if version not in req.specifier:raise RuntimeError(f'{req.name}: {version} fora de {req.specifier}')
        versions[req.name]=version
    resolved={}
    pending=[Requirement(t) for t in requirements if t.strip() and not t.lstrip().startswith('#')]
    visited=set()
    while pending:
        req=pending.pop()
        key=(req.name.lower().replace('_','-'),tuple(sorted(req.extras)))
        if key in visited:continue
        visited.add(key)
        version=metadata.version(req.name)
        if version not in req.specifier:raise RuntimeError('Dependência transitiva incompatível: '+str(req))
        resolved[key[0]]=version
        for text in metadata.requires(req.name) or []:
            dependency=Requirement(text)
            if dependency.marker is None or any(dependency.marker.evaluate({'extra':extra}) for extra in (set(req.extras)|{''})):
                pending.append(dependency)
    pinned=ROOT/'requirements-local.lock'
    if pinned.exists():
        for text in pinned.read_text().splitlines():
            if not text.strip() or text.lstrip().startswith('#'):continue
            req=Requirement(text)
            if metadata.version(req.name) not in req.specifier:raise RuntimeError('Ambiente diverge do lock local: '+req.name)
    import psycopg
    if psycopg.__version__!='3.2.10':raise RuntimeError('Versão psycopg divergente')
    from approved_pe_snapshot import load_approved_snapshot,SNAPSHOT_SHA256
    data=load_approved_snapshot()
    stamp=datetime.now().strftime('%Y%m%dT%H%M%S%f')
    out=ROOT/'.local-build'/stamp;app=out/'app';app.mkdir(parents=True)
    # Git's public file set excludes preserved private originals, even if they
    # remain beside the source tree. Never package using root-level globs.
    public=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    files=[ROOT/name for name in sorted(set(public)) if name and
           not name.startswith(('tests/','supabase-port/')) and
           (Path(name).suffix in ('.py','.js','.css','.html','.json') or name in ('requirements.txt','requirements-local.lock'))]
    manifest={}
    for p in files:
        rel=p.relative_to(ROOT);target=app/rel;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(p.read_bytes());manifest[rel.as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
        if p.suffix=='.py':compile(p.read_bytes(),str(rel),'exec')
    # Importação da função empacotada; chamadas de rede tornam o build inválido.
    verify='''import socket
def blocked(*a,**k): raise RuntimeError("Rede proibida no build local")
socket.socket.connect=blocked
socket.create_connection=blocked
from api.index import handler
from approved_pe_snapshot import load_approved_snapshot
try:
 load_approved_snapshot()
except FileNotFoundError:
 pass
else:
 raise AssertionError("Artefato privado incluído indevidamente no build público")
print("Entrada serverless importada; dados privados ausentes do pacote público")
'''
    subprocess.run([sys.executable,'-c',verify],cwd=app,check=True)
    report=dict(mode='BUILD_LOCAL_OFFLINE_PYTHON',runtime=sys.version,requirements=versions,
        psycopgBinaryVersion=metadata.version('psycopg-binary'),resolvedDependencies=resolved,appFiles=manifest,
        snapshotSha256=SNAPSHOT_SHA256,classes=41,remoteAccess=False,databaseConnection=False,
        vercelCLIExecuted=False,artifact=str(app))
    (out/'build-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lock='# Ambiente local Windows / Python 3.13; requisitos oficiais em requirements.txt.\n'+'\n'.join(f'{k}=={v}' for k,v in sorted(resolved.items()))+'\n'
    (out/'requirements-resolved.txt').write_text(lock,encoding='utf-8')
    (ROOT/'.local-build/LATEST.txt').write_text(str(out),encoding='utf-8')
    print(json.dumps(dict(build='OK',artifact=str(out),classes=len(data['rows']),requirements=versions)))

if __name__=='__main__':main()
