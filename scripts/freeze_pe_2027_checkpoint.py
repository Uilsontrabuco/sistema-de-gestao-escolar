"""Congela resultados já calculados; cria/restaura backup sem recalcular PE."""
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import sys
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_pe_publication_snapshot import validate, self_test
ID='PE-2027-FECHAMENTO-TECNICO-APROVADO-2026-09-22'
OUT=ROOT/'output'/ID
SOURCE=ROOT/'output/fechamento-definitivo-administrativo-2027/fechamento.json'
DB=ROOT/'data/caj.sqlite3'
APPROVAL=Path('C:/Users/Uilson Trabuco/.codex/attachments/22684528-d580-433a-8223-8e70854da4e1/Texto colado.txt')

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def emit(path,value):
    with path.open('x',encoding='utf-8') as f:
        f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n' if not isinstance(value,str) else value)

def br(c):return f'{c/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')

def main():
    OUT.mkdir(exist_ok=True)
    now=datetime.now().astimezone();stamp=now.strftime('%Y%m%dT%H%M%S')
    frozen_path=OUT/'snapshot-41-turmas.json'
    if frozen_path.exists():raise RuntimeError('Checkpoint existente: não sobrescrever ou regerar')
    source_before=sha(SOURCE);db_before=sha(DB)
    approved=json.loads(SOURCE.read_text(encoding='utf-8'))
    assert approved['schoolAfterCents']==60564103 and approved['differenceCents']==0
    assert approved['reserveCents']==1582705 and all(approved['tests'].values())
    stored={r['id']:r for r in approved['rows']}
    rows=[]
    for d in approved['details']:
        r=stored[d['id']]
        rows.append(dict(id=r['id'],turma=r['name'],capacidade=r['capacity'],matriculados=r['enrolled'],
            novos=r['newStudents'],rematriculas=r['reenrolled'],vagas=r['vacancies'],mensalidadeCentavos=r['tuitionCents'],
            ticketLiquidoCentavosExato=d['ticketExactCents'],docenteCentavos=d['teacherCents'],
            diretosExclusivosCentavos=d['exclusiveCents'],rateioSerieNovoCentavos=0,rateioSegmentoCentavos=d['segmentCents'],
            coberturaAnteriorMantidaCentavos=d['inheritedCoverageCents'],folhaGlobalCentavos=d['globalAllocation']['folha'],
            apoioGlobalCentavos=d['globalAllocation']['apoio'],geraisGlobalCentavos=d['globalAllocation']['gerais'],
            custoTotalCentavos=r['consideredCostCents'],peAlunos=r['pe'],pePercentualCapacidade=r['percentCapacity'],
            margemFisica=r['physicalMargin'],situacao='PE superior à capacidade' if r['physicallyInfeasible'] else 'Dentro da capacidade'))
    snapshot=dict(checkpointId=ID,closedAt=now.isoformat(),year=2027,status='GO TÉCNICO — AGUARDANDO PUBLICAÇÃO',
        costTotalCents=60564103,reserveCents=1582705,reserveIncludedInClassCost=False,
        sourceSha256=source_before,noRecalculation=True,rows=rows)
    validate(snapshot,snapshot)
    validator_tests=self_test(snapshot)
    conn=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)
    conn.execute('PRAGMA query_only=ON')
    version,payload=conn.execute('SELECT version,payload FROM state WHERE id=1').fetchone()
    state=json.loads(payload)
    classes={c['id']:c for c in state['classes']}
    assert len(classes)==len(state['classes'])==41 and set(classes)==set(stored)
    mapping=[]
    for r in rows:
        c=classes[r['id']]
        assert (c['name'],c['capacity'],c['students'])==(r['turma'],r['capacidade'],r['matriculados'])
        mapping.append(dict(localId=r['id'],className=r['turma'],localStateId=c['id'],
            expectedMainBackendId=r['id'],remoteIdVerified=False,legacyPublicTurmasUuid=None,
            localMatch='EXATO',capacity=r['capacidade'],enrolled=r['matriculados']))
    logical_before=list(conn.iterdump())
    db_image=conn.serialize()
    conn.close()
    emit(frozen_path,snapshot)
    csv_path=OUT/'snapshot-41-turmas.csv'
    # Serialização estática dos mesmos 41 registros; nenhuma fórmula/workbook.
    with csv_path.open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';')
        writer.writeheader();writer.writerows(rows)
    with csv_path.open(encoding='utf-8-sig',newline='') as f:
        csv_rows=list(csv.DictReader(f,delimiter=';'))
    assert len(csv_rows)==41
    for source,export in zip(rows,csv_rows):
        assert all(str(v)==export[k] for k,v in source.items())
    lines=['# Snapshot final — 41 turmas','',f'Checkpoint: {ID}. Fechamento: {now.isoformat()}.',
        'Valores copiados do fechamento aprovado, sem execução de cálculo de PE. Campos monetários no JSON/CSV em centavos; ticket mantém precisão decimal original.', '',
        '| Turma | Capacidade | Matriculados | Mensalidade R$ | Ticket líquido R$ | Docente R$ | Diretos R$ | Segmento R$ | Cobertura anterior R$ | Folha global R$ | Apoio global R$ | Gerais global R$ | Custo total R$ | PE | PE % capacidade | Margem física | Situação |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['turma']} | {r['capacidade']} | {r['matriculados']} | {br(r['mensalidadeCentavos'])} | {br(float(r['ticketLiquidoCentavosExato']))} | {br(r['docenteCentavos'])} | {br(r['diretosExclusivosCentavos'])} | {br(r['rateioSegmentoCentavos'])} | {br(r['coberturaAnteriorMantidaCentavos'])} | {br(r['folhaGlobalCentavos'])} | {br(r['apoioGlobalCentavos'])} | {br(r['geraisGlobalCentavos'])} | {br(r['custoTotalCentavos'])} | {r['peAlunos']} | {r['pePercentualCapacidade']:.2f}% | {r['margemFisica']} | {r['situacao']} |")
    lines += ['', 'Rateio novo por série: zero em todas as linhas, conforme fechamento. Frações docentes compartilhadas já estão nas quotas docentes; não somar novamente. Reserva R$ 15.827,05 fora dos custos. Total das turmas R$ 605.641,03.', '',
        'Custo = docente + diretos exclusivos + segmento + cobertura anterior mantida + folha global + apoio global + gerais global. Essa conferência de soma não recalcula o PE.']
    emit(OUT/'snapshot-41-turmas.md','\n'.join(lines)+'\n')
    emit(OUT/'mapa-ids-41-turmas.json',dict(checkpointId=ID,localStateVersion=version,rows=mapping))
    emit(OUT/'APROVACAO-ENCERRAMENTO.txt',APPROVAL.read_text(encoding='utf-8'))
    emit(OUT/'APROVACAO-RATEIOS.txt',approved['administrativeApproval'])
    shutil.copyfile(SOURCE,OUT/'fechamento-aprovado-fonte.json')
    assumptions=['41 turmas, 775 matriculados, capacidade 1103, vagas líquidas 328.',
        '8º C existe com 20 matriculados; 1º D, 2º D e 3º D são turmas normais.',
        'Multiplicador docente 4,5; hora-aula e grade homologadas; frações compartilhadas sem duplicação.',
        'Maria Edna integral G4 B; demais custos nominais/exclusivos preservados.',
        'Lohana Auxiliar Administrativo, não docente; Marcelo integra a folha.',
        'Jailane, Veroneide e Paula ASG, 44h, salário-base R$ 1.690,50 cada, sem acréscimo duplicado.',
        'R$ 274,14 históricos do 8º C não são novo salário.',
        'G2 desconto previsto 12%, mensalidade R$ 930,69; inadimplência 4,5% uma vez. Demais benefícios/tickets preservados por linha.',
        '45% Marcando Vidas uma única vez; 50% bolsa filantropia; sem duplicar descontos.',
        'PCLD gerencial já neutralizada e inadimplência única; estimativa de descontos orçados não reinserida.',
        'A/B/C nominal/série/segmento antes dos residuais globais. Critérios específicos homologados preservados.',
        'Dos R$ 124.132,02: R$ 11.976,03 financiam nominais das quatro turmas dentro do envelope; R$ 112.155,99 globais por capacidade/1103, maiores restos por ID.',
        'R$ 15.827,05 antigo 7º C segregados; 7º A/B não recebem essa reserva.',
        'PEs superiores à capacidade preservados sem ajuste artificial.']
    critical=[ROOT/n for n in ['approved_residual_allocation_2027.py','administrative_pe_2027.py','pe_real.py','pe_final_2027.py',
        'server.py','cloud_store.py','teaching_cost.py','teaching_cost_snapshot.py','pe_layers_2027_source.json','benefits_2027.py',
        'personnel_confirmations_2027.py','vercel.json','supabase-port/supabase_schema.sql','supabase-port/review/FINAL-ESTRUTURA.sql']]
    critical.extend(sorted((ROOT/'output/fechamento-definitivo-administrativo-2027').glob('testes-*.txt')))
    snapshot_hashes={p.name:sha(p) for p in [frozen_path,csv_path,OUT/'snapshot-41-turmas.md']}
    backup_name=f'backup-pre-publicacao-pe-2027-{stamp}.zip'
    backup_path=OUT/'backups'/backup_name
    restored_path=OUT/f'restauracao-validacao-{stamp}'
    checkpoint=dict(id=ID,status='GO TÉCNICO — AGUARDANDO PUBLICAÇÃO',closedAt=now.isoformat(),
        tests=dict(python=420,javascriptEntries=92,sqlStatic=9,approved=True,source=approved['tests']),
        premises=assumptions,financialParameters=dict(teacherMonthlyFactor='4.5',delinquencyPercent='4.5',
            G2DiscountPercent='12',tuitionAndExactTickets='snapshot-41-turmas.json; copiar, não recalcular',
            capacityGlobal=1103,rounding='Maiores restos; desempate por ID'),
        residualTreatment=approved['bridges'],nominalTotalCents=approved['nominalTotalCents'],
        inheritedCoverageCents=approved['inheritedCoverageCents'],reservedCents=1582705,
        totals=dict(classes=41,capacity=1103,enrolled=775,vacancies=328,costCents=60564103,differenceCents=0),
        aboveCapacity=[r for r in rows if r['situacao']=='PE superior à capacidade'],
        finalPEs=[dict(id=r['id'],name=r['turma'],pe=r['peAlunos']) for r in rows],
        sourceHash=source_before,snapshotHashes=snapshot_hashes,criticalHashes={str(p.relative_to(ROOT)):sha(p) for p in critical},
        localDatabaseHash=db_before,localStateVersion=version,
        backupRelativePath=str(backup_path.relative_to(ROOT)),restorationRelativePath=str(restored_path.relative_to(ROOT)),
        verificationDocument='VALIDACAO-BACKUP-FINAL.json',remoteInspected=False,publicationExecuted=False)
    assert len(checkpoint['aboveCapacity'])==11
    emit(OUT/'CHECKPOINT.json',checkpoint)
    emit(OUT/'CHECKPOINT.md','\n'.join(['# '+ID,'','**GO TÉCNICO — AGUARDANDO PUBLICAÇÃO**','',
        'Data/hora: '+now.isoformat(),'', '41/41 PEs calculados; 1.103 capacidade; 775 matriculados; 328 vagas; R$ 605.641,03 reconciliados, diferença zero; reserva R$ 15.827,05 separada.', '',
        '## Premissas administrativas','']+['- '+s for s in assumptions]+['',
        '## Registros congelados','',
        'Os 41 PEs, custos exclusivos, quotas de segmento, globais, cobertura anterior e parâmetros por turma estão em snapshot-41-turmas.json/csv/md. A composição de origem está integralmente em fechamento-aprovado-fonte.json. As duas aprovações formais estão preservadas em arquivos TXT.',
        'CHECKPOINT.json registra hashes críticos, parâmetros, as 11 turmas acima da capacidade e os resultados dos testes. Snapshot em modo somente leitura, sem sobrescrita pelo gerador; manifesto SHA-256 detecta alterações. Isso é proteção local, não armazenamento WORM externo.', '',
        '## Backup e publicação','',f'Backup novo: backups/{backup_name}. Restauração isolada: {restored_path.name}. Comprovação posterior: VALIDACAO-BACKUP-FINAL.json.',
        'O backup desta etapa não substitui um novo backup imediatamente antes de uma publicação futura. Revalidar o estado remoto somente após autorização.',
        'Nenhum cálculo foi executado; nenhum banco operacional ou produção foi alterado. Nenhum acesso remoto, deploy ou push. Preparação em PLANO-PUBLICACAO-SEGURA-PE-2027.md.'])+'\n')
    emit(OUT/'PRE-VALIDACAO-LOCAL.json',dict(idsMatched=41,duplicateIds=0,duplicateNames=0,
        stateVersion=version,mainSchema='seven7_app.state(payload.classes): IDs textuais',
        legacySchema='public.turmas: UUID; sem equivalência remota comprovada',remoteVerification=False,
        existingEndpointUsesPriorCalculation=True,adapterRequiredBeforePublication=True,
        migrationsPrepared=False,migrationReason='Caminho recomendado: snapshot privado versionado no servidor; nenhuma alteração de schema necessária',
        comparatorTests=validator_tests,sourceDataUnchanged=True))
    # Manifesto dos artefatos congelados; não inclui o próprio manifesto.
    artifacts={p.name:sha(p) for p in OUT.iterdir() if p.is_file()}
    emit(OUT/'MANIFESTO-SNAPSHOT.json',dict(checkpointId=ID,createdAt=now.isoformat(),files=artifacts))
    # Backup integral do estado operacional e evidências locais; históricos
    # de recuperação, caches, credenciais e backups anteriores ficam fora.
    backup_path.parent.mkdir(exist_ok=True)
    exclude_dirs={'.git','.vercel','.venv','node_modules','__pycache__','tmp','recovery','.codex','.agents','backups'}
    exclusions=[];manifest={};source_hashes={}
    with ZipFile(backup_path,'x',ZIP_DEFLATED,compresslevel=6) as archive:
        for base,dirs,names in os.walk(ROOT):
            dirs[:]=[d for d in dirs if d not in exclude_dirs and not d.startswith('restauracao-validacao-')]
            for name in sorted(names):
                p=Path(base)/name;rel=p.relative_to(ROOT).as_posix()
                if name.startswith('.env') or p.suffix.lower() in ('.zip','.pyc') or name.endswith(('-wal','-shm')):
                    exclusions.append(rel);continue
                raw=db_image if p==DB else p.read_bytes()
                digest=hashlib.sha256(raw).hexdigest()
                archive.writestr(rel,raw);manifest[rel]=digest
                if p!=DB:source_hashes[rel]=digest
        manifest_data=dict(checkpointId=ID,createdAt=now.isoformat(),files=manifest,
            exclusions=dict(directories=sorted(exclude_dirs),files=exclusions,
                reason='Caches/dependências/históricos de recuperação e backups anteriores não são necessários ao retorno do estado operacional; credenciais permanecem fora e não foram lidas. Código, banco, evidências e snapshot incluídos.'),
            runtime=dict(python=sys.version,os=os.name),originalDatabaseHash=db_before)
        archive.writestr('BACKUP-MANIFEST.json',json.dumps(manifest_data,ensure_ascii=False,indent=2).encode('utf-8'))
    backup_hash=sha(backup_path)
    # Restauração de TODOS os arquivos em caminho novo, validado antes de extrair.
    resolved=restored_path.resolve()
    if restored_path.exists() or not resolved.is_relative_to(OUT.resolve()):raise RuntimeError('Destino de restauração inválido')
    with ZipFile(backup_path) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            target=(restored_path/name).resolve()
            if not target.is_relative_to(resolved):raise RuntimeError('Entrada de backup fora do destino')
        restored_path.mkdir()
        for name in archive.namelist():
            target=restored_path/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(archive.read(name))
    for name,digest in manifest.items():
        assert sha(restored_path/name)==digest
    restored_db=sqlite3.connect((restored_path/'data/caj.sqlite3').as_uri()+'?mode=ro',uri=True)
    assert restored_db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert list(restored_db.iterdump())==logical_before
    restored_db.close()
    restored_snapshot=json.loads((restored_path/frozen_path.relative_to(ROOT)).read_text(encoding='utf-8'))
    validate(snapshot,restored_snapshot)
    assert sha(DB)==db_before and sha(SOURCE)==source_before
    for name,digest in source_hashes.items():assert sha(ROOT/name)==digest
    for p in [frozen_path,csv_path,OUT/'snapshot-41-turmas.md',OUT/'MANIFESTO-SNAPSHOT.json']:
        p.chmod(stat.S_IREAD)
    verification=dict(checkpointId=ID,verifiedAt=datetime.now().astimezone().isoformat(),
        backupCreated=True,backupRestorable=True,currentDatabaseUnchanged=True,
        path=str(backup_path),sha256=backup_hash,filesRestored=len(manifest),
        restoreDirectory=str(restored_path),allFileHashesMatch=True,sqliteIntegrity='ok',sameLogicalDatabase=True,
        snapshotRecords=41,snapshotIdentical=True,noPERerun=True,comparatorTests=validator_tests,
        previousBackupsOverwritten=False,remoteAccess=False,deploy=False,push=False)
    emit(OUT/'VALIDACAO-BACKUP-FINAL.json',verification)
    emit(OUT/'BACKUP-FINAL.sha256',backup_hash+'  '+backup_name+'\n')
    emit(OUT/'VALIDACAO-BACKUP-FINAL.md','\n'.join(['# Validação do backup final','',
        '**BACKUP FINAL CRIADO**','**BACKUP RESTAURÁVEL VALIDADO**','**BASE ATUAL NÃO ALTERADA**','',
        f'Arquivo: {backup_path}',f'SHA-256: {backup_hash}',f'Restauração isolada: {restored_path}',
        f'{len(manifest)} arquivos restaurados e conferidos por hash; SQLite íntegro e conteúdo lógico igual à base atual; 41 registros do snapshot idênticos.',
        'Todos os arquivos de origem incluídos mantiveram hash; backup anterior não sobrescrito. A validação é local e não equivale a um backup de produção.',
        'Os arquivos deste comprovante foram criados após a verificação do ZIP; são recibos externos, não fazem parte do ZIP que atestam.',
        'Estado operacional, código, testes, evidências e snapshot estão incluídos. Caches/runtime instalado, históricos em recovery, metadados Git, credenciais .env e backups anteriores ficam fora; não foram modificados. Para restaurar o runtime, usar requirements.txt e runtimes locais registrados no manifesto.'])+'\n')
    # O índice lista saídas desta etapa sem enumerar os arquivos restaurados.
    emit(OUT/'ARQUIVOS-GERADOS.md','\n'.join(['# Arquivos gerados','']+['- '+str(p.relative_to(ROOT)) for p in sorted(OUT.iterdir()) if p.is_file()]+[
        '- '+str(backup_path.relative_to(ROOT)),'- '+str(restored_path.relative_to(ROOT))+' / árvore restaurada completa','',
        'Ferramentas locais: scripts/freeze_pe_2027_checkpoint.py e scripts/verify_pe_publication_snapshot.py. Nenhuma delas publica resultados.'])+'\n')
    print(json.dumps(verification,ensure_ascii=True))

if __name__=='__main__':main()
