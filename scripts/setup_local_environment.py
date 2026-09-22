"""Ambiente offline: requirements.txt + instalações já existentes nesta máquina."""
import hashlib
import json
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ENV=ROOT/'.venv'
SOURCE=ROOT/'tmp/python-cloud'

def main():
    if not (ENV/'pyvenv.cfg').exists():
        if ENV.exists():raise RuntimeError('.venv existente sem pyvenv.cfg; não sobrescrever')
        venv.EnvBuilder(with_pip=True,system_site_packages=True).create(ENV)
    python=ENV/'Scripts/python.exe'
    site=ENV/'Lib/site-packages'
    manifest={}
    # Artefatos locais usados anteriormente no projeto, sem pip/rede/download.
    for name in ['psycopg','psycopg_binary','psycopg_binary.libs','psycopg-3.2.10.dist-info','psycopg_binary-3.2.10.dist-info','tzdata','tzdata-2026.4.dist-info']:
        source=SOURCE/name
        if not source.is_dir():raise RuntimeError('Dependência offline ausente: '+name)
        target=site/name
        if not target.exists():shutil.copytree(source,target)
        for p in source.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
                raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest()
                q=target/p.relative_to(source)
                if q.read_bytes()!=raw:raise RuntimeError('Artefato local diverge: '+str(q))
                manifest[str(p.relative_to(SOURCE))]=h
    out=ROOT/'.local-dependencies';out.mkdir(exist_ok=True)
    (out/'offline-source-hashes.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    code='import psycopg,reportlab,pypdf,pdfplumber,openpyxl,PIL; print("Dependencias importadas offline; psycopg="+psycopg.__version__)'
    subprocess.run([str(python),'-c',code],check=True,cwd=ROOT)
    print('Ambiente local pronto; requisitos serão conferidos pelo build_local.py.')

if __name__=='__main__':main()
