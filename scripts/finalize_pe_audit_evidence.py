"""Empacota logs e prova integridade durante a reprodução local do relatório."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from scripts.audit_full_pe_2027 import main, OUT, SOURCE


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize():
    paths=[ROOT/name for name in (
        'server.py','domain.js','break_even.js','financial_integration.py',
        'teaching_cost.py','teaching_projection.py','budget_2027_snapshot.py',
        'personnel_projection.py','data/caj.sqlite3',
        'scripts/generate_approved_pe_2027_preview.py',
        'output/previa-auditavel-aprovada-2027/previa.json',
        'output/previa-auditavel-aprovada-2027/RELATORIO.md',
        'output/fechamento-modulo-2027/fechamento.json')]+[SOURCE]
    before={str(p.relative_to(ROOT)):digest(p) for p in paths}
    logs={name:(ROOT/'tmp'/file).read_text(encoding='utf-8',errors='replace')
          for name,file in [('python','pe-audit-python-final.txt'),('javascript','pe-audit-node.txt'),('sql','pe-audit-sql.txt')]}
    for name in ('python','sql'):
        if not re.search(r'\nOK\s*$',logs[name]):
            raise ValueError(f'Suíte {name} não terminou aprovada')
    if '# fail 0' not in logs['javascript']:
        raise ValueError('JavaScript não aprovado')
    python_count=int(re.search(r'Ran (\d+) tests',logs['python'])[1])
    sql_count=int(re.search(r'Ran (\d+) tests',logs['sql'])[1])
    node_count=int(re.search(r'# tests (\d+)',logs['javascript'])[1])
    custom_pass=len(re.findall(r'^# PASS ',logs['javascript'],re.M))
    custom_files=len(re.findall(r'^# Subtest: [A-Z]:.*(?:domain|regression|teaching_cost)\.cjs\s*$',logs['javascript'],re.M))
    if custom_files != 3 or custom_pass != 30:
        raise ValueError('Contagem dos scripts JavaScript mudou; revisar explicitamente')
    js_count=node_count-custom_files+custom_pass
    main()
    after={str(p.relative_to(ROOT)):digest(p) for p in paths}
    if before != after:
        raise ValueError('Arquivo protegido mudou durante a reprodução')
    evidence=dict(scope='Comparação antes/depois da reprodução final; não é hash coletado antes do início da conversa',
                  protectedFiles=before, allPreserved=True,
                  localDatabaseInspection=dict(mode='read-only',stateVersion=0,classes=41,capacity=1103,plans=0),
                  sourceScope='Extrações locais existentes e checkpoint aprovado; sem consulta da produção',
                  tests=dict(python=python_count,javascript=js_count,sqlStatic=sql_count,
                             total=python_count+js_count+sql_count,newPythonTests=21,
                             nodeRunnerEntries=node_count,customScriptCases=custom_pass),
                  changedThisExecution=['pe_full_audit.py','scripts/audit_full_pe_2027.py',
                      'scripts/finalize_pe_audit_evidence.py','tests/test_full_pe_audit.py'],
                  reportSha256=digest(OUT/'RELATORIO.md'))
    (OUT/'integridade.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    for name,text in logs.items():
        (OUT/f'testes-{name}.txt').write_text(text,encoding='utf-8')
    note=f'''# Testes da auditoria PE completo 2027

**{python_count+js_count+sql_count} verificações individuais aprovadas; zero falhas finais.**

- Python: {python_count}, incluindo 21 testes novos. Comando: `python -m unittest discover -s tests -p "test_*.py" -v`.
- JavaScript: {js_count}. O runner `node --test` relata {node_count} entradas: {node_count-custom_files} testes nativos e três arquivos que contêm {custom_pass} casos próprios (15 domínio, 11 regressão, 4 custeio). Os arquivos contêineres não foram contados novamente.
- SQL estático: {sql_count}. Comando: `python supabase-port/tests/final_sql_static.py`. Somente parser de arquivos; não executa SQL.
- A suíte JavaScript incluiu todos os `.cjs` de `tests` e os `.test.cjs` de `supabase-port/tests`.
- Servidores auxiliares `visual_server.py` e `preview.py` são ferramentas de QA, não suítes automatizadas; não foram iniciados. Nenhuma interface foi modificada nesta execução.

Os primeiros testes novos detectaram duas expectativas de teste imprecisas: centavo do ticket do 3º EM e comparação exata de ponto flutuante no percentual. Corrigidas as expectativas, a suíte completa foi repetida e aprovada. Node e parser SQL precisaram da autorização de execução fora do sandbox para acessar caminhos locais; nenhuma chamada de produção foi realizada.

Os testes cobrem manifestos de turmas/vagas, custos da grade, tarifas, duração e rateios compartilhados na suíte existente; a nova suíte cobre distribuição integral do saldo institucional, razão sem perdas/duplicatas, PCLD, inadimplência, calendário, PE mínimo inteiro, independência das matrículas, contas documentais e contrato futuro de descontos. Ver os logs completos nesta pasta.

Reproduzir o relatório: `python scripts/audit_full_pe_2027.py`.
Após atualizar os logs em `tmp`, consolidar evidências: `python scripts/finalize_pe_audit_evidence.py`.

O teste de preservação em `integridade.json` compara hashes antes/depois da reprodução final. O banco local foi inspecionado em modo somente leitura e não contém plano 2027 persistido; o trabalho usa o checkpoint e as fontes locais, não uma base remota atualizada.
'''
    (OUT/'TESTES.md').write_text(note,encoding='utf-8')
    report=OUT/'RELATORIO.md'
    text=report.read_text(encoding='utf-8').replace('Ver TESTES.md, logs e integridade.json nesta pasta.',
        f"**{python_count+js_count+sql_count} verificações aprovadas: {python_count} Python + {js_count} JavaScript + {sql_count} SQL estático; 21 testes novos.** Ver TESTES.md, logs e integridade.json nesta pasta.")
    report.write_text(text,encoding='utf-8')
    evidence['reportSha256']=digest(report)
    (OUT/'integridade.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(evidence['tests']))


if __name__=='__main__':
    finalize()
