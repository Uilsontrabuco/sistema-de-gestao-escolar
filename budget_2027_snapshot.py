"""Reconciliação estrutural do Orçamento Oficial CAJ 2027.

Fonte: Orçamento COLEGIO ADVENTISTA DE JUAZEIRO 2027 (1).pdf, páginas
4–7. O total mensal oficial é preservado; docentes e postos de estágio já
capturados diretamente são abatidos antes de qualquer rateio.
"""
from decimal import Decimal


SOURCE = 'Orçamento COLEGIO ADVENTISTA DE JUAZEIRO 2027 (1).pdf · páginas 4–7'
OFFICIAL_TOTAL_MONTHLY_CENTS = 84148696
OFFICIAL_TOTAL_ANNUAL_CENTS = 1009784357
TEACHING_CAPTURED_CENTS = 12267300
INTERNS_CAPTURED_CENTS = 1425000

# A página 4 fecha estes três blocos em R$ 841.486,97. O documento também
# apresenta o total oficial de R$ 841.486,96; o centavo é ajustado no maior
# bloco, de forma explícita e determinística.
BUDGET_COMPONENTS = (
    dict(id='payroll-class',expense='Folha de Pagamento / Encargos Pessoais',
         source_cents=26763016,captured_cents=TEACHING_CAPTURED_CENTS,
         rounding_adjustment_cents=0),
    dict(id='support-payroll',expense='Rateio Folha Apoio',
         source_cents=11996177,captured_cents=INTERNS_CAPTURED_CENTS,
         rounding_adjustment_cents=0),
    dict(id='general-expenses',expense='Despesas Gerais',
         source_cents=45389504,captured_cents=0,rounding_adjustment_cents=-1),
)

# A página 4 não apresenta apenas totais: ela atribui estes três blocos
# diretamente a cada linha de turma.  A auditoria do G2 deve, portanto,
# prevalecer sobre um rateio global por capacidade. Os valores abaixo são os
# valores brutos da própria linha; docente e estágio são abatidos depois para
# que cada custo apareça exatamente uma vez no PE.
DIRECT_CLASS_SOURCE_CENTS = {
    'G2 A': {'payroll-class': 627193, 'support-payroll': 152000,
             'general-expenses': 575116},
    'G2 B': {'payroll-class': 627193, 'support-payroll': 152000,
             'general-expenses': 575116},
}

DIRECT_CLASS_CAPTURED_CENTS = {
    'G2 A': {'payroll-class': 239760, 'support-payroll': 75000},
    'G2 B': {'payroll-class': 237447, 'support-payroll': 75000},
}


def _deterministic_allocation(total_cents, weighted_ids):
    """Distribui centavos pelo maior resto, com desempate pela ordem recebida."""
    if not isinstance(total_cents,int) or total_cents < 0:raise ValueError('Valor de rateio inválido')
    weights=[(str(key),int(weight)) for key,weight in weighted_ids]
    if not weights or any(weight<=0 for _,weight in weights):raise ValueError('Universo de rateio inválido')
    total_weight=sum(weight for _,weight in weights)
    raw=[Decimal(total_cents)*weight/total_weight for _,weight in weights]
    parts=[int(value) for value in raw]
    remainder=total_cents-sum(parts)
    order=sorted(range(len(raw)),key=lambda index:(raw[index]-parts[index],-index),reverse=True)
    for index in order[:remainder]:parts[index]+=1
    return {key:value for (key,_),value in zip(weights,parts)}


def allocate_by_capacity(total_cents, classes):
    return _deterministic_allocation(total_cents,((room['id'],room['capacity']) for room in classes))


def allocate_by_segment(total_cents, classes, stage):
    eligible=[room for room in classes if room['stage']==stage]
    return _deterministic_allocation(total_cents,((room['id'],room['capacity']) for room in eligible))


def allocate_per_class(total_cents, classes):
    return _deterministic_allocation(total_cents,((room['id'],1) for room in classes))


