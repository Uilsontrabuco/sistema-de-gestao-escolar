"""Consolida evidência nova sem reescrever a auditoria anterior."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/reconciliacao-pendencias-pe-2027'
OLD = ROOT / 'output/auditoria-pe-completo-2027'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline = json.loads((OLD / 'integridade.json').read_text(encoding='utf-8'))
    for name, expected in baseline['protectedFiles'].items():
        if digest(ROOT / name) != expected:
            raise AssertionError(f'Arquivo protegido diverge: {name}')
    if digest(OLD / 'RELATORIO.md') != baseline['reportSha256']:
        raise AssertionError('Relatório anterior diverge')
    sources = json.loads((OUT / 'fontes/manifesto.json').read_text(encoding='utf-8'))
    for source in sources:
        if 'sha256' in source and digest(Path(source['path'])) != source['sha256']:
            raise AssertionError(f"Fonte diverge: {source['path']}")
    logs = {name: (ROOT / 'tmp' / file).read_text(encoding='utf-8', errors='replace')
            for name, file in [('python', 'pe-pending-python.txt'),
                               ('javascript', 'pe-audit-node.txt'), ('sql', 'pe-audit-sql.txt')]}
    for name in ('python', 'sql'):
        if not re.search(r'\nOK\s*$', logs[name]):
            raise AssertionError(f'Suíte incompleta: {name}')
    if '# fail 0' not in logs['javascript']:
        raise AssertionError('JavaScript falhou')
    py = int(re.search(r'Ran (\d+) tests', logs['python'])[1])
    sql = int(re.search(r'Ran (\d+) tests', logs['sql'])[1])
    node = int(re.search(r'# tests (\d+)', logs['javascript'])[1])
    custom = len(re.findall(r'^# PASS ', logs['javascript'], re.M))
    containers = len(re.findall(r'^# Subtest: [A-Z]:.*(?:domain|regression|teaching_cost)\.cjs\s*$', logs['javascript'], re.M))
    if containers != 3 or custom != 30:
        raise AssertionError('Revisar contagem JavaScript')
    js = node - containers + custom
    total = py + js + sql
    for name, content in logs.items():
        (OUT / f'testes-{name}.txt').write_text(content, encoding='utf-8')
    note = f'''# Validação da continuidade documental do PE 2027

**{total} verificações individuais aprovadas, zero falhas finais.**

- Python: {py}, incluindo 13 testes documentais novos nesta execução e os 21 testes da auditoria anterior. Comando: `python -m unittest discover -s tests -p "test_*.py" -v`.
- JavaScript: {js}. Runner: {node} entradas, das quais {containers} contêineres de {custom} casos próprios; contêineres não contados novamente. Incluídos todos os `.cjs` de `tests` e `.test.cjs` de `supabase-port/tests`.
- SQL estático: {sql}. Comando: `python supabase-port/tests/final_sql_static.py`. Somente análise de arquivos, sem conexão a banco remoto.

Novos testes cobrem fontes oficiais, 125 registros de folha e 2.131 rubricas, somas documentais, identidade/função, lacunas de custo, controles históricos institucionais, residuais G2, contas de descontos, mensalidades e preservação do cenário. Aprovação técnica não substitui comprovação documental dos valores ainda ausentes.

Node e parser SQL usaram autorização de execução fora do sandbox para caminhos locais. Nenhum deploy, push, alteração de produção, conexão ao Supabase remoto ou importação de descontos.

Os hashes protegidos foram comparados com o registro da auditoria anterior; todos coincidem, inclusive o banco local e o relatório anterior. Os originais recuperados em D: coincidem com os hashes coletados na extração desta execução.

Reprodução: extração com `scripts/trace_pe_document_sources.py` (runtime com pypdf/openpyxl), seguida de `python scripts/reconcile_pe_pending.py`. Após a suíte completa, `python scripts/finalize_pe_pending_evidence.py` consolida logs e integridade sem executar o gerador do relatório anterior.
'''
    (OUT / 'TESTES.md').write_text(note, encoding='utf-8')
    files = ['scripts/trace_pe_document_sources.py', 'scripts/reconcile_pe_pending.py',
             'scripts/finalize_pe_pending_evidence.py', 'tests/test_pe_pending_documents.py']
    evidence = dict(
        scope='Comparação com hashes da auditoria anterior e hashes dos originais coletados nesta continuidade',
        allPreserved=True, protectedFiles=baseline['protectedFiles'],
        previousReportSha256=baseline['reportSha256'], sources=sources,
        tests=dict(python=py, javascript=js, sqlStatic=sql, total=total,
                   newPythonTests=13, nodeRunnerEntries=node, customScriptCases=custom),
        newCodeHashes={name: digest(ROOT / name) for name in files},
        artifacts={str(p.relative_to(OUT)): digest(p) for p in sorted(OUT.rglob('*'))
                   if p.is_file() and p.name != 'integridade.json'},
        documentaryClosed=False)
    (OUT / 'integridade.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(evidence['tests']))


if __name__ == '__main__':
    main()
