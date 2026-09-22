"""Gera somente mapa de pendências a partir do checkpoint, sem cálculo de PE."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/mapa-pendencias-financeiras-2027'
TOTAL = 12413202

def load(p):
    return json.loads((ROOT / p).read_text(encoding='utf-8'))

def money(c):
    return f'{c/100:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')

def pct(c):
    return f'{c/TOTAL*100:.4f}%'.replace('.', ',')

def account_question(a):
    code, desc = a['code'], a['description']
    if code == '4111001':
        detail = 'nomes/matrículas, parcela mensal orçada de cada posto, centro de custo e turmas atendidas; separar as quotas nominais já protegidas'
    elif code in ('4111005', '4111009', '4112001', '4111020'):
        detail = 'postos que geram a provisão/encargo/ajuste, valor orçado de cada um e vínculo com os mesmos beneficiários do salário; indicar o que já está coberto'
    elif code == '4119040':
        detail = 'estagiária/posto e turma atendida, bolsa/seguro/consultoria cobertos; distinguir Emilly, Liliane, Sthefany, Gleiciane, Rebeca e Sheila e as quotas já protegidas'
    elif code == '4119010':
        detail = 'prestador/contrato RPS/RPA, serviço, valor mensal e turmas efetivamente atendidas; indicar se há sobreposição com pessoal já incluído'
    elif code.startswith('411'):
        detail = 'funcionário/posto beneficiário, valor mensal previsto por posto, centro de custo e abrangência turma/série/segmento/escola, descontadas as parcelas já cobertas'
    elif code in ('4191005', '4193250', '4129101', '4129102', '4129103', '4129121'):
        detail = 'valor desta conta dentro de cada saldo de Gerais p.4 e alcance institucional/segmento previsto no critério existente; indicar cobertura já incluída em outros rateios'
    elif code.startswith('4123'):
        detail = 'bem/instalação, local de uso, depreciação mensal e turmas/segmentos que utilizam o ativo'
    elif code.startswith('4122'):
        detail = 'local/equipamento atendido, serviço previsto, valor mensal e salas/turmas beneficiadas'
    elif code in ('4121040', '4121048', '4124010'):
        detail = 'obrigação/processo, centro responsável, valor mensal e se o fato gerador é institucional ou ligado a turma/posto específico'
    elif code in ('4121058',):
        detail = 'posto beneficiado pela moradia, valor previsto e vínculo desse posto com turma/série/segmento ou escola'
    elif code in ('4121001', '4121021', '4121042', '4121051', '4121074'):
        detail = 'unidade/local/contrato ou licença atendida, parcela mensal e abrangência efetiva; distinguir custo global de uso exclusivo'
    else:
        detail = 'serviço/material/atividade beneficiada, valor mensal, centro responsável e turmas/segmentos efetivamente atendidos'
    return f'Na conta {code} ({desc}), qual valor integra cada saldo listado e quais são {detail}?'

def main():
    OUT.mkdir(exist_ok=True)
    sources = [
        'output/forense-saldos-2027/composicao-e-simulacao-conservadora.json',
        'output/forense-saldos-2027/RELATORIO-FORENSE-DOS-SALDOS.md',
        'output/reconciliacao-pendencias-pe-2027/reconciliacao.json',
        'output/pre-publicacao-2027/backup-premissas-8C-mantido-20270922.zip',
        'output/simulacao-rateio-series-2027/simulacao.json',
    ]
    hashes = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}
    checkpoint = load(sources[0])
    people = load(sources[2])['people']
    groups = {'payrollCents / saldo': 'FOLHA', 'supportCents / saldo': 'APOIO', 'generalNetCents / saldo': 'GERAIS'}
    rows = []
    for c in checkpoint['components']:
        if c['component'] not in groups:
            continue
        group = groups[c['component']]
        series = c['turma'].split()[0]
        segment = 'Fundamental II' if series == '8º' else 'Fundamental I'
        question = (f"Dos R$ {money(c['cents'])} hoje associados a {c['turma']}, quais contas e valores formam o saldo de {group.lower()}? "
                    f"Para cada parcela, ela atende somente {c['turma']}, quais outras turmas do {series} ano, o segmento ou a escola? ")
        question += ('Indique o funcionário/posto e o que já está coberto por salário/encargos.' if group == 'FOLHA' else
                     'Indique o posto/prestador e o que já está coberto pelas quotas nominais/C28/C29.' if group == 'APOIO' else
                     'Indique o serviço/bem/local e a parcela já coberta pelo rateio global existente.')
        rows.append(dict(id=f"{group}-{c['turma'].replace(' ', '')}", group=group, turma=c['turma'], series=series,
            cents=c['cents'], percent=pct(c['cents']), accountCode=None,
            accountFamily='411* (não é conta analítica)' if group != 'GERAIS' else 'Contas operacionais líquidas; código analítico não vinculado',
            description=f'Saldo de {group.lower()} após controles nominais preservados',
            source=c['evidence'], department=segment+'; centro de custo analítico do saldo não consta',
            reason='A linha p.4 informa bloco agregado; não há matriz conta × posto/serviço × bloco × turma que reconcilie o saldo após as quotas protegidas.',
            required=question, classification=5))
    rows.sort(key=lambda r: (-r['cents'], r['id']))
    assert len(rows) == 33 and sum(r['cents'] for r in rows) == TOTAL
    totals = {g: sum(r['cents'] for r in rows if r['group']==g) for g in ['FOLHA','APOIO','GERAIS','OUTROS']}
    accounts = []
    for a in checkpoint['accountCatalogue']:
        # Já neutralizados, não compõem os saldos e não geram decisão para cobri-los.
        if a['excludedFromEconomicCost']:
            continue
        group = 'APOIO' if a['code'] in ('4119010','4119040') else 'FOLHA' if a['code'].startswith('411') else 'GERAIS'
        accounts.append(dict(code=a['code'], description=a['description'], schoolMonthlyCents=a['monthlyCents'],
            pendingPartCents=None, percentOfPending=None, group=group, sourcePage=a['sourcePage'],
            source='Orçamento COLÉGIO ADVENTISTA DE JUAZEIRO 2027 (1).pdf',
            department=a['scope']+'; não identifica centro de custo da parcela',
            segmentAllocation=a.get('segmentAllocationCents'), classificationUnchanged=True,
            reason='Valor escolar identificado; parcela nesta pendência e beneficiário por turma não conciliados.',
            question=account_question(a)))
    accounts.sort(key=lambda a: (-a['schoolMonthlyCents'], a['code']))
    lines = ['# MAPA DAS PENDÊNCIAS FINANCEIRAS PARA DECISÃO HUMANA', '',
        'Checkpoint forense aprovado e preservado. Este documento é um mapa de perguntas; não gera simulação, redistribuição, classificação nova ou cálculo de PE.', '',
        '**Limite de granularidade:** os R$ 124.132,02 são 33 saldos de bloco/turma, não 33 contas analíticas. É possível detalhar exatamente os valores por origem, mas não atribuir valor a cada conta sem inventar uma decomposição. Por isso o mapa contém duas tabelas complementares: saldos que fecham o total e contas separadas com a parcela pendente marcada N/D. O total escolar de uma conta não é sua parcela nos R$ 124.132,02.', '',
        '## Totais por grupo', '', '| Grupo | Pendente R$ | % do total |','|---|---:|---:|']
    for g in sorted(totals, key=lambda g: -totals[g]):
        lines.append(f'| {g} | {money(totals[g])} | {pct(totals[g])} |')
    lines += ['', 'OUTROS = R$ 0,00 na composição deste checkpoint: não é suposição de inexistência de despesas na escola. Nenhuma parcela adicional ou reserva foi incluída.', '',
        '## Saldos por origem — ordem decrescente dentro de cada grupo', '',
        'Origem documental comum: orçamento oficial p.4, reconciliado no checkpoint após as quotas nominais. O valor de cada linha é saldo aritmético, não lançamento identificado. A lista global em ordem decrescente está também no arquivo JSON. Percentuais arredondados a quatro casas.', '']
    for group in ['FOLHA','APOIO','GERAIS','OUTROS']:
        lines += [f'### {group}', '', '| ID / código da conta | Descrição | Valor R$ | % | Origem/documento | Departamento/CC existente | Associação atual | Motivo da pendência | Informação necessária / pergunta administrativa |',
                  '|---|---|---:|---:|---|---|---|---|---|']
        for r in rows:
            if r['group'] == group:
                lines.append(f"| {r['id']} / analítica N/D ({r['accountFamily']}) | {r['description']} | {money(r['cents'])} | {r['percent']} | {r['source']} | {r['department']} | {r['turma']} / {r['series']} ano | {r['reason']} | {r['required']} |")
        if not totals[group]:
            lines.append('| Nenhum saldo neste grupo | — | 0,00 | 0,0000% | Checkpoint | — | — | — | Nenhuma decisão adicional |')
    lines += ['', '## Contas analíticas separadas — perguntas para completar a decomposição', '',
        '**Não somar esta tabela à anterior.** Valor de referência é o mensal da escola; parcela e percentual dentro do total pendente continuam N/D. Ordenação decrescente pelo valor escolar, único valor conhecido por conta. A separação de contas 411 entre FOLHA e APOIO abaixo organiza perguntas por natureza, não comprova em qual bloco p.4 foram contabilizadas. A primeira resposta necessária é justamente esse vínculo.', '']
    for group in ['FOLHA','APOIO','GERAIS','OUTROS']:
        lines += [f'### {group} — contas', '', '| Código | Descrição | Mensal escola R$ (referência) | Parcela pendente R$ / % | Origem | Departamento/CC existente | Turma/série associada à parcela | Impedimento | Pergunta objetiva |',
                  '|---|---|---:|---|---|---|---|---|---|']
        for a in accounts:
            if a['group'] == group:
                lines.append(f"| {a['code']} | {a['description']} | {money(a['schoolMonthlyCents'])} | N/D / N/D | Orçamento oficial p.{a['sourcePage']} | {a['department']} | Não demonstrada; conferir saldos de 1º/2º/3º A/B/C e 8º A/B | {a['reason']} | {a['question']} |")
        if group == 'OUTROS':
            lines.append('| — | Nenhuma parcela residual separada no checkpoint | — | 0,00 / 0% | Checkpoint | — | — | — | — |')
    lines += ['', 'Contas 4124001 (PCLD), 4126005 (descontos financeiros) e 4126007 (descontos condicionais) já neutralizadas: não são fontes dos saldos e não precisam ser reinseridas. Contas negativas, como 4114051, conservam o sinal; não viram custo positivo.', '',
        '## Funcionários e serviços já identificados — sem reclassificação', '',
        'Não foi comprovado quanto do RESÍDUO corresponde a cada pessoa. Há nomes ligados às quotas nominais já protegidas e pessoas históricas nas contas de pessoal. Identificação da pessoa não é identificação do saldo. Valores abaixo são controles existentes, nunca acréscimos ou deduções da pendência.', '',
        '| Turma/abrangência | Nome / função | Controle conhecido | Evidência | Pergunta administrativa |','|---|---|---|---|---|']
    for c in checkpoint['components']:
        if c['component'] in ('estagiarias','auxiliares-segmento','coordenacao-segmento'):
            lines.append(f"| {c['turma']} | {c['employeeOrService']} / {c['component']} | R$ {money(c['cents'])}, quota já protegida | {c['evidence']} | O saldo desta turma contém outra parcela deste posto além da quota protegida? Qual conta, valor e beneficiário, ou confirme que a cobertura já está integral? |")
    bycode = {str(p['code']): p for p in people}
    for cl in checkpoint['nominalDetails']:
        seen = set()
        for t in cl['teacher_costs']:
            name = t['professor']
            if name in seen or 'lohana' in name.lower() or 'marcelo' in name.lower():
                continue
            seen.add(name)
            p = bycode.get(str(t.get('professor_id')), {})
            dept = p.get('department','Departamento não identificado no cadastro cruzado')
            lines.append(f"| {cl['class_name']} | {name} / docente, {dept} | Quota docente preservada, ver checkpoint; parcela no resíduo N/D | Grade homologada: {', '.join(t.get('source_codes', []))}; cadastro/folha {p.get('payrollPage','N/D')} | Há encargo/provisão orçamentário deste posto no saldo, além da quota protegida? Qual conta e valor, e quais turmas o posto atende? |")
    lines += [
        '| Administrativo | Lohana Rodrigues Leite da Silva / Auxiliar Administrativo, não docente | Parcela no resíduo N/D | Decisão administrativa vigente; cadastro histórico C28 não redefine a função | Em qual conta/centro está a cobertura de Lohana e quais turmas/segmentos atende? Essa cobertura já foi integralmente incluída no orçamento/rateios? |',
        '| Folha | Marcelo / integra a folha; função específica não fornecida | Parcela no resíduo N/D; R$ 39,15 histórico não é novo salário | Confirmação administrativa e controle histórico do 8º C | Qual matrícula/posto e conta vinculam Marcelo ao orçamento já contabilizado, e quais beneficiários atende? |',
        '| Serviços gerais | Jailane, Veroneide e Paula / ASG, 44h semanais, R$ 1.690,50 por pessoa | Salários/jornada aprovados; parcela no resíduo N/D | Premissas administrativas preservadas | Em quais contas/centros os três postos já estão cobertos e quais locais/turmas atendem? Indique apenas a cobertura existente, sem acrescentar salários novamente. |', '',
        'Rateio Sede 4191005 e Fundo Educação 4193250 são serviços/rateios institucionais identificados. Falta somente quantificar sua presença nos saldos das linhas e demonstrar a ligação com o critério global existente; sua natureza institucional não autoriza repartir um saldo sem essa ligação.', '',
        '## PRIORIDADE PARA DESTRAVAR 1º D, 2º D, 3º D E 8º C', '',
        'Esta seção contém apenas as decisões sobre composição e beneficiários que podem fechar a cobertura dessas quatro turmas. Nenhum PE é recalculado. A/B/C são origens a conciliar, não fontes autorizadas a transferir.', '',
        '| Prioridade / turma | Origens do saldo | Contas/informações a decidir | Pergunta para resposta do responsável |','|---|---|---|---|']
    for target, series, origins in [('1º D','1º','1º A/B/C'),('2º D','2º','2º A/B/C'),('3º D','3º','3º A/B/C'),('8º C','8º','8º A/B')]:
        amounts = {g: sum(r['cents'] for r in rows if r['series']==series and r['group']==g) for g in totals}
        for g in ['FOLHA','APOIO','GERAIS']:
            codes = ('4111001/4111005/4111009/4112001/4111020 e demais 411 que efetivamente compõem o bloco; posto, cobertura já contabilizada e beneficiários' if g=='FOLHA' else
                     '4119040/4119010 e demais contas efetivamente usadas no bloco; posto/contrato e cobertura C28/C29 já protegida' if g=='APOIO' else
                     '4191005/4193250 e contas operacionais 412*/414* efetivamente integrantes; serviço/bem/local, valor e beneficiários')
            lines.append(f'| {target} — {g} | {origins}: R$ {money(amounts[g])} de saldo | {codes} | Que parcela já orçada atende também {target}? Informe conta, valor mensal e posto/serviço que comprova o atendimento, ou indique expressamente que não atende. Separe a parcela exclusiva das origens e confirme ausência de cobertura duplicada. |')
    lines += ['', 'Os nomes docentes e postos existentes estão listados acima; não falta inventar novo professor ou estimar encargo. Para 8º C, os R$ 274,14 históricos continuam não aditivos. Não se pede decisão sobre a reserva do antigo 7º C nesta etapa.', '',
        '## Fechamento do mapa', '',
        f'- Total pendente inicial = **R$ {money(TOTAL)}**.',
        f'- Total detalhado no mapa por bloco/turma = **R$ {money(sum(r["cents"] for r in rows))}**.',
        '- Diferença não explicada na soma = **R$ 0,00**.',
        '- Parcela ainda sem decomposição por conta analítica/beneficiário = **R$ 124.132,02 (100%)**. A conciliação aritmética não resolve essa pendência econômica. Não foi possível atribuir um valor comprovado do resíduo a cada nome/conta.', '',
        'Preservados: R$ 605.641,03 nas 41 turmas; 775 matriculados; capacidade 1.103; 328 vagas; reserva R$ 15.827,05; PE 33 do 2º C; PE 55 do 3º C; quotas nominais e todos os demais PEs vigentes. Nenhuma transferência aplicada.',
        'Verificação desta entrega: 33 saldos somados em centavos, sem repetição; nenhuma conta escolar de referência adicionada à soma; hashes do checkpoint, simulação anterior e backup iguais antes/depois. Sem novo teste de aplicação, pois só foram gerados estes documentos. Nenhum cálculo de PE, banco, deploy, push, publicação, remoto/Supabase ou produção.']
    data = dict(pendingInitialCents=TOTAL, detailedCents=sum(r['cents'] for r in rows), differenceCents=0,
        analyticalAccountUnresolvedCents=TOTAL, totals=totals, balancesDescending=rows,
        accountsReferenceOnly=accounts, hashes=hashes, noSimulation=True, noStateMutation=True)
    (OUT/'MAPA-PARA-DECISAO-HUMANA.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (OUT/'mapa-pendencias.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    print(json.dumps(dict(totals=totals, lines=len(rows), accounts=len(accounts), difference=0)))

if __name__ == '__main__':
    main()
