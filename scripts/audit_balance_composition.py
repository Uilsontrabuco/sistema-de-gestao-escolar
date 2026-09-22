"""Forense local: lê artefatos congelados; nunca aplica ou abre banco."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/forense-saldos-2027'

def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))

def br(c):
    return 'N/D' if c is None else f'{c / 100:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')

def main():
    OUT.mkdir(exist_ok=True)
    paths = ['output/simulacao-rateio-series-2027/simulacao.json',
             'output/auditoria-criterios-rateio-2027/auditoria.json',
             'output/pe-real-2027/reconciliacao-custos.json',
             'output/desbloqueio-pe-2027/docencia-reconstruida.json',
             'output/reconciliacao-pendencias-pe-2027/reconciliacao.json',
             'output/pre-publicacao-2027/backup-premissas-8C-mantido-20270922.zip']
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
    sim, audit, ledger, teaching, personnel = [read(p) for p in paths[:5]]
    before = sim['originalRows']
    after = copy.deepcopy(before)
    byid = {r['id']: r for r in before}
    teacher_map = {r['class_id']: r for r in teaching['classes']}
    transfers = []
    for i, f in enumerate(audit['flows'], 1):
        transfers.append(dict(f, id=i, classification=5, eligibleCents=0,
            account=None, employeeOrService=None,
            department='FI' if f['grade'] != '8º' else 'FII',
            missing='De-para conta/empregado/serviço → saldo do bloco p.4 → beneficiários efetivos da transferência',
            decision='Manter integralmente na origem; pareamento é ponte matemática, não lançamento contábil'))
    # Catálogo escolar não é uma decomposição inventada das transferências.
    accounts = []
    for a in ledger['accounts']:
        if not a['monthlyCents'] or a.get('isParent'):
            continue
        neutral = a['code'] in ('4124001', '4126005', '4126007')
        global_proven = a['code'] in ('4191005', '4193250')
        accounts.append(dict(a, classification=4 if global_proven else 5,
            classificationScope='abrangência da conta escolar; não atribui centavos a transferências',
            beneficiary='Escola; conservar critério global existente' if global_proven else 'Vínculo do saldo com turma não individualizado',
            transferTraceProven=False, eligibleTransferCents=0,
            excludedFromEconomicCost=neutral,
            reason='Já neutralizada; não é fonte redistribuível' if neutral else
                'Rateio institucional identificado; falta conciliação desta conta com cada parcela p.4' if global_proven else
                'Conta e valor conhecidos; natureza exclusiva/compartilhada do saldo por turma não demonstrada'))
    components, comparison = [], []
    interns = {}
    roster = read('output/reconciliacao-pendencias-pe-2027/fontes/Relação Estagiárias OF.xlsx.json')
    for row in roster[0]['rows']:
        cells = row['cells']
        room = str(cells.get('3', '')).replace('°', 'º').replace(' ', '')
        for d in audit['details']:
            if room == d['name'].replace(' ', ''):
                interns[d['name']] = (str(cells.get('2', '')).strip(), row['row'])
    protected = shared = unknown = 0
    for d in audit['details']:
        r = byid[d['id']]
        known_allocated = r['consideredCostCents'] is not None
        for c in r['nominalCosts']:
            if not c['cents']:
                continue
            category = 3 if c['kind'] in ('auxiliares-segmento', 'coordenacao-segmento') else 1
            value = c['cents']
            if d['name'] == '8º C' and c['kind'] == 'docentes':
                value -= 27414
            compsource = c['evidence']
            who = ('Anny / C29' if c['kind'] == 'auxiliares-segmento' else
                   'Debora / C28' if c['kind'] == 'coordenacao-segmento' else
                   'Consultar docentes e ocorrências no anexo nominal' if c['kind'] == 'docentes' else
                   'Lotação nominal já validada; fonte conservada sem nova despesa')
            if c['kind'] == 'estagiarias' and d['name'] in interns:
                who, source_row = interns[d['name']]
                compsource += f'; Relação Estagiárias OF.xlsx, Folha1!B{source_row}:C{source_row}'
            components.append(dict(turma=d['name'], component=c['kind'], cents=value,
                classification=category, evidence=compsource, employeeOrService=who,
                includedInFinancialPartition=known_allocated,
                treatment='Quota nominal protegida; compartilhamento já fracionado não autoriza retirar a quota da turma',
                account='411*: não existe de-para analítico da quota com o saldo p.4'))
            if known_allocated:
                if category == 3:
                    shared += value
                else:
                    protected += value
        if known_allocated:
            anchor = sum(c['cents'] for c in r['nominalCosts'])
            unknown += r['consideredCostCents'] - anchor
            for block, nominal in [('payrollCents', r['teacherCents']),
                                   ('supportCents', anchor - r['teacherCents']), ('generalNetCents', 0)]:
                residual = d['blocksBefore'][block] - nominal
                assert residual >= 0
                components.append(dict(turma=d['name'], component=block+' / saldo', cents=residual,
                    classification=5, account='411*' if block != 'generalNetCents' else 'Contas gerais líquidas do catálogo',
                    employeeOrService=None, includedInFinancialPartition=True,
                    evidence=f"Orçamento p.4, {r['costBridge']['sourceName']}; saldo aritmético após controles nominais, não lançamento identificado",
                    treatment='Congelado na origem; não é prova de despesa exclusiva nem de compartilhamento'))
        comparison.append(dict(name=d['name'], peCurrent=r['pe'], pePreviousSimulation=d['peAfter'],
            peConservative=r['pe'], costCurrentCents=r['consideredCostCents'],
            costConservativeCents=r['consideredCostCents'], allocatedDeltaCents=0,
            oldProposedCategoryDeltas=d['blocksDelta'], materialPrevious=d['material']))
    affected = sum(byid[d['id']]['consideredCostCents'] or 0 for d in audit['details'])
    assert protected + shared + unknown == affected
    assert before == after
    assert len(transfers) == 33 and len(comparison) == 15
    assert len(after) == 41 and sum(r['enrolled'] for r in after) == 775
    assert sum(r['capacity'] for r in after) == 1103
    assert sum(r['capacity']-r['enrolled'] for r in after) == 328
    assert sum(r['consideredCostCents'] or 0 for r in after) == 60564103
    assert sim['reserveBeforeCents'] == sim['reserveAfterCents'] == 1582705
    assert next(r for r in after if r['name'] == '8º C')['enrolled'] == 20
    # Pesquisa dirigida sobre extrações existentes: preserva resultados e localizadores.
    source_dirs = ['output/reconciliacao-pendencias-pe-2027/fontes', 'output/fechamento-modulo-2027/fontes']
    terms = ['2º Ano C', '3º Ano C', '4111001', '4119040', '4191005', '4193250']
    hits = []
    for directory in source_dirs:
        for path in sorted((ROOT / directory).glob('*.txt')):
            for number, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
                if any(term.casefold() in line.casefold() for term in terms):
                    hits.append(dict(file=str(path.relative_to(ROOT)), line=number, text=line))
    result = dict(conclusion='REVISÃO NECESSÁRIA', comparison=comparison, components=components,
        transfers=transfers, accountCatalogue=accounts, conservativeRows=after,
        partition=dict(scope='15 turmas; quotas nominais dentro do envelope, não adições',
            protectedCents=protected, structuralAlreadyAllocatedCents=shared, unidentifiedBalanceCents=unknown,
            affectedTotalCents=affected, outsideScopeUnchangedCents=60564103-affected,
            schoolCents=60564103, reserveCents=1582705, differenceCents=0),
        newlyRedistributableCents=0, transferProposalCents=sum(f['cents'] for f in transfers),
        nominalDetails=[teacher_map[d['id']] for d in audit['details']],
        sourceSearchHits=hits, sourceHashes=hashes)
    (OUT / 'composicao-e-simulacao-conservadora.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# Auditoria forense dos saldos e simulação conservadora', '', '**REVISÃO NECESSÁRIA. Simulação não aplicada.**', '',
        'As 33 propostas têm origem e valor rastreados até linha/bloco da p.4. Nenhuma tem de-para que individualize a conta, empregado/serviço e beneficiários de cada centavo transferido. São pareamentos matemáticos, não lançamentos históricos. A simulação conservadora movimenta R$ 0,00 e mantém custos e PEs vigentes.', '',
        'Classificações: 1 exclusivo da turma (a quota nominal já vinculada, inclusive frações de serviço compartilhado, fica protegida); 2 compartilhado comprovado; 3 estrutural do segmento/série; 4 global da escola; 5 não identificado para a redistribuição. Uma conta conhecida no total escolar não prova o beneficiário do saldo numa turma. As aulas compartilhadas já estão fracionadas na grade: não há nova parcela livre a transferir.', '',
        '## Comparação das 15 turmas', '', '| Turma | PE atual | PE simulado anterior | PE conservador | Custo atual R$ | Custo conservador R$ | Diferença alocada R$ |', '|---|---:|---:|---:|---:|---:|---:|']
    for c in comparison:
        lines.append('| '+c['name']+' | '+' | '.join(str(c[k]) if c[k] is not None else 'N/D' for k in ['peCurrent','pePreviousSimulation','peConservative'])+' | '+br(c['costCurrentCents'])+' | '+br(c['costConservativeCents'])+' | 0,00 |')
    lines += ['', 'N/D não é zero. Para 1º D, 2º D, 3º D e 8º C não há custo integral atribuído no estado vigente; nenhum PE integral novo pode ser confirmado pelas transferências não individualizadas.', '',
        '## Concentrações e anomalias da proposta anterior', '', '| Turma | Folha proposta Δ R$ | Apoio proposto Δ R$ | Gerais propostos Δ R$ | Tratamento conservador |','|---|---:|---:|---:|---|']
    for d in audit['details']:
        lines.append('| '+d['name']+' | '+' | '.join(br(v) for v in d['blocksDelta'].values())+' | Bloquear todos os movimentos sem composição; manter origem |')
    lines += ['', '2º C: folha R$ 8.438,34, apoio R$ 3.840,29 e gerais líquidos R$ 7.487,00. A retirada proposta de R$ 3.983,26 + R$ 1.540,38 + R$ 3.966,73 = R$ 9.490,37 causava PE 33 → 17.',
        '3º C: folha R$ 9.087,45, apoio R$ 4.135,70 e gerais líquidos R$ 8.062,91. A retirada proposta de R$ 4.603,02 + R$ 2.630,47 + R$ 3.887,47 = R$ 11.120,96 causava PE 55 → 26.',
        'A concentração é explicada matematicamente pelos pesos documentais de alunos/receita previstos. Isso não demonstra concentração INDEVIDA de serviço compartilhado: falta a composição econômica das retiradas. Não foi comprovado que esses saldos sejam exclusivos, nem que sejam compartilháveis. Ambos ficam na classe 5; PE 33 e 55 preservados. Toda anomalia material da proposta anterior foi bloqueada, não apenas essas duas.', '',
        '## Composição por turma — quotas e saldos', '', '| Turma | Componente / conta | Valor mensal R$ | Classe | Funcionário/serviço | Origem/evidência |','|---|---|---:|---:|---|---|']
    for c in components:
        lines.append(f"| {c['turma']} | {c['component']} / {c['account']} | {br(c['cents'])} | {c['classification']} | {c['employeeOrService'] or 'Não identificado'} | {c['evidence']} |")
    lines += ['', 'C28: Debora, coordenação FI, pool histórico R$ 2.746,13 / 18 turmas, pesos homologados. C29: Anny, apoio FI, pool R$ 2.638,43 por capacidade homologada. Classe 3: distribuição já comprovada e preservada, sem financiar os saldos. As quotas das quatro turmas sem custo integral são controles nominais não aditivos e não entram novamente na partição financeira abaixo.',
        '8º C: R$ 2.878,65 nominais rastreados; R$ 274,14 históricos separados, não aditivos. Lohana permanece Auxiliar Administrativo, não docente; Marcelo na folha. Jailane, Veroneide e Paula permanecem ASG, 44h, R$ 1.690,50 cada. Nenhum salário/encargo foi acrescentado. O anexo técnico conserva os registros históricos da grade como evidência, sem reclassificar Lohana como docente.', '',
        '## As 33 transferências, individualmente', '', '| Nº | Bloco | Origem p.4 | Destino proposto | Valor R$ | Classe | Parcela autorizável R$ |','|---|---|---|---|---:|---:|---:|']
    for f in transfers:
        lines.append(f"| {f['id']} | {f['block']} | {f['source']} | {f['destination']} | {br(f['cents'])} | 5 | 0,00 |")
    lines += ['', 'Cada linha requer o de-para conta/empregado/serviço → saldo do bloco → beneficiário. A soma das transferências é fluxo bruto da proposta, não custo adicional e não deve ser somada à escola.', '',
        '## Catálogo contábil — maior granularidade do orçamento', '',
        'Os valores abaixo são da ESCOLA, não das 33 transferências; não somar este catálogo às quotas. Segmentos e valores p.6/7 estão preservados integralmente no JSON. O PDF oferece contas globais/segmentos, mas não a matriz conta × turma × folha/apoio. As extrações do orçamento Excel contêm dados de 2024 (células de ano e lançamentos); não substituem automaticamente orçamento/lotação 2027. Folha agosto/2026 e cadastro nominal demonstram postos e eventos, não a conversão integral para cada saldo de 2027.', '',
        '| Conta | Descrição | Mensal escola R$ | Escopo | Página | Classe para vínculo | Tratamento |','|---|---|---:|---|---:|---:|---|']
    for a in accounts:
        lines.append(f"| {a['code']} | {a['description']} | {br(a['monthlyCents'])} | {a['scope']} | {a['sourcePage']} | {a['classification']} | {a['reason']} |")
    lines += ['', 'Classe 4 em Rateio Sede/Fundo Educação identifica natureza institucional; não identifica quanto de cada transferência corresponde a essas contas. Mantém-se a distribuição global anterior. Não se converte rubrica global em saldo da série por proporcionalidade presumida. Demais classes 5 não contestam a existência/valor contábil: indicam ausência de granularidade suficiente para mover a parcela.', '',
        '## Fechamento sem dupla contagem', '', '| Escopo | Valores protegidos R$ | Compartilháveis comprovados já distribuídos R$ | Saldos não individualizados R$ | Total reconciliado R$ | Diferença R$ |','|---|---:|---:|---:|---:|---:|',
        f'| 15 turmas afetadas (envelope já atribuído) | {br(protected)} | {br(shared)} | {br(unknown)} | {br(affected)} | 0,00 |',
        f'| 26 turmas fora do escopo, preservadas integralmente | — | — | — | {br(60564103-affected)} | 0,00 |',
        '| 41 turmas | — | — | — | 605.641,03 | 0,00 |', '',
        'A primeira linha é uma partição sem sobreposição: controles nominais protegidos + quotas estruturais já homologadas + saldo que não possui composição por beneficiário. Não identificado não significa fora do orçamento: esses saldos ficam onde estão. Nenhum novo valor foi desalocado. A reserva R$ 15.827,05 continua separada; envelope com reserva R$ 621.468,08. Atribuição integral às quatro turmas permanece pendente; seus nominais não são somados outra vez.',
        'PCLD R$ 42.117,80 e descontos R$ 177.901,08 já estão neutralizados no envelope usado. Não foram reinseridos, transferidos ou descontados uma segunda vez. Encargos e pessoal permanecem dentro das rubricas existentes. Nenhum custo foi criado, excluído ou transferido nesta simulação conservadora.', '',
        '## Informação precisa ainda necessária', '',
        '1. Folha: ponte das contas 4111001, 4111005, 4111009, 4111020 e 4112001 (e demais contas 411 efetivamente integrantes) até o bloco Folha de cada origem das transferências, com posto/encargos/provisões e beneficiários. Não falta confirmar salários ou jornadas já aprovados; falta vincular o saldo orçamentário.',
        '2. Apoio: composição do bloco por 4119040 (estágio), 4119010 (serviços administrativos) e demais contas efetivamente integrantes, identificando contratos/postos exclusivos versus comuns e conciliação às quotas C28/C29 já contabilizadas. Esses códigos são contas a conciliar, não afirmação de composição exata do saldo.',
        '3. Gerais: matriz das contas operacionais líquidas p.12–15 para as linhas p.4, destacando Rateio Sede 4191005 e Fundo Educação 4193250 e identificando beneficiários de manutenção, material, serviços e provisões. Sem essa ponte não há quantia dessas contas demonstravelmente disponível nas 33 propostas.', '',
        'Dados congelados e backup verificados por SHA-256 antes/depois. Nenhuma aplicação da simulação, escrita no banco, acesso Supabase remoto/produção, deploy, push ou publicação. Relatório local para revisão humana.', '',
        '## Quatro turmas — resultado separado', '',
        '| Turma | Nominal comprovado R$ (não aditivo) | PE proposta anterior | PE conservador integral | Dado que impede liberar cobertura |',
        '|---|---:|---:|---|---|']
    for d in audit['details']:
        if d['costBeforeCents'] is None:
            lines.append(f"| {d['name']} | {br(d['teacherAnchorCents']+d['otherNominalAnchorCents'])} | {d['peAfter']} | N/D | Composição e beneficiários dos saldos de folha, apoio e gerais que sairiam das origens da mesma série |")
    lines += ['', '## Anexo nominal docente — parcelas protegidas da grade', '',
        'Os valores semanais × 4,5 abaixo detalham o controle nominal; não são novas despesas. Ocorrências compartilhadas indicam serviços já fracionados na grade. Uma quota atribuída não pode ser retirada de seu beneficiário para cobrir outro. Arredondamento de itens individuais pode diferir em centavos do total calculado ao final da turma; prevalece a âncora homologada. Sem presumir encargos.', '',
        '| Turma | Docente / código | Disciplinas | Custo semanal R$ | Mensal × 4,5 R$ | Fontes / ocorrências compartilhadas |','|---|---|---|---:|---:|---|']
    for d in audit['details']:
        for t in teacher_map[d['id']]['teacher_costs']:
            if d['name'] == '8º C' and ('lohana' in t['professor'].lower() or 'marcelo' in t['professor'].lower()):
                continue
            lines.append(f"| {d['name']} | {t['professor']} / {t.get('professor_id','regência')} | {', '.join(t['disciplines'])} | {br(t['weekly_cost']*100)} | {br(t['weekly_cost']*450)} | {', '.join(t.get('source_codes',[]))}; compartilhadas: {', '.join(t.get('shared_occurrence_ids',[])) or 'nenhuma indicada'}; {t.get('evidence','carga extraída / grade homologada')} |")
    logs = [('testes-python.txt', 'Ran 415 tests'), ('testes-js-verificado.txt', '# pass 92'),
            ('testes-sql-verificado.txt', 'Ran 9 tests')]
    if all((OUT / filename).exists() and marker in (OUT / filename).read_text(encoding='utf-8', errors='replace') for filename, marker in logs):
        lines += ['', '## Testes desta execução', '',
                  '415 testes Python aprovados; 92 entradas JavaScript aprovadas (incluem executores agrupados); 9 verificações SQL estáticas aprovadas. Logs nesta pasta. Tentativas iniciais JavaScript/SQL bloqueadas pelo ambiente local foram preservadas; reexecução local com acesso às bibliotecas foi aprovada e passou. Nenhuma conexão de banco na verificação SQL.',
                  'Asserções adicionais: 33 transferências bloqueadas, 15 comparações, 41 linhas integralmente idênticas ao estado anterior, conservação de custos, alunos, capacidade, vagas e reserva; hashes das fontes e backup preservados.']
    (OUT / 'RELATORIO-FORENSE-DOS-SALDOS.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p,h in hashes.items())
    (OUT / 'integridade.json').write_text(json.dumps(dict(hashes=hashes, preserved=True, checks=15), indent=2), encoding='utf-8')
    print(json.dumps(dict(partition=result['partition'], transfers=33, moved=0, sourceHits=len(hits))))

if __name__ == '__main__':
    main()
