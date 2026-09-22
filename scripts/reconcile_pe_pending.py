"""Continuação documental do PE; não altera os valores nem artefatos homologados."""
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from pe_full_audit import full_cost_audit
from financial_integration import cents
from scripts.audit_full_pe_2027 import budget_accounts
from scripts.generate_approved_pe_2027_preview import money
from financial_integration import monthly_teaching_base_cents
from server import blank
from teaching_cost import load_documentary_costs

OUT=ROOT/'output/reconciliacao-pendencias-pe-2027'
SOURCES=OUT/'fontes'
COST_CODES={'90000','91032','91500','91510','91520','92000','94501','95006','95014','95015','72900','94202'}
NUMBER=r'\(?[\d.]+,\d{2}\)?'


def br_cents(value):
    return int(Decimal(value.replace('.','').replace(',','.').replace('(','-').replace(')',''))*100)


def payroll_records():
    """Lê a coluna Valor (a última), nunca Base/Percentagem/Total como salário."""
    people=[]; current=None; page=None
    for line in (SOURCES/'agosto-layout.txt').read_text(encoding='utf-8').splitlines():
        if line.startswith('PAGINA '):page=int(line.split()[-1])
        start=re.match(r'\s*Funcionario:\s*(\d+)\s+(.+?)\s*$',line)
        if start:
            current=dict(code=start[1],person=start[2],page=page,events=[])
            people.append(current);continue
        if current is None:continue
        total=re.match(r'\s*Total\s+(\d+)\s+(.+)$',line)
        if total:
            numbers=re.findall(NUMBER,total[2])
            current['printedEventCount']=int(total[1])
            current['printedTotalCents']=br_cents(numbers[-1])
            current=None;continue
        event=re.match(r'\s*(\d{5})\s+(.+?)\s+('+NUMBER+r'(?:\s+'+NUMBER+r'){5})\s*$',line)
        if event:
            nums=re.findall(NUMBER,event[3]);v=br_cents(nums[-1]);code=event[1]
            included=v>0 and (int(code)<15000 or code in COST_CODES)
            current['events'].append(dict(code=code,description=event[2],valueCents=v,page=page,
                                          includedInPriorEconomicBasis=included))
        elif re.match(r'\s*\d{5}\s',line):
            raise ValueError(f'Rubrica não interpretada na página {page}: {line}')
    for p in people:
        if len(p['events'])!=p['printedEventCount'] or sum(e['valueCents'] for e in p['events'])!=p['printedTotalCents']:
            raise ValueError(f'Folha não fecha: {p["person"]}')
        p['priorEconomicCostCents']=sum(e['valueCents'] for e in p['events'] if e['includedInPriorEconomicBasis'])
    if len({p['code'] for p in people})!=len(people):raise ValueError('Funcionário duplicado')
    return people


def classify(role,department):
    if department=='CAJ - Serviços de Apoio':return 'C27'
    if ('Coordena' in department or 'Orienta' in department or department=='Fundamental l') and any(s in role for s in ('Coordena','Orientador','Psic')):return 'C28'
    if 'Auxiliar de Classe' in role:return 'C29'
    if any(s in department for s in ('Secretaria Escolar','Tesouraria Escolar','Direção Escolar')):return 'C30'
    if 'Estagi' in role:return 'C02'
    return 'DOCENTE_OU_OUTRO'


