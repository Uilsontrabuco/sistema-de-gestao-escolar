"""Investigação dirigida, somente leitura das bases; não promove custos parciais."""
import json,sys,hashlib
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pe_real import money
OUT=ROOT/'output/desbloqueio-pe-2027'
TARGETS=('1º D','2º D','3º D','8º C')
ADMINISTRATIVE_ROLES={
    'Lohana Rodrigues Leite da Silva': dict(role='Auxiliar administrativo',payrollMembershipConfirmed=True,
        source='Correção direta do usuário em 22/09/2026; função atual supera descrição anterior de Auxiliar de Coordenação'),
    'Marcelo Rodrigues': dict(role=None,payrollMembershipConfirmed=True,
        source='Confirmação direta do usuário em 22/09/2026: integra a folha; função específica e valor não informados'),
}
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def br(c):return 'NÃO DETERMINADO' if c is None else f'{Decimal(str(c))/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')

def investigate(report,layers,teaching,ledger):
    result=[];occ={o['occurrence_id']:o for o in teaching['occurrences']}
    for name in TARGETS:
        row=next(r for r in report['rows'] if r['name']==name)
        source=next(r for r in layers['rows'] if r['name']==name)
        teacher=next(r for r in teaching['classes'] if r['class_name']==name)
        weekly=money(Decimal(str(teacher['weekly_cost']))*100)
        assert money(Decimal(weekly)*Decimal('4.5'))==row['teacherCents']
        assert sum(money(Decimal(str(t['weekly_cost']))*100) for t in teacher['teacher_costs'])==weekly
        entries=[]
        for t in teacher['teacher_costs']:
            ids=t.get('occurrence_ids',[])
            entries.append(dict(name=t['professor'],lessons=t['weekly_lesson_equivalents'],
                weeklyCents=money(Decimal(str(t['weekly_cost']))*100),
                monthlyExactCents=str(Decimal(str(t['weekly_cost']))*450),
                disciplines=t['disciplines'],occurrences=ids,pages=sorted({occ[i]['page'] for i in ids if i in occ}),
                sharedIds=t.get('shared_occurrence_ids',[]),source=t.get('evidence'),
                currentTeacherExcluded=t['professor'] in ADMINISTRATIVE_ROLES,
                administrativeConfirmation=ADMINISTRATIVE_ROLES.get(t['professor'])))
        peers=[]
        for p in report['rows']:
            if p['name'].split()[0]!=name.split()[0]:continue
            tc=next(t for t in teaching['classes'] if t['class_id']==p['id'])
            common=sorted({i for t in entries for i in t['sharedIds']} & {i for t in tc['teacher_costs'] for i in t.get('shared_occurrence_ids',[])})
            peers.append(dict(name=p['name'],teacherCents=p['teacherCents'],costCents=p['consideredCostCents'],
                supportCents=p.get('costBridge',{}).get('supportCents'),
                generalNetCents=(p['costBridge']['generalCents']-p['costBridge']['pcldRemovedCents']-p['costBridge']['discountReclassifiedCents']) if p.get('costBridge') else None,
                sharedOccurrenceIds=common,weeklyMinutes=tc['weekly_minutes'],
                teacherNames=[t['professor'] for t in tc['teacher_costs']]))
        verified=[c for c in source['components'] if c['verified']]
        pending=[c for c in source['components'] if not c['verified'] and c['cents']]
        result.append(dict(name=name,id=row['id'],teachers=entries,weeklyCents=weekly,monthlyTeacherCents=row['teacherCents'],
            weeklyMinutes=teacher['weekly_minutes'],verifiedComponents=verified,legacyPendingComponents=pending,
            partialKnownCents=sum(c['cents'] for c in verified),legacyPendingSimulationCents=sum(c['cents'] for c in pending),
            integralCostCents=None,missingActualCostCents=None,canClose=False,pe=None,
            sourceDocument=source['document'],peers=peers,
            exactMissing='Vínculo das despesas destas unidades ao orçamento: parcela nominal de folha/apoio e participação comprovada nos serviços institucionais/gerais líquidos; origem da conta já orçada e compensação nas parcelas já distribuídas. Não falta tarifa docente nem multiplicador.',
            teacherRoleConflictCents=sum(money(Decimal(t['monthlyExactCents'])) for t in entries if t['currentTeacherExcluded'])))
    reserve=next(x for x in ledger['allocations'] if x['classId'] is None)
    assert reserve['costCents']==1582705
    assert sum(x['costCents'] for x in ledger['allocations'] if x['classId'])==60564103
    return dict(classes=result,reserve=reserve,sourceClassesUnchanged=True,administrativeRoles=ADMINISTRATIVE_ROLES,
                reserveIncludedInSchoolEnvelope=True,reserveIncludedInClassAllocation=False,
                reserveObligationStatus='SEM EVIDÊNCIA SUFICIENTE',newIntegralPECount=0)

