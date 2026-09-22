import sys,json,re,hashlib,sqlite3
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pe_real import AUDIT
from enrollment_2027 import apply_snapshot_to_state,project_current


def main():
    from pypdf import PdfReader
    p=Path('D:/Turmas CAJ 2027 (2).pdf')
    pages=[page.extract_text() for page in PdfReader(p).pages]
    rooms=json.loads((ROOT/'pe_layers_2027_source.json').read_text(encoding='utf-8'))['rows']
    lookup={r['name']:r for r in rooms};rows=[];ignored=[]
    for page,text in enumerate(pages,1):
        for line in text.splitlines():
            m=re.fullmatch(r'(.+?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)',line.strip())
            if not m:
                if line.strip()=='1º EM B':ignored.append(dict(label=line.strip(),page=page,reason='Linha sem valores, não é 42ª turma'))
                continue
            label,*values=m.groups()
            if label=='Total':continue
            name='1º EM' if label=='1º EM A' else label
            if name not in lookup:raise ValueError('Turma não homologada: '+name)
            cap,count,new,returning,vac=map(int,values)
            if cap!=lookup[name]['capacity'] or count!=new+returning or vac!=cap-count:raise ValueError('Linha inconsistente: '+name)
            rows.append(dict(id=lookup[name]['id'],name=name,sourceLabel=label,sourcePage=page,
                capacity=cap,students=count,new=new,re=returning,vacancies=vac))
    totals={k:sum(r[k] for r in rows) for k in ('capacity','students','new','re','vacancies')}
    assert len(rows)==41 and len({r['id'] for r in rows})==41
    assert totals==dict(capacity=1103,students=775,new=37,re=738,vacancies=328)
    data=dict(source=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=rows,totals=totals,ignoredRows=ignored)
    (ROOT/'enrollment_2027_source.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    (AUDIT/'matriculas-fonte.txt').write_text('\n'.join(pages),encoding='utf-8')
    # Alvo local fixo, backup consistente antes da única atualização transacional.
    database=ROOT/'data/caj.sqlite3';backup=AUDIT/'caj-antes-matriculas.sqlite3'
    db=sqlite3.connect(database)
    try:
        db.execute('BEGIN IMMEDIATE')
        version,payload=db.execute('SELECT version,payload FROM state WHERE id=1').fetchone()
        state=json.loads(payload)
        if state.get('enrollmentDocumentarySource',{}).get('sha256')!=data['sha256']:
            if backup.exists():raise ValueError('Backup já existe; não sobrescrever estado anterior')
            # Conexão somente leitura para copiar o estado confirmado anterior à transação.
            original=sqlite3.connect(f'file:{database.as_posix()}?mode=ro',uri=True)
            dest=sqlite3.connect(backup);original.backup(dest);dest.close();original.close()
            updated=apply_snapshot_to_state(state,data)
            from server import validate,recalculate
            recalculate(updated);validate(updated,state)
            db.execute('UPDATE state SET payload=?,version=? WHERE id=1',(json.dumps(updated,ensure_ascii=False),version+1))
            audit=dict(userId='local-documentary-import',user='Importação documental local autorizada',module='enrollments',
                action='snapshot',date=datetime.now(timezone.utc).isoformat(),field='classes/enrollments',
                before=state['classes'],after=updated['classes'],source=data['source'],sha256=data['sha256'])
            db.execute('INSERT INTO audit(payload) VALUES(?)',(json.dumps(audit,ensure_ascii=False),))
        db.commit()
    except Exception:db.rollback();raise
    finally:db.close()
    report=json.loads((AUDIT/'resultado.json').read_text(encoding='utf-8'))
    (AUDIT/'resultado.json').write_text(json.dumps(project_current(report,data=data),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(totals))


if __name__=='__main__':main()