def reconcile():
    audit=full_cost_audit()
    payroll=payroll_records();bycode={p['code']:p for p in payroll}
    roster=json.loads((SOURCES/'Planilha CAJ.xlsx.json').read_text(encoding='utf-8'))[0]['rows']
    people=[]
    for r in roster:
        cells=r['cells'];code=str(cells['1']);role=cells.get('3','');dept=cells.get('4','')
        p=bycode.get(code)
        people.append(dict(code=code,person=cells['2'],role=role,department=dept,
            classGroup=classify(role,dept),rosterCell=f'Sheet1!A{r["row"]}:D{r["row"]}',
            payrollPage=p['page'] if p else None,
            historicalCostCents=p['priorEconomicCostCents'] if p else None,
            status='BASE_AGOSTO_2026_NAO_E_FOLHA_ORCAMENTARIA_2027' if p else 'SEM_VERBAS_NA_FOLHA_AGOSTO'))
    groups={}
    for group in ('C27','C28','C29','C30','C02'):
        members=[p for p in people if p['classGroup']==group]
        groups[group]=dict(people=members,totalCents=sum(p['historicalCostCents'] or 0 for p in members),
                           missingCost=[p['code'] for p in members if p['historicalCostCents'] is None])
    # Recupera exatamente os controles administrativos da prévia aprovada.
    coord_admin=[p for p in groups['C28']['people'] if p['department'] in
                 ('CAJ - Coordenação Pedagógica','CAJ - Orientação Pedagógica')]
    known_admin=groups['C27']['totalCents']+groups['C30']['totalCents']+sum(p['historicalCostCents'] or 0 for p in coord_admin)
    institutional=cents(audit['summary']['institutionalAllocatedMonthly'])
    bridge=dict(institutionalEnvelopeCents=institutional,
        historicalAdministrativeControlsCents=known_admin,
        unbridgedDifferenceCents=institutional-known_admin,
        nominalBudget2027ReconciledCents=None,
        note='Controles históricos recuperados não comprovam inclusão nominal no orçamento 2027. Diferença não constitui nova despesa.',
        coordinationAdministrativePeople=coord_admin)
    paula=next(p for p in people if p['code']=='955')
    paula.update(confirmedClass='G3 B',additionalPosition=True,monthlyCostCents=None,
                 budgetInclusion='NAO_COMPROVADA',alreadyIncludedElsewhere='NAO_COMPROVADO',
                 addedExpenseCents=0,
                 reason='Cadastro prova existência/função; matrícula 955 não aparece entre os funcionários da folha de agosto.')
    g2=[]
    teaching={r['class_name']:r for r in load_documentary_costs(blank()['classes'])['classes']}
    for name in ('G2 A','G2 B'):
        r=next(r for r in audit['classes'] if r['class']==name)
        teacher=cents(r['teachingCostMonthly']);intern=cents(r['internsMonthly'])
        g2.append(dict(className=name,budgetPayrollCents=627193,teacherCapturedCents=teacher,
            payrollResidualCents=627193-teacher,budgetSupportCents=152000,internCapturedCents=intern,
            supportResidualCents=152000-intern,nominallyIdentifiedResidualCents=0,
            retentionBasis='ORCAMENTO_2027_P4_E_APROVACAO_C32',nature='COMPLEMENTO_ORCAMENTARIO_SEM_COMPOSICAO_NOMINAL',
            directEconomicEvidence=False,
            capturedTeachers=[dict(person=p['professor'],weeklyCents=cents(p['weekly_cost']),
                monthlyCents=monthly_teaching_base_cents(cents(p['weekly_cost']))) for p in teaching[name]['teacher_costs']],
            genericG2People=[p for p in people if p['department']=='CAJ - Grupo 2']))
    accounts={a['code']:a for a in budget_accounts()}
    discounts=[dict(accounts[code],economicNature='CONCESSAO_AO_ALUNO_REDUCAO_ECONOMICA_DA_RECEITA',
                    sourcePresentation='DESPESA_FINANCEIRA_NO_BALANCETE',
                    overlapWithStructural3Percent='NAO_COMPROVADO_POR_ALUNO_EVENTO',
                    futureRule='NAO_SOMAR_A_REDUCAO_REAL_QUE_REPRESENTE_O_MESMO_EVENTO')
               for code in ('4126005','4126007')]
    targets=[]
    for name in ('G2 A','G2 B','G4 B','G5 A','G5 B'):
        r=next(r for r in audit['classes'] if r['class']==name)
        components=[e for e in audit['expenseLedger'] if e['classId']==r['classId']]
        targets.append(dict(className=name,capacity=r['capacity'],ticketCents=cents(r['netTicket']),
            costCents=cents(r['totalCostMonthly']),capacityRevenueCents=cents(r['capacityRevenueMonthly']),
            deficitCents=-round(r['capacityResultMonthly']*100),pe=r['breakEvenStudents'],
            institutionalAllocationCents=cents(r['institutionalAllocationMonthly']),components=components,
            status='PE_ACIMA_DA_CAPACIDADE_NO_CENARIO_ATUAL_NAO_CERTIFICADO_COMO_CUSTO_REAL_DEFINITIVO'))
    tuition=[dict(segment=segment,tuitionCents=amount,source='Orçamento 2027 (1).pdf, página 2, linha Reajustado')
             for segment,amount in [('Educação Infantil',93069),('Fundamental I',96467),('Fundamental II',123981),
                                    ('Ensino Médio 1º/2º',142559),('Ensino Médio 3º',146105)]]
    return dict(status='PENDENCIAS_DOCUMENTAIS_PARCIALMENTE_ESCLARECIDAS',payroll=payroll,people=people,
                groups=groups,paula=paula,g2=g2,institutionalBridge=bridge,discounts=discounts,
                tuition=tuition,commercialDiscountRevenueAccount=accounts['3149026'],
                discountImportGate=dict(ready=False,reason='Cobertura das contas 4126005/4126007 por benefícios reais não demonstrada',
                    structuralDiscount='3% apenas no cenário estrutural; substituído pelo real na projeção',
                    reconciliation='Para cada evento: reconhecer uma vez como redução de receita OU despesa, nunca nos dois lados'),
                targetClasses=targets,fullAudit=audit,
                payrollTotals=dict(people=len(payroll),events=sum(len(p['events']) for p in payroll),
                                   printedTotalCents=sum(p['printedTotalCents'] for p in payroll)))


