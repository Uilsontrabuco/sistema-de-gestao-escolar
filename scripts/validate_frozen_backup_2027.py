"""Retoma restauração local validando cada arquivo; suporta caminhos longos Windows."""
import hashlib
import json
import os
import sqlite3
import stat
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/PE-2027-FECHAMENTO-TECNICO-APROVADO-2026-09-22'

def native(path):
    absolute=str(path.resolve())
    return Path('\\\\?\\'+absolute) if os.name=='nt' else path

def sha(path):
    return hashlib.sha256(native(path).read_bytes()).hexdigest()

def emit(path,value):
    with path.open('x',encoding='utf-8') as f:
        f.write(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def main():
    checkpoint=json.loads((OUT/'CHECKPOINT.json').read_text(encoding='utf-8'))
    archive_path=ROOT/checkpoint['backupRelativePath']
    restored=ROOT/checkpoint['restorationRelativePath']
    if not restored.resolve().is_relative_to(OUT.resolve()):raise ValueError('Destino fora da pasta de validação')
    db=ROOT/'data/caj.sqlite3'
    db_hash=sha(db)
    assert db_hash==checkpoint['localDatabaseHash']
    with ZipFile(archive_path) as z:
        assert z.testzip() is None
        manifest=json.loads(z.read('BACKUP-MANIFEST.json'))
        for name in z.namelist():
            target=restored/name
            if not target.resolve().is_relative_to(restored.resolve()):raise ValueError('Caminho fora da restauração')
            data=z.read(name)
            extended=native(target)
            extended.parent.mkdir(parents=True,exist_ok=True)
            if extended.exists():
                if extended.read_bytes()!=data:raise ValueError('Arquivo já restaurado diverge: '+name)
            else:
                with extended.open('xb') as f:f.write(data)
        for name,digest in manifest['files'].items():
            assert sha(restored/name)==digest,name
            if name!='data/caj.sqlite3':assert sha(ROOT/name)==digest,name
    before=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)
    after=sqlite3.connect((restored/'data/caj.sqlite3').as_uri()+'?mode=ro',uri=True)
    assert after.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert list(before.iterdump())==list(after.iterdump())
    before.close();after.close()
    snapshot=OUT/'snapshot-41-turmas.json'
    assert sha(snapshot)==sha(restored/snapshot.relative_to(ROOT))
    assert sha(db)==db_hash
    for name,digest in checkpoint['snapshotHashes'].items():assert sha(OUT/name)==digest
    for name in ['snapshot-41-turmas.json','snapshot-41-turmas.csv','snapshot-41-turmas.md','MANIFESTO-SNAPSHOT.json']:
        (OUT/name).chmod(stat.S_IREAD)
    result=dict(checkpointId=checkpoint['id'],verifiedAt=datetime.now().astimezone().isoformat(),
        backupCreated=True,backupRestorable=True,currentDatabaseUnchanged=True,
        path=str(archive_path),sha256=sha(archive_path),filesRestored=len(manifest['files']),
        restoreDirectory=str(restored),allFileHashesMatch=True,sqliteIntegrity='ok',sameLogicalDatabase=True,
        snapshotRecords=41,snapshotIdentical=True,noPERerun=True,
        previousBackupsOverwritten=False,remoteAccess=False,deploy=False,push=False,
        longPathsUsed=True,operationalStateHash=db_hash)
    emit(OUT/'VALIDACAO-BACKUP-FINAL.json',result)
    emit(OUT/'BACKUP-FINAL.sha256',result['sha256']+'  '+archive_path.name+'\n')
    emit(OUT/'VALIDACAO-BACKUP-FINAL.md','\n'.join(['# Validação do backup final','',
        '**BACKUP FINAL CRIADO**','**BACKUP RESTAURÁVEL VALIDADO**','**BASE ATUAL NÃO ALTERADA**','',
        f'Arquivo: {archive_path}',f'SHA-256: {result["sha256"]}',f'Restauração isolada: {restored}',
        f'{result["filesRestored"]} arquivos restaurados e conferidos por hash; SQLite íntegro e conteúdo lógico igual à base atual; snapshot de 41 registros idêntico.',
        'A primeira extração encontrou o limite de comprimento de caminhos do Windows. A validação foi retomada com prefixo de caminhos longos; os arquivos existentes foram comparados antes de prosseguir, sem sobrescrever divergências. ZIP original preservado.',
        'Nenhum cálculo de PE foi executado. Todos os arquivos de origem incluídos mantiveram hash; backup anterior preservado.',
        'Código, estado operacional, testes, evidências e snapshot incluídos. Caches/runtime instalado, recovery histórico, Git, credenciais .env e backups anteriores excluídos e preservados no local original. Runtimes/requirements constam do manifesto; não foi lida credencial.',
        'Este é um backup local; realizar novo backup do ambiente alvo imediatamente antes de publicação futura autorizada. Recibos de validação e ferramenta de retomada foram criados após o ZIP e permanecem externos ao arquivo que validam.',
        'O snapshot está somente leitura e protegido por manifesto SHA-256; imutabilidade local detectável, não WORM externo.'])+'\n')
    emit(OUT/'ARQUIVOS-GERADOS.md','\n'.join(['# Arquivos gerados','']+[
        '- '+str(p.relative_to(ROOT)) for p in sorted(OUT.iterdir()) if p.is_file()]+[
        '- '+str(archive_path.relative_to(ROOT)),'- '+str(restored.relative_to(ROOT))+' / árvore restaurada completa',
        '- scripts/freeze_pe_2027_checkpoint.py','- scripts/verify_pe_publication_snapshot.py',
        '- scripts/validate_frozen_backup_2027.py'])+'\n')
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__':main()
