"""Preserva a reconciliação G2 e toda evidência anterior; empacota a auditoria 41."""
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
G2=ROOT/'output/reconciliacao-g2-pe-documental-15'
OUT=ROOT/'output/auditoria-documental-41-turmas-2027'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    baseline=json.loads((G2/'integridade.json').read_text(encoding='utf-8'))
    checks={Path(p):h for p,h in baseline['checkedFiles'].items()}
    checks.update({ROOT/p:h for p,h in baseline['newCodeHashes'].items()})
    checks.update({G2/p:h for p,h in baseline['outputHashes'].items()})
    sources=json.loads((OUT/'fontes.json').read_text(encoding='utf-8'))
    checks.update({Path(p):h for p,h in sources['sourceHashes'].items()})
    for path,expected in checks.items():
        if sha(path)!=expected: raise AssertionError('Alteração de fonte/arquivo anterior: '+str(path))
    logs={name:(ROOT/'tmp'/file).read_text(encoding='utf-8',errors='replace') for name,file in
          [('python','41-pe-python.txt'),('javascript','pe-audit-node.txt'),('sql','pe-audit-sql.txt')]}
    for name in ('python','sql'):
        if not re.search(r'\nOK\s*$',logs[name]): raise AssertionError('Suíte incompleta: '+name)
    py=int(re.search(r'Ran (\d+) tests',logs['python'])[1])
    sql=int(re.search(r'Ran (\d+) tests',logs['sql'])[1])
    node=int(re.search(r'# tests (\d+)',logs['javascript'])[1])
    custom=len(re.findall(r'^# PASS ',logs['javascript'],re.M))
    containers=len(re.findall(r'^# Subtest: [A-Z]:.*(?:domain|regression|teaching_cost)\.cjs\s*$',logs['javascript'],re.M))
    if '# fail 0' not in logs['javascript'] or custom!=30 or containers!=3:
        raise AssertionError('Conferir suíte JavaScript')
    js=node-containers+custom
    if py!=baseline['tests']['python']+15 or js!=baseline['tests']['javascript'] or sql!=baseline['tests']['sqlStatic']:
        raise AssertionError('Verificações anteriores não preservadas')
    for name,content in logs.items():
        (OUT/f'testes-{name}.txt').write_text(content,encoding='utf-8')
    note=f'''# Validação da auditoria documental das 41 turmas

**{py+js+sql} verificações individuais aprovadas: {py} Python + {js} JavaScript + {sql} SQL estático.**

As 338 verificações anteriores foram preservadas e repetidas; foram adicionados 15 testes da comparação documental.

- Python: `python -m unittest discover -s tests -p "test_*.py" -v`.
- JavaScript: `node --test` com todos os `.cjs` de `tests` e `.test.cjs` de `supabase-port/tests`. {node} entradas incluem três contêineres de 30 casos próprios, contados uma única vez; total {js}.
- SQL: `python supabase-port/tests/final_sql_static.py`. Somente parser estático; sem execução remota.
- Novos testes: 48 linhas documentais, capacidade ausente versus alunos previstos, fórmulas históricas, três turmas sem correspondência, 8º C inativo, conclusão G2, pontes exatas de custo/receita, benefícios, universos comparáveis, arredondamentos, coincidência de PE sem equivalência de base, tabela de 41 e benefícios negativos fora do cadastro atual.
- {len(checks)} arquivos/fontes anteriores conferidos por SHA-256 e preservados, incluindo todo o relatório G2, seus testes/código, fontes, banco local, módulos existentes e relatórios anteriores.
- A leitura por coordenadas da coluna de capacidade foi ajustada à diferença vertical de fonte entre os rótulos e números dos subtotais (tolerância de 2 pontos, com linhas distantes mais de 10 pontos). A conferência visual mostrou somente zeros de subtotal; nenhuma capacidade individual foi inferida desses zeros.
- Node e parser SQL usaram a autorização para execução local fora do sandbox por dependências de caminhos. Não houve deploy, push, alteração de PE/produção, acesso ao Supabase remoto ou importação da planilha de descontos.

Reprodução com fontes extraídas: `python scripts/audit_documentary_41_pe.py`. Extração original: o mesmo script com `--extract` no runtime com pypdf, pdfplumber e openpyxl. Consolidação após testes: `python scripts/finalize_documentary_41_evidence.py`.

Testes aprovados demonstram reprodução e preservação; não certificam composição nominal ausente nem adotam metodologia definitiva.
'''
    (OUT/'TESTES.md').write_text(note,encoding='utf-8')
    evidence=dict(allPreserved=True,checkedFiles={str(p):h for p,h in checks.items()},
        g2ConclusionUnchanged=True,definitivePEsChanged=False,previousApprovedTests=338,
        tests=dict(python=py,javascript=js,sqlStatic=sql,total=py+js+sql,newPythonTests=15),
        newCodeHashes={p:sha(ROOT/p) for p in ['scripts/audit_documentary_41_pe.py',
            'scripts/finalize_documentary_41_evidence.py','tests/test_documentary_41_audit.py']},
        outputHashes={str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='integridade.json'})
    (OUT/'integridade.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(tests=evidence['tests'],preservedFiles=len(checks))))


if __name__=='__main__': main()