def nominal_report(data):
    lines=['# Memória nominal recuperada — agosto/2026', '',
        'Fonte cadastral: D:/Planilha CAJ.xlsx, Sheet1. Fonte de valores: D:/Relação CAJ - Agosto 2026.pdf. '
        'Valores abaixo reproduzem a base econômica da auditoria anterior C02/C27–C30, NÃO salários líquidos nem valores certificados de 2027. '
        'Não somar esta tabela ao PE. As rubricas individuais, inclusive excluídas, constam em reconciliacao.json.', '',
        '| Código | Funcionário | Função | Departamento comprovado | Base histórica/mês | Grupo | Células do cadastro | Página folha |',
        '|---|---|---|---|---:|---|---|---:|']
    for p in data['people']:
        lines.append(f"| {p['code']} | {p['person']} | {p['role']} | {p['department']} | {money(p['historicalCostCents'])} | {p['classGroup']} | {p['rosterCell']} | {p['payrollPage'] or 'ausente'} |")
    lines+=['','Romilton Silva da Costa (679) consta somente na folha, página 45, base histórica R$ 2.530,77. '
            'Não consta no cadastro atual e não foi reinserido na projeção. Jailane (952) substitui seu posto por confirmação do CAJ; '
            'o custo de Romilton não foi atribuído a Jailane por inferência. Veroneide (953) é posto adicional, sem verba comprovada na folha examinada.', '']
    return '\n'.join(lines)


