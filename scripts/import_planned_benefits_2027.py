"""Importação autorizada somente em data/caj.sqlite3, com backup e idempotência."""
import json
import sys
import sqlite3
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pe_real import AUDIT, normalized
from benefits_2027 import import_benefits, summarize, apply_benefit_view
from enrollment_2027 import project_current


def main():
    import openpyxl
    wb=openpyxl.load_workbook('D:/Descontos 2027 - ABN  CAJ.xlsx',read_only=True,data_only=True)
    identities=defaultdict(set)
    for row in wb['Export'].values:
        if row[2]=='CAJ' and row[3] and row[5]:identities[normalized(row[5])].add(str(row[3]))
    wb.close()
    identity_map={k:next(iter(v)) for k,v in identities.items() if len(v)==1}
    records=json.loads((AUDIT/'registros-saneados-locais.json').read_text(encoding='utf-8'))
    database=ROOT/'data/caj.sqlite3';backup=AUDIT/'caj-antes-beneficios-previstos.sqlite3'
    db=sqlite3.connect(database)
    try:
        db.execute('BEGIN IMMEDIATE')
        version,payload=db.execute('SELECT version,payload FROM state WHERE id=1').fetchone()
        state=json.loads(payload);updated=import_benefits(state,records,identity_map)
        if updated!=state:
            if backup.exists():raise ValueError('Backup já existe; não sobrescrever sem conciliação da atualização')
            original=sqlite3.connect(f'file:{database.as_posix()}?mode=ro',uri=True)
            dest=sqlite3.connect(backup);original.backup(dest);dest.close();original.close()
            from server import validate,recalculate
            validate(updated,state);recalculate(updated)
            assert updated['classes']==state['classes'] and updated['enrollments']==state['enrollments']
            db.execute('UPDATE state SET version=?,payload=? WHERE id=1',(version+1,json.dumps(updated,ensure_ascii=False)))
            audit=dict(userId='local-documentary-import',user='Importação local autorizada pelo responsável financeiro',
                module='benefits',action='import-planned',date='2026-09-21',
                source='Descontos_2027_CAJ_Progressao_Series_Atualizada.xlsx',
                before=len(state['benefits']),after=len(updated['benefits']),rule='Base prevista independente das 775 matrículas; sem segunda progressão')
            db.execute('INSERT INTO audit(payload) VALUES(?)',(json.dumps(audit,ensure_ascii=False),))
        db.commit()
    except Exception:db.rollback();raise
    finally:db.close()
    report=json.loads((AUDIT/'resultado.json').read_text(encoding='utf-8'))
    report=apply_benefit_view(project_current(report,state=updated),updated)
    (AUDIT/'resultado.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    evidence=dict(summary=summarize(updated),identityMatches=sum(bool(b.get('studentId')) for b in updated['benefits'] if b.get('sourceKind')=='planned-2027'),
        identitySource='Export!D/F: ID associado por nome normalizado exato e único; classes preservadas da planilha progredida',
        previousVersion=version,currentVersion=version+(updated!=state))
    (AUDIT/'beneficios-previstos-importacao.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in evidence.items() if k!='summary'}|{k:v for k,v in evidence['summary'].items() if k!='rows'},ensure_ascii=True))


if __name__=='__main__':main()
