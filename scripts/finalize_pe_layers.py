"""Consolida testes, preservação e alterações pontuais autorizadas nesta execução."""
import sys,json,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.report_pe_layers import main as report, OUT


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    prior=ROOT/'output/auditoria-documental-41-turmas-2027'
    base=json.loads((prior/'integridade.json').read_text(encoding='utf-8'))
    checks={Path(p):h for p,h in base['checkedFiles'].items()}
    checks.update({ROOT/p:h for p,h in base['newCodeHashes'].items()})
    checks.update({prior/p:h for p,h in base['outputHashes'].items()})
    server=ROOT/'server.py'
    expected_server=checks.pop(server)
    if sha(OUT/'server.py.before')!=expected_server:raise AssertionError('Backup servidor não coincide com baseline')
    route="""            if path=='/api/break-even/layers':
                require(self.current(),'financial','view')
                year=int(parse_qs(urlparse(self.path).query).get('year',['2027'])[0])
                if year!=2027:return self.respond(400,{'error':'Camadas documentais disponíveis somente para 2027.'})
                from pe_layers import build_layers
                return self.respond(200,build_layers())
"""
    current=server.read_text(encoding='utf-8')
    stripped=current.replace(route,'').replace("            permitted['/pe_layers.js']='pe_layers.js'\n",'')
    if stripped!=(OUT/'server.py.before').read_text(encoding='utf-8'):raise AssertionError('Mudança inesperada no servidor')
    html=(ROOT/'index.html').read_text(encoding='utf-8')
    if html.replace('<script src="pe_layers.js?v=202709-layers1"></script>','')!=(OUT/'index.html.before').read_text(encoding='utf-8'):
        raise AssertionError('Mudança inesperada no índice')
    for p,h in checks.items():
        if sha(p)!=h:raise AssertionError('Arquivo homologado alterado: '+str(p))
    logs={k:(ROOT/'tmp'/f).read_text(encoding='utf-8',errors='replace') for k,f in
          [('python','pe-layers-python.txt'),('javascript','pe-audit-node.txt'),('sql','pe-audit-sql.txt')]}
    for k in ('python','sql'):
        if not re.search(r'\nOK\s*$',logs[k]):raise AssertionError('Testes não aprovados: '+k)
    py=int(re.search(r'Ran (\d+) tests',logs['python'])[1]);sql=int(re.search(r'Ran (\d+) tests',logs['sql'])[1])
    node=int(re.search(r'# tests (\d+)',logs['javascript'])[1])
    custom=len(re.findall(r'^# PASS ',logs['javascript'],re.M))
    containers=len(re.findall(r'^# Subtest: [A-Z]:.*(?:domain|regression|teaching_cost)\.cjs\s*$',logs['javascript'],re.M))
    if '# fail 0' not in logs['javascript'] or custom!=30 or containers!=3:raise AssertionError('Suíte JS não aprovada')
    js=node-containers+custom;total=py+js+sql
    if (py,js,sql)!=(272,105,9):raise AssertionError('Conferir preservação/contagem das suítes')
    report()
    for k,v in logs.items():(OUT/f'testes-{k}.txt').write_text(v,encoding='utf-8')
    notes=f'''# Testes da arquitetura PE 2027

**{total} verificações individuais aprovadas: {py} Python + {js} JavaScript + {sql} SQL estático.**

353 verificações anteriores preservadas e repetidas; 33 adicionais (26 Python, 7 JavaScript).

- Python: `python -m unittest discover -s tests -p "test_*.py" -v`.
- JavaScript: `node --test` em todos os `.cjs` de `tests` e `.test.cjs` de `supabase-port/tests`. {node} entradas incluem três contêineres de 30 casos, não contados novamente: {js} casos individuais.
- SQL: `python supabase-port/tests/final_sql_static.py`; somente análise estática, nenhuma conexão.
- Novos testes cobrem três camadas, 41 turmas/1.103 vagas, 50 docentes preservados, G2 15/7/22, custos pendentes excluídos, identidades de custos/rateios, matrícula/capacidade independentes da fórmula, teto versus impresso, ausência não zero, PCLD, tripla incidência de desconto, projeção real bloqueada, parcelas compartilhadas, acesso financeiro e renderização/navegação/erro sem dado obsoleto.
- Fluxo de navegador verificado na base TEMPORÁRIA `127.0.0.1:8877`: login de teste → menu PE → API autenticada → 41 linhas. G2 A/B exibiram documental 15, gerencial parcial 7, provisório 22, custo pendente e cobertura incompleta. Inspeção visual confirmou leitura da tabela e explicações. A ferramenta agent-browser não estava instalada; foi usada a automação de navegador disponível no Codex. Console não foi coletado; navegação, retorno da API e conteúdo visível foram verificados.
- A verificação visual encontrou que o menu PE não selecionava a página financeira; o adaptador novo corrige isso e há teste de regressão específico. Falha de atualização limpa resultados anteriores em vez de manter valores obsoletos.
- {len(checks)} arquivos/fontes anteriores com hashes idênticos, incluindo banco, dados homologados e relatórios G2/41. O servidor foi validado contra backup: somente rota de leitura e arquivo JS público adicionados; o índice adiciona apenas o adaptador. Cálculos legados e expectativas anteriores não foram alterados.
- Nenhum deploy, push, importação de descontos, alteração de produção ou acesso ao Supabase remoto. Node/parser SQL usaram autorização local fora do sandbox para caminhos.

Resultado: ARQUITETURA DO PE 2027 VALIDADA. PE gerencial ainda não documentalmente fechado: comprovado significa a base parcial identificada, não completude de todos os custos.
'''
    (OUT/'TESTES.md').write_text(notes,encoding='utf-8')
    path=OUT/'RELATORIO.md';text=path.read_text(encoding='utf-8')
    text=text.replace('K. **Testes:** contagem e logs finais em TESTES.md. As 353 verificações anteriores são repetidas, sem alterar suas expectativas.',
        f'K. **{total} verificações aprovadas:** {py} Python + {js} JavaScript + {sql} SQL estático. As 353 anteriores foram preservadas; 33 novas. Logs em TESTES.md.')
    path.write_text(text,encoding='utf-8')
    new=['pe_layers.py','pe_layers.js','pe_layers_2027_source.json','scripts/package_pe_layers.py','scripts/report_pe_layers.py',
         'scripts/finalize_pe_layers.py','scripts/preview_pe_layers.py','tests/test_pe_layers.py','tests/test_pe_layers_http.py','tests/pe_layers.test.cjs']
    evidence=dict(previousTestsPreserved=353,tests=dict(python=py,javascript=js,sqlStatic=sql,total=total,newCases=33),
        preservedFiles={str(p):h for p,h in checks.items()},
        authorizedChanges={name:dict(before=sha(OUT/(name+'.before')),after=sha(ROOT/name)) for name in ('server.py','index.html')},
        newFiles={name:sha(ROOT/name) for name in new},
        outputs={str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='integridade.json'},
        architectureValidated=True,managerialDocumentarilyClosed=False)
    (OUT/'integridade.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(evidence['tests']))


if __name__=='__main__':main()