def structural_budget_allocation(classes, teaching_cents, intern_cents, official_total_cents):
    if len(classes)!=41:raise ValueError('Orçamento estrutural exige exatamente 41 turmas')
    if teaching_cents!=TEACHING_CAPTURED_CENTS:raise ValueError('Docentes capturados divergem da reconciliação oficial')
    if intern_cents!=INTERNS_CAPTURED_CENTS:raise ValueError('Estagiárias capturadas divergem da reconciliação oficial')
    if official_total_cents!=OFFICIAL_TOTAL_MONTHLY_CENTS:raise ValueError('Total mensal não corresponde ao Orçamento Oficial 2027')
    rows={str(room['id']):{'shared':0,'details':[]} for room in classes}
    distributed=0
    for component in BUDGET_COMPONENTS:
        distributable=component['source_cents']-component['captured_cents']+component['rounding_adjustment_cents']
        direct={}
        for room in classes:
            name=room['name']
            if name not in DIRECT_CLASS_SOURCE_CENTS:continue
            source_value=DIRECT_CLASS_SOURCE_CENTS[name][component['id']]
            captured=DIRECT_CLASS_CAPTURED_CENTS.get(name,{}).get(component['id'],0)
            assigned=source_value-captured
            if assigned < 0:raise ValueError('Captura direta excede a rubrica oficial da turma')
            direct[str(room['id'])]=assigned
        remaining=[room for room in classes if str(room['id']) not in direct]
        balance=distributable-sum(direct.values())
        if balance < 0:raise ValueError('Alocações diretas excedem o bloco oficial')
        allocations=allocate_by_capacity(balance,remaining)
        allocations.update(direct)
        if sum(allocations.values())!=distributable:raise ValueError('Rateio estrutural não fecha')
        capacity_total=sum(room['capacity'] for room in remaining)
        for room in classes:
            target=str(room['id']);assigned=allocations[target]
            is_direct=target in direct
            rows[target]['shared']+=assigned
            rows[target]['details'].append(dict(
                id=component['id'],expense=component['expense'],
                originalMonthly=component['source_cents']/100,
                capturedDirect=component['captured_cents']/100,
                roundingAdjustment=component['rounding_adjustment_cents']/100,
                distributableMonthly=distributable/100,
                criterion=('ALOCACAO_DIRETA_ORCAMENTO_OFICIAL' if is_direct else
                           'CAPACIDADE_ESTRUTURAL_SALDO_APOS_ALOCACOES_DIRETAS'),
                universeClasses=(1 if is_direct else len(remaining)),
                weight=(1 if is_direct else room['capacity']/capacity_total),
                sourceClassMonthly=(DIRECT_CLASS_SOURCE_CENTS[room['name']][component['id']]/100
                                    if is_direct else None),
                capturedInClass=(DIRECT_CLASS_CAPTURED_CENTS.get(room['name'],{}).get(component['id'],0)/100
                                 if is_direct else 0),
                assignedValue=assigned/100,source=SOURCE))
        distributed+=distributable
    expected=official_total_cents-teaching_cents-intern_cents
    if distributed!=expected or sum(row['shared'] for row in rows.values())!=expected:
        raise ValueError('Reconciliação estrutural não fecha com o orçamento')
    return dict(status='RECONCILIADO',rows=rows,officialMonthly=official_total_cents/100,
        officialAnnual=OFFICIAL_TOTAL_ANNUAL_CENTS/100,teachingCaptured=teaching_cents/100,
        internsCaptured=intern_cents/100,fixedAssistantsCaptured=0,otherDirectCaptured=intern_cents/100,
        sharedDistributed=distributed/100,excluded=0,pending=0,roundingAdjustment=-0.01,
        difference=0,source=SOURCE,
        criteria=['ALOCACAO_DIRETA_ORCAMENTO_OFICIAL','CAPACIDADE_ESTRUTURAL_SALDO_APOS_ALOCACOES_DIRETAS'],
        components=[dict(item) for item in BUDGET_COMPONENTS])
