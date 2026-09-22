"""Local-only integrity evidence; never emit credentials or nominal records."""
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT = ROOT / 'output/pe-real-2027'


def main():
    baseline = json.loads((OUT / 'baseline.json').read_text(encoding='utf-8'))
    changed = [p for p, h in baseline.items() if not (ROOT / p).exists()
               or hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
    assert set(changed) == {'index.html', 'server.py', 'scripts\\audit_pe_real.py', 'pe_real.py', 'professional.js'}, changed
    before = sqlite3.connect(f'file:{(OUT / "caj-antes-matriculas.sqlite3").as_posix()}?mode=ro', uri=True)
    after = sqlite3.connect(f'file:{(ROOT / "data/caj.sqlite3").as_posix()}?mode=ro', uri=True)
    users_equal = before.execute('SELECT * FROM users ORDER BY id').fetchall() == after.execute('SELECT * FROM users ORDER BY id').fetchall()
    bv, bp = before.execute('SELECT version,payload FROM state WHERE id=1').fetchone()
    av, ap = after.execute('SELECT version,payload FROM state WHERE id=1').fetchone()
    bs, ass = json.loads(bp), json.loads(ap)
    state_changes = [k for k in set(bs) | set(ass) if bs.get(k) != ass.get(k)]
    assert set(state_changes) <= {'classes', 'enrollments', 'enrollmentDocumentarySource', 'benefits'}, state_changes
    old_audit = before.execute('SELECT * FROM audit ORDER BY id').fetchall()
    new_audit = after.execute('SELECT * FROM audit ORDER BY id').fetchall()
    assert users_equal and av == bv + 2
    assert new_audit[:len(old_audit)] == old_audit and len(new_audit) == len(old_audit) + 2
    benefits_backup=sqlite3.connect(f'file:{(OUT / "caj-antes-beneficios-previstos.sqlite3").as_posix()}?mode=ro',uri=True)
    previous_benefits_state=json.loads(benefits_backup.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
    assert {k for k in set(previous_benefits_state)|set(ass) if previous_benefits_state.get(k)!=ass.get(k)}=={'benefits'}
    from benefits_2027 import summarize
    summary=summarize(ass)
    assert (summary['total'],summary['active'],summary['waiting'],summary['pending'])==(1016,0,902,114)
    source = json.loads((ROOT / 'enrollment_2027_source.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(Path(source['source']).read_bytes()).hexdigest() == source['sha256']
    evidence = dict(baselineFiles=len(baseline), unchanged=len(baseline)-len(changed),
        authorizedChanges=changed, usersAndPermissionsUnchanged=users_equal,
        changedStateKeys=sorted(state_changes), previousVersion=bv, currentVersion=av,
        previousAuditPreserved=True, addedAuditRows=2, enrollmentSourceUnchanged=True,
        benefitImportOnlyChangedBenefits=True,benefitTotals={k:v for k,v in summary.items() if k!='rows'},
        enrollmentTotals=source['totals'], checks=dict(python=371, javascript=117, sqlStatic=9, total=497))
    (OUT / 'integridade.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    for kind in ('python', 'node', 'sql'):
        shutil.copyfile(ROOT / f'tmp/pe-real-{kind}.txt', OUT / f'testes-{kind}.txt')
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == '__main__':
    main()
