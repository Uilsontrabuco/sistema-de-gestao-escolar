"""Verifica preservação da auditoria anterior e registra testes da ponte G2."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT / 'output/reconciliacao-pendencias-pe-2027'
OUT = ROOT / 'output/reconciliacao-g2-pe-documental-15'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline = json.loads((PRIOR/'integridade.json').read_text(encoding='utf-8'))
    checks = {ROOT/name: expected for name, expected in baseline['protectedFiles'].items()}
    checks.update({ROOT/name: expected for name, expected in baseline['newCodeHashes'].items()})
    checks.update({PRIOR/name: expected for name, expected in baseline['artifacts'].items()})
    checks[ROOT/'output/auditoria-pe-completo-2027/RELATORIO.md'] = baseline['previousReportSha256']
    source = json.loads((OUT/'fontes.json').read_text(encoding='utf-8'))
    checks.update({Path(name): expected for name, expected in source['sourceHashes'].items()})
    for path, expected in checks.items():
        if sha(path) != expected:
            raise AssertionError(f'Arquivo anterior ou fonte diverge: {path}')
    logs = {name: (ROOT/'tmp'/file).read_text(encoding='utf-8', errors='replace') for name, file in
            [('python', 'g2-bridge-python.txt'), ('javascript', 'pe-audit-node.txt'), ('sql', 'pe-audit-sql.txt')]}
    for name in ('python', 'sql'):
        if not re.search(r'\nOK\s*$', logs[name]):
            raise AssertionError(f'Suíte {name} não aprovada')
    py = int(re.search(r'Ran (\d+) tests', logs['python'])[1])
    sql = int(re.search(r'Ran (\d+) tests', logs['sql'])[1])
    node = int(re.search(r'# tests (\d+)', logs['javascript'])[1])
    custom = len(re.findall(r'^# PASS ', logs['javascript'], re.M))
    containers = len(re.findall(r'^# Subtest: [A-Z]:.*(?:domain|regression|teaching_cost)\.cjs\s*$', logs['javascript'], re.M))
    if '# fail 0' not in logs['javascript'] or custom != 30 or containers != 3:
        raise AssertionError('JavaScript: conferir resultado e contagem')
    js = node-containers+custom
    for name, content in logs.items():
        (OUT/f'testes-{name}.txt').write_text(content, encoding='utf-8')
    note = f'''# Testes e preservação — somente reconciliação G2

**{py+js+sql} verificações individuais aprovadas: {py} Python + {js} JavaScript + {sql} SQL estático.**

- Python: `python -m unittest discover -s tests -p "test_*.py" -v`; 11 testes novos da ponte G2.
- JavaScript: todos os `.cjs` de `tests` e `.test.cjs` de `supabase-port/tests`; {node} entradas do runner, menos três contêineres, mais 30 casos próprios = {js} verificações.
- SQL estático: `python supabase-port/tests/final_sql_static.py`; análise de arquivos sem conexão a banco remoto.
- Novos testes verificam reprodução do PDF, fórmula histórica sem atribuição indevida a 2027, decomposição dos dois residuais, estágio sem custo duplicado, ponte exata, bases de receita distintas, origem das outras receitas, teto mínimo e bloqueio de novo PE definitivo.
- Extração visual das páginas 4, 10 e 12 e conferência da página 2 já existente. Nenhuma planilha de descontos foi aberta.
- {len(checks)} arquivos/fontes conferidos com hashes registrados anteriormente ou na extração desta execução, todos preservados. A proteção inclui código existente, banco local, prévia, relatórios e a razão completa das 41 turmas. Consequentemente, as outras 39 turmas permaneceram inalteradas.
- Node e parser SQL utilizaram a autorização para execução local fora do sandbox. Nenhum deploy, push, acesso ao Supabase remoto ou alteração de produção.

O primeiro parser da linha PDF foi ajustado para reconhecer a separação real entre nome, quantidade e receita. Os onze testes novos e a suíte completa passaram após esse ajuste. Não foi alterada nenhuma regra da aplicação.

Reprodução com fontes já extraídas: `python scripts/reconcile_g2_documentary_pe.py`. Extração dos dois arquivos originais, sem gravação neles: executar o mesmo script com `--extract` no runtime com pypdf, pypdfium2 e openpyxl.
'''
    (OUT/'TESTES.md').write_text(note, encoding='utf-8')
    result = dict(allPreserved=True, checkedFiles={str(p): h for p, h in checks.items()},
                  scope=['G2 A', 'G2 B'], other39ClassesUnchanged=True,
                  tests=dict(python=py, javascript=js, sqlStatic=sql, total=py+js+sql, newPythonTests=11),
                  newCodeHashes={name: sha(ROOT/name) for name in
                    ['scripts/reconcile_g2_documentary_pe.py', 'scripts/finalize_g2_bridge_evidence.py',
                     'tests/test_g2_documentary_bridge.py']},
                  outputHashes={str(p.relative_to(OUT)): sha(p) for p in OUT.rglob('*')
                                if p.is_file() and p.name != 'integridade.json'})
    (OUT/'integridade.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(tests=result['tests'], preservedFiles=len(checks))))


if __name__ == '__main__':
    main()