def main():
    OUT.mkdir(exist_ok=True)
    paths=['output/pe-administrativo-aprovado-20270922/resultado-administrativo.json','pe_layers_2027_source.json',
           'output/desbloqueio-pe-2027/docencia-reconstruida.json','output/pe-real-2027/reconciliacao-custos.json']
    report,layers,teaching,ledger=[read(p) for p in paths]
    data=investigate(report,layers,teaching,ledger)
    data['sourceHashes']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    (OUT/'reconciliacao-forense.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# RELATÓRIO DE DESBLOQUEIO DO PE','',
    '**NO-GO mantido: 0 das 4 turmas pode ser fechada integralmente apenas com as evidências atuais.** Há componentes quantificados; o que falta é a ligação das quatro unidades com a distribuição do orçamento já consumido pelas demais turmas. Não faltam genericamente professores, tarifas ou o multiplicador. A exceção nominal específica do 8º C está detalhada abaixo.', '',
    'Escopo exclusivo: 1º D, 2º D, 3º D, 8º C e R$ 15.827,05. Preservados 41 turmas, 775 matriculados, capacidade 1.103, vagas 328, 8º C=20, salários ASG 1.690,50/44h, benefícios, taxas, custo e todos os PEs calculáveis. Nenhuma gravação operacional.', '',
    '## Resultado por turma','',
    '| Turma | Docência estrutural/mês | Componentes parciais já documentados | Simulação antiga NÃO comprovada | Custo integral / PE novo |',
    '|---|---:|---:|---:|---|']
    for c in data['classes']:lines.append(f"| {c['name']} | {br(c['monthlyTeacherCents'])} | {br(c['partialKnownCents'])} | {br(c['legacyPendingSimulationCents'])} | Não determinável / não calculado |")
    lines+=['', 'A coluna de simulação antiga não é o valor exato que falta hoje. Ela foi produzida por rateio genérico por capacidade e contém despesas cuja cobertura/identidade não foi demonstrada. Não se soma ao custo parcial nem à reserva. O valor monetário da parcela efetivamente ausente continua indeterminado; sua natureza e o vínculo faltante são identificados a seguir.',
    'Docência: reconstruída por load_documentary_costs a partir de output/auditoria-carga-horaria/extracao.json, mantendo as regras homologadas. Fonte primária: Carga Horária Oficial 2026 (projeção estrutural 2027); tarifas no Orçamento 2027 p.2: FI R$ 16,20 e FII R$ 26,11. Custo mensal = custo semanal já conciliado × 4,5, arredondado em centavos no total da turma. Frações e pools compartilhados explicam por que não se pode multiplicar um número aparente de aulas sem a memória do rateio.', '']
    labels={'docentes':'Docência estrutural','estagiarias':'Estágio direto','auxiliar-direta':'Auxiliar exclusiva','auxiliares-segmento':'Auxiliar do segmento','coordenacao-segmento':'Coordenação do segmento'}
    for c in data['classes']:
        lines += [f"## {c['name']}",'',
          'Orçamento p.4: '+('linha ausente para esta seção D.' if c['sourceDocument'] is None else '8º Ano C com zero alunos/receitas/despesas. Zero documental não comprova ausência de custo da turma atual ativa.'),'',
          '| Componente | Origem/evidência | Valor mensal R$ | Já contabilizado? | Faltante? | Tratamento recomendado |',
          '|---|---|---:|---|---|---|']
        for p in c['verifiedComponents']:
            note=p['evidence']
            if p['kind']=='estagiarias' and c['name']=='3º D':note='Sheila/881; relação OF, 3º D; folha agosto p.48: bolsa 759,00 + seguro 19,35 + consultoria 75,42'
            if p['kind']=='auxiliares-segmento' and p['cents']:note='Anny/773; cadastro C29/FI e folha agosto p.3; pool R$ 2.638,43 distribuído pela capacidade congelada FI'
            if p['kind']=='coordenacao-segmento' and p['cents']:note='Debora/846; cadastro C28/FI e folha agosto p.7; pool R$ 2.746,13 dividido igualmente entre as 18 turmas FI'
            lines.append(f"| {labels[p['kind']]} | {note} | {br(p['cents'])} | Na memória nominal; não como novo custo integral alocado | Não falta valor parcial; falta ponte no envelope | Preservar como composição, não adicionar ao orçamento |")
        lines += ['| Folha e apoio adicionais / cobertura dos itens nominais | Contas 411* e blocos p.4; sem vínculo desta turma | NÃO DETERMINADO | Envelope escolar já contém pessoal; destino individual não demonstrado | Sim: mapa conta→posto/serviço→turma e parcela já coberta | Identificar cobertura antes de somar |',
                  '| Serviços institucionais e gerais líquidos | P.4 apoio/gerais por receita; p.6–7 contas por segmento; ausência de peso financeiro válido para a turma | NÃO DETERMINADO | Distribuídos nas 37 linhas financeiras e reserva | Sim: participação comprovada e origem/compensação no rateio atual | Não criar peso por capacidade/matrícula nem copiar A/B/C |',
                  '| Encargos adicionais | Provisões e encargos já existentes nas contas de pessoal | NÃO DETERMINADO individualmente | Sim, no agregado orçamentário | Não há comprovação de encargo extra | Não estimar nem reaplicar |',
                  '| PCLD adicional | Conta 4124001 já neutralizada; ticket contém 4,5% | 0,00 aplicado | Exclusão já feita uma vez | Não | Não descontar nem somar novamente |','',
                  'Zeros de estágio/auxiliar na memória significam nenhum posto direto identificado nessa relação específica; não certificam custo integral zero de apoio institucional.', '',
                  '### Docência: autores históricos das ocorrências e valores estruturais','',
                  '| Autor na fonte / situação | Aulas equivalentes semanais na memória | Custo semanal R$ | Mensal de referência R$ | Página/ocorrências |',
                  '|---|---:|---:|---:|---|']
        for t in c['teachers']:
            source=('p. '+','.join(map(str,t['pages']))+'; '+','.join(t['occurrences'])) if t['pages'] else t['source']
            status=' — NÃO DOCENTE 2027; vínculo atual não informado' if t['currentTeacherExcluded'] else ''
            lines.append(f"| {t['name']}{status} | {t['lessons']:.6g} | {br(t['weeklyCents'])} | {br(t['monthlyExactCents'])} | {source} |")
        lines += ['', f"Total semanal {br(c['weeklyCents'])} × 4,5 = {br(c['monthlyTeacherCents'])}/mês. Minutos registrados: {c['weeklyMinutes']}. Complementos de regência expressos em h/a não criam minutos inexistentes na fonte. Valores mensais individuais arredondados são referência; o total é arredondado na turma.",'',
          '### Comparação com a mesma série','',
          '| Turma | Docência/mês R$ | Custo integral atual R$ | Apoio documental R$ | Gerais líquidos documentais R$ | Ocorrências compartilhadas com a turma auditada |',
          '|---|---:|---:|---:|---:|---|']
        for p in c['peers']:lines.append(f"| {p['name']} | {br(p['teacherCents'])} | {br(p['costCents'])} | {br(p['supportCents'])} | {br(p['generalNetCents'])} | {', '.join(p['sharedOccurrenceIds']) or 'Nenhuma coincidência de ocorrência compartilhada'} |")
        lines += ['', 'Mesmo professor não significa a mesma aula. Apenas identidades de ocorrências e pools já conciliados comprovam compartilhamento; suas parcelas já integram o custo docente e não foram reaproveitadas uma segunda vez. Auxiliares/coordenação seguem os pools nominais homologados, distintos do rateio financeiro de folha/apoio do orçamento.', '',
                  '**Parcela que impede fechar:** '+c['exactMissing']]
        for p in c['legacyPendingComponents']:lines.append(f"- Referência antiga não certificada: {p['kind']} = R$ {br(p['cents'])}; não é obrigação identificada nem autorização de inclusão.")
        if c['teacherRoleConflictCents']:
            lines += ['', f"**Vínculo adicional específico:** R$ {br(c['teacherRoleConflictCents'])}/mês de unidades estruturais históricas sob Lohana (O0731/O0732: R$ 234,99) e Marcelo (O0789: R$ 39,15). Lohana continua somente Auxiliar de Coordenação; Marcelo não é professor. A lista de 50 docentes foi corrigida no código, mas a matriz histórica conserva essas autorias. Falta indicar quem atende EDCF1 (2 h/a) e CUTG2 (fração 1/3) no 8º C em 2027, ou qual serviço substitui essas ocorrências, e onde seu custo já está coberto. Nenhum nome foi substituído por suposição; total estrutural preservado."]
        lines += ['', '**Os dados atuais permitem fechar sem nova informação? NÃO.** Docência e parcelas nominais conhecidas não determinam participação integral em serviços e no envelope orçamentário.','']
    r=data['reserve']
    lines += ['## Rastreamento da reserva R$ 15.827,05','',
      'Origem exclusiva no razão: 7º Ano C, orçamento p.4, FII, 27 alunos previstos. 22.094,01 impresso − 0,01 ajuste − 1.199,67 PCLD − 5.067,28 descontos = 15.827,05. Não existe 7º C ativo, conforme decisão administrativa já aprovada.', '',
      '| Parcela líquida | Valor R$ | Já aparece onde? | Classificação de obrigação/destino atual | Tratamento |',
      '|---|---:|---|---|---|',
      '| Folha | 5.748,45 | Dentro do envelope de pessoal escolar; 7º A/B possuem somente suas próprias parcelas 6.812,98 / 6.387,17 de folha | SEM EVIDÊNCIA SUFICIENTE: não identifica empregado, contrato ou obrigação remanescente | Não copiar nem distribuir |',
      '| Apoio | 3.416,95 | Dentro do pool escolar R$ 119.961,77; 7º A/B conservam 4.049,72 / 3.796,61 | SEM EVIDÊNCIA SUFICIENTE: conta/posto beneficiário não individualizado | Manter separado |',
      '| Gerais líquidos | 6.661,65 | Gerais 12.928,60 menos PCLD 1.199,67 e descontos 5.067,28; parte das contas institucionais da escola | SEM EVIDÊNCIA SUFICIENTE: contratos e consumo evitáveis/remanescentes não identificados por turma | Não declarar custo extinto nem ratear |',
      '| PCLD (ponte, não somar às parcelas líquidas) | 1.199,67 | Já neutralizada uma vez dentro de 42.117,80 | JÁ ABSORVIDA no ajuste econômico, não novo custo | Não reaplicar |',
      '| Descontos (ponte, não somar às parcelas líquidas) | 5.067,28 | Já retirados uma vez das contas 4126005/4126007 | JÁ ABSORVIDOS na reclassificação econômica | Não reaplicar |','',
      'Contabilidade do envelope não comprova obrigação econômica atual. Nenhuma das três parcelas líquidas pôde ser classificada como custo ainda existente ou custo extinto com segurança. Elas já estão no total escolar, mas NÃO absorvidas no custo alocado de 7º A/B ou outra turma: 605.641,03 + 15.827,05 = 621.468,08. Essa igualdade foi revalidada contra todas as alocações únicas. Não somar a reserva ao envelope de novo.',
      'Pessoal global: contas 411* = 387.591,93, composto de folha 267.630,16 + apoio 119.961,77. As páginas 6–7 rateiam contas por receita de segmento; a p.4 distribui folha por alunos previstos no segmento e apoio/gerais por receita bruta. Essa regra não oferece peso financeiro para D inexistente ou C zerado sem revisar a distribuição já aplicada nas demais turmas.', '',
      '## O que fornecer para desbloquear precisamente','',
      '1. **Um mapa de cobertura orçamentária das quatro turmas**: para cada uma, vincular a docência e os apoios nominais acima às contas/pools já orçados; identificar participação nos gerais e serviços institucionais e de qual parcela já distribuída sairá o valor. Alternativamente, comprovar que nenhum custo adicional existe e demonstrar onde está a cobertura. Não basta repetir um total de A/B/C ou aprovar soma por capacidade.',
      '2. **No mesmo mapa, vínculo 2027 das ocorrências EDCF1 e CUTG2 do 8º C** historicamente atribuídas a Lohana/Marcelo: responsável/serviço atual e cobertura de R$ 274,14 estruturais, sem cadastrá-los como docentes.',
      '3. **Para a reserva, detalhamento conta/posto/contrato de 5.748,45 de folha, 3.416,95 de apoio e 6.661,65 de gerais líquidos**, com indicação de continuidade, cobertura já existente ou encerramento. Pode integrar o mesmo mapa; não é necessário provar novamente que o 7º C foi extinto.', '',
      'Portanto, o principal dado ausente é a ponte de cobertura, não um novo salário, tarifa ou multiplicador. Há também o vínculo específico do 8º C; não seria correto afirmar que basta um único número. Os valores antigos não comprovados não são o saldo exato a financiar.', '',
      '## Preservação e resultado','',
      'Custos alocados antes/depois: R$ 605.641,03. Reserva antes/depois: R$ 15.827,05. Envelope R$ 621.468,08. Soma dos PEs calculáveis: 911; quatro PEs não determinados. Novos custos e exclusões: R$ 0,00. Nenhuma transferência, importação, alteração do motor, publicação, push, deploy, Supabase remoto ou produção.']
    lines=[line.replace('Lohana continua somente Auxiliar de Coordenação; Marcelo não é professor.',
        'Correção mais recente do usuário: Lohana é Auxiliar administrativo; Marcelo integra a folha e permanece não docente. A confirmação supera a pendência de existência de Marcelo na folha, mas não informa seu valor ou conta. Não criar salário adicional.')
        .replace('Falta indicar quem atende EDCF1 (2 h/a) e CUTG2 (fração 1/3) no 8º C em 2027, ou qual serviço substitui essas ocorrências, e onde seu custo já está coberto.',
        'Falta mapear a cobertura, na folha administrativa já existente, das unidades históricas EDCF1 (2 h/a) e CUTG2 (fração 1/3), e demonstrar se representam serviço compartilhado ou atribuição histórica a corrigir no 8º C. Não exigir nova confirmação de que Marcelo integra a folha; não converter as autorias históricas em docentes atuais.')
        .replace('responsável/serviço atual e cobertura de R$ 274,14 estruturais, sem cadastrá-los como docentes.',
        'cobertura na folha já existente e natureza do serviço correspondente aos R$ 274,14 estruturais, sem salário adicional e sem cadastrá-los como docentes.') for line in lines]
    (OUT/'RELATORIO-DE-DESBLOQUEIO-DO-PE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps([(r['name'],r['partialKnownCents'],r['legacyPendingSimulationCents'],r['teacherRoleConflictCents']) for r in data['classes']]))
if __name__=='__main__':main()