def report(data):
    bridge=data['institutionalBridge'];audit=data['fullAudit'];s=audit['summary']
    lines=['# Continuação documental — pendências do PE 2027', '',
        '**PE 2027 AINDA NÃO FECHADO DOCUMENTALMENTE.** Nenhum valor homologado foi alterado. '
        'A investigação partiu da auditoria existente e recuperou os documentos originais no disco D:, cujo caminho estava registrado na tarefa anterior.', '',
        '## Evidências recuperadas e resultado', '',
        '- Folha de agosto/2026: **125 funcionários, 2.131 rubricas**; a soma algébrica de R$ 359.448,98 fecha com o total impresso. '
        'Esse total mistura proventos, descontos, provisões e imunidades; não é salário líquido nem custo econômico isolado.',
        '- Cadastro Planilha CAJ: **127 registros**. Os três sem rubricas na folha são Paula (955), Jailane (952) e Veroneide (953). '
        'Romilton (679) aparece na folha, mas não no cadastro atual. Não houve união automática de pessoas pelo posto.',
        '- Os três PDFs 2027 (1), (2) e (3) são cópias com SHA-256 idêntico. A versão sem sufixo também foi extraída e mantida como referência distinta; '
        'a fonte oficial adotada continua sendo a versão (1).',
        '- Foram recuperadas as aprovações C02/C27–C32 e conferidos os históricos 2024/2025 e a extração de abril/2026. '
        'O XLSM antigo contém bases de 2024; ele não comprova folha nominal de 2027. A planilha de descontos reais não foi aberta.', '',
        '## 1. Paula / G3 B', '',
        '| Informação | Resultado documental |', '|---|---|',
        '| Pessoa/código | Paula Araujo Dias, 955 |',
        '| Função/departamento | Estagiário(a), Educação Infantil — Planilha CAJ, Sheet1!A97:D97 |',
        '| Turma e posto | G3 B; adicional/vaga nova — confirmação do responsável, C02/C03 |',
        '| Início | Agosto/2026 conforme declaração anterior do responsável; não é comprovação de pagamento |',
        '| Custo mensal completo | Não localizado; nenhuma rubrica em nome/código 955 na folha de agosto |',
        '| Inclusão no orçamento | Não demonstrada nominalmente |',
        '| Já em outro bloco? | Não demonstrado. O saldo agregado de estágio não prova que inclui Paula |',
        '| Valor adicional lançado | R$ 0,00; custo continua desconhecido, não foi considerado gratuito |', '',
        'A conta 4119040 contém **R$ 17.759,48/mês** de serviços de estagiários. As 19 pessoas com valores comprovados na base usada pela prévia somam '
        '**R$ 14.895,91/mês**; a diferença aritmética de **R$ 2.863,57** não identifica Paula nem corresponde a seu salário. '
        'Não foi usada bolsa padrão de R$ 750 ou R$ 759. Quando seu custo for comprovado, será necessário demonstrar inclusão no envelope para escolher entre reclassificação e custo adicional.', '',
        '## 2. G2 A / G2 B — rastreamento', '',
        'Os complementos não surgiram da distribuição do saldo institucional desta execução. Eles vêm das linhas do orçamento 2027 (p. 4) '
        'e da decisão expressa C32 de preservá-los provisoriamente. O próprio orçamento usa 16 alunos em cada G2; isso explica a alocação igual de R$ 6.271,93, '
        'mas não prova que esse valor seja um conjunto nominal de custos exclusivos do G2. **Atribuição orçamentária e custo direto documental são coisas distintas.**', '',
        '| Turma | Rubrica/pessoa | Mensal | Origem e motivo de constar | Natureza/evidência |',
        '|---|---|---:|---|---|']
    for g in data['g2']:
        for p in g['capturedTeachers']:
            lines.append(f"| {g['className']} | {p['person']} | {money(p['monthlyCents'])} | Grade homologada × 4,5 | Direto/compartilhado conforme grade; já capturado, não incluir no residual |")
        name='Joyce dos Santos Pereira' if g['className']=='G2 A' else 'Larissa Lorrana Miranda de Jesus'
        lines += [f"| {g['className']} | {name} | R$ 838,35 | Bolsa + seguro + consultoria da folha; lotação aprovada | Direto; já capturado |",
            f"| {g['className']} | Complemento de folha/encargos, pessoa não identificada | {money(g['payrollResidualCents'])} | R$ 6.271,93 − {money(g['teacherCapturedCents'])}; orçamento p. 4 e C32 | Complemento orçamentário provisório; 0% nominalmente identificado |",
            f"| {g['className']} | Complemento de apoio, pessoa não identificada | {money(g['supportResidualCents'])} | R$ 1.520,00 − R$ 838,35; orçamento p. 4 | Apoio agregado preservado; sem prova de custo direto exclusivo |"]
    lines+=['', 'A diferença de R$ 23,13 entre os residuais é exatamente a diferença dos custos docentes. '
        'Não há prova de pessoas adicionais diferentes em cada turma. A classificação direta/compartilhada/institucional dos complementos não está documentalmente resolvida. '
        'Eles permanecem somente no cenário orçamentário provisório, por fonte e decisão anteriores, sem nova distribuição para forçar fechamento ou capacidade.', '',
        '| Pessoa vinculada genericamente ao Grupo 2 | Base completa de agosto | Evidência |',
        '|---|---:|---|']
    for p in data['g2'][0]['genericG2People']:
        lines.append(f"| {p['person']} | {money(p['historicalCostCents'])} | {p['rosterCell']}; folha p. {p['payrollPage']} — não distingue A/B |")
    lines+=['', 'Esses valores de agosto não foram somados às aulas já capturadas. Incluem outras verbas/atividades, sem ponte por seção para justificar qualquer parte dos residuais.', '',
        '## 3. Pessoal institucional', '',
        '| Composição recuperada como controle histórico | Valor mensal |', '|---|---:|',
        '| C27 — Serviços de Apoio, nominal na folha/cadastro | R$ 68.433,20 |',
        '| C28 — Coordenação/orientação administrativa, nominal | R$ 21.842,71 |',
        '| C30 — Secretaria/Tesouraria/Direção, nominal | R$ 25.275,88 |',
        '| Controles históricos somados | **R$ 115.551,79** |',
        '| Envelope institucional atualmente rateado | **R$ 202.296,04** |',
        '| Diferença ainda sem ponte nominal | **R$ 86.744,25** |', '',
        '**R$ 115.551,79 não significa que essa parcela do orçamento 2027 foi certificada nominalmente.** '
        'É o total dos controles de agosto que a prévia anterior já identificava como administrativos. '
        'Falta a ponte que demonstre quanto de cada pessoa/verba foi previsto em 2027, quais encargos foram absorvidos e quais parcelas já aparecem nas turmas.', '',
        'O envelope de R$ 202.296,04 é calculado por diferença: R$ 387.591,93 de pessoal menos R$ 185.295,89 já atribuídos '
        '(docentes, estágios, auxiliares, coordenação segmentada e complementos G2). Não existe uma conta de folha denominada “R$ 202.296,04” com esse rol de pessoas.', '',
        'A memória nominal completa com funcionário, função, departamento, valor, células e página está em **NOMINAL-AGOSTO.md**. '
        'A grade existente e os rateios aprovados permanecem intactos. Vínculos de segmento foram preservados; não foi inventada subturma.', '',
        '**Lohana:** código 516, Auxiliar de Coordenação, CAJ — Coordenação Pedagógica (Sheet1!A72:D72), folha p. 30. '
        'Base econômica histórica aprovada **R$ 2.746,13**, já contida nos R$ 21.842,71 de C28 administrativo; não acrescentada novamente. '
        'Os R$ 2.476,44 impressos em “Total” da folha não são seu custo econômico: incluem descontos pessoais e outra apresentação de provisões.', '',
        '**Marcelo Rodrigues:** não localizado como empregado na Planilha CAJ nem na folha de agosto; não projetado como professor, conforme decisão do CAJ. '
        'Não foi criada função administrativa ou remuneração para ele. Sua referência histórica na grade não comprova vínculo de trabalho 2027. '
        'Os postos de aula homologados foram mantidos sem atribuir a ele identidade docente futura.', '',
        'A base histórica segue a seleção de verbas já usada na auditoria anterior: remunerações positivas, encargos/benefícios selecionados e provisão 95015. '
        'Descontos pessoais não aumentam custo; 92200 não é somado novamente a 95015; bases informativas não são valores pagos. '
        'A folha contém rubricas de imunidade patronal; sua seleção no controle histórico não certifica desembolso nem autoriza adicioná-las novamente ao orçamento. '
        'A compatibilidade entre essa base, as isenções do orçamento e as projeções 2027 integra a ponte nominal pendente.', '',
        '## 4. Descontos no orçamento', '',
        '| Conta | Descrição | Mensal | Anual documental |', '|---|---|---:|---:|']
    for a in data['discounts']:
        lines.append(f"| {a['code']} | {a['description']} | {money(a['monthlyCents'])} | {money(a['annualCents'])} |")
    lines += ['| **Total** | | **R$ 177.901,08** | **R$ 2.134.812,90** |', '',
        'Origem: orçamento oficial, p. 14, conta sintética 4126000. A sintética não foi somada às duas analíticas. '
        '**Natureza comprovada pelo demonstrativo:** descontos concedidos apresentados contabilmente em despesas financeiras. '
        'Economicamente, são concessões que reduzem o recebimento; não compra adicional de recurso/serviço escolar. '
        'A natureza e os valores estão identificados; condições contratuais, alunos e eventos que os compõem não constam nesse demonstrativo.', '',
        'O desconto comercial já deduzido da receita está em **3149026 — (-) Descontos Incondicionais/Comercial**, '
        '**R$ 34.646,32/mês** e **R$ 415.755,85/ano** (p. 12). Portanto, não é correto afirmar só pelo nome “desconto” '
        'que os R$ 177.901,08 são integralmente o mesmo desconto estrutural de 3%. São contas distintas e não há memória por aluno/evento provando a interseção.', '',
        '**Regra para a próxima etapa:** o desconto real substituirá os 3% somente na projeção; inadimplência continuará uma vez. '
        'Qualquer parcela de 4126005/4126007 que corresponda aos mesmos eventos incluídos no ticket real deverá ser neutralizada/reclassificada no PE gerencial, '
        'preservando o orçamento oficial. Manter a despesa desses eventos e também deduzi-los integralmente do ticket seria dupla contagem. '
        'Sem comprovação da cobertura, a importação oficial continua bloqueada; nenhum valor foi retirado do PE por suposição.', '',
        '## 5. Mensalidades confirmadas', '',
        '| Segmento | Mensalidade 2027 | Fonte |', '|---|---:|---|']
    for t in data['tuition']:lines.append(f"| {t['segment']} | {money(t['tuitionCents'])} | {t['source']} |")
    lines+=['', 'Valores conferidos na tabela visual “Valores de Mensalidades”, coluna de cada segmento, linha “Reajustado”. '
        '**Fundamental II: R$ 1.239,81 confirmado.** Nenhuma mensalidade foi alterada.', '',
        '## 6. Cinco turmas — novo cálculo com os valores preservados', '',
        'Como nenhuma pendência trouxe evidência de valor substituto ou eliminação de parcela, o recálculo confirma os resultados anteriores. '
        'A capacidade e o ticket foram mantidos; não se usou a matrícula atual.', '',
        '| Turma | Cap. | Docentes | Estágio | Auxiliar direta | Compl. folha | Compl. apoio | Aux. segmento | Coord. | Gerais líquidos | Institucional | Custo total | Receita capacidade | Déficit | PE |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    keys=['docentes','estagiarias','auxiliar-direta','residual-g2','apoio-direto-g2','auxiliares-segmento','coordenacao-segmento','gerais-liquidos-pcld','pessoal-institucional']
    for t in data['targetClasses']:
        values={e['component']:e['monthlyCents'] for e in t['components']}
        cells=[t['className'],str(t['capacity'])]+[money(values[k]).replace('R$ ','') for k in keys]
        cells += [money(t['costCents']),money(t['capacityRevenueCents']),money(t['deficitCents']),str(t['pe'])]
        lines.append('| '+' | '.join(cells)+' |')
    lines+=['', 'O custo antes de atribuir o saldo institucional ainda cabia na receita de capacidade dessas cinco turmas. '
        'A parcela institucional acrescentada foi suficiente para ultrapassar a folga: G2 A/B recebem R$ 3.301,29 cada; '
        'G4 B R$ 4.768,54; G5 A R$ 3.851,51; G5 B R$ 3.301,29. '
        'Isso explica matematicamente a passagem acima da capacidade, sem provar que o rateio seja custo direto de cada turma.', '',
        '- G2 A/B: além do institucional, os complementos sem composição nominal somam R$ 4.555,98 e R$ 4.579,11. '
        'Esses valores exigem revisão da fonte, não atribuição a novas pessoas por algoritmo.',
        '- G4 B: R$ 2.638,43 de Maria Edna, R$ 1.555,74 de estágios e R$ 2.106,34 de auxiliares do segmento estão separados; '
        'a lotação exclusiva de Maria Edna permanece. O déficit aparece após somar R$ 4.768,54 institucionais.',
        '- G5 A/B: a grade docente de R$ 3.255,08 é igual e preservada; G5 A tem estágio de R$ 853,77 e 21 vagas, G5 B não tem estágio atribuído e tem 18 vagas. '
        'As parcelas de coordenação e capacidade explicam o restante. A inexistência de estágio atribuído não é inferência de necessidade zero.', '',
        '**Há inviabilidade física no cenário de custos atual**, mas não é possível certificá-la como inviabilidade definitiva do custo real '
        'enquanto os complementos, o pessoal institucional e a cobertura dos descontos não estiverem documentalmente conciliados. '
        'Não se alterou capacidade nem se reduziu custo para fazer o PE caber.', '',
        f"Totais mantidos: custo mensal {money(cents(s['managerialPETotalMonthly']))}; anual {money(cents(s['managerialAnnual']))};",
        f"rateios {money(cents(s['allocationsMonthly']))}; soma dos PEs 831; 41 turmas e 1.103 vagas.", '',
        '## 7. Validação e preservação', '',
        'Ver TESTES.md e integridade.json desta pasta. O relatório anterior, módulos homologados, dados locais e orçamento oficial foram preservados. '
        'Não houve deploy, push, conexão com Supabase remoto nem importação da planilha de descontos.', '',
        '## Lista única final — somente o que ainda falta', '',
        '1. **Demonstrativo de verbas/contrato de Paula (955) com custo mensal completo e indicação de inclusão no orçamento 2027.** '
        'Uso: preencher o posto adicional G3 B e decidir entre reclassificar valor já previsto ou acrescentar custo comprovadamente ausente.',
        '2. **Memória nominal de formação do pessoal no orçamento 2027, por funcionário, rubrica, centro de custo e turma quando existente**, '
        'incluindo os R$ 6.271,93 de folha e R$ 1.520,00 de apoio de cada G2, a passagem da folha agosto para 2027, '
        'Jailane (952) substituindo Romilton, Veroneide (953) como nova vaga e encargos/isenções. '
        'Uso: conciliar os complementos G2, confirmar quais parcelas dos R$ 115.551,79 históricos pertencem ao orçamento e explicar os R$ 86.744,25 restantes do envelope institucional, sem duplicar pessoas/encargos.',
        '3. **Memória das contas 4126005 e 4126007 por tipo de benefício/evento e sua relação com 3149026 e os descontos reais por aluno.** '
        'Uso: identificar cobertura e valor a neutralizar no PE gerencial quando esses mesmos benefícios reduzirem o ticket; impedir dupla contagem na futura importação.', '']
    return '\n'.join(lines)


def main():
    result=reconcile()
    (OUT/'reconciliacao.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'RELATORIO.md').write_text(report(result),encoding='utf-8')
    (OUT/'NOMINAL-AGOSTO.md').write_text(nominal_report(result),encoding='utf-8')
    print(json.dumps(dict(payroll=result['payrollTotals'],groups={k:(v['totalCents'],v['missingCost']) for k,v in result['groups'].items()},
                         bridge=result['institutionalBridge']),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
