"""Decompõe o orçamento e reproduz seus critérios, sem criar lotação nominal."""
import sys,json,re
from pathlib import Path
from decimal import Decimal
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pe_real import AUDIT, money, normalized, ceil_ratio
from scripts.audit_full_pe_2027 import budget_accounts, amount
from scripts.audit_pe_real import br, write


def allocation(total, weights):
    sign=1 if total>=0 else -1
    total=abs(total);den=sum(Decimal(str(w)) for _,w in weights)
    raw=[Decimal(total)*Decimal(str(w))/den for _,w in weights]
    parts=[int(x) for x in raw]
    for i in sorted(range(len(raw)),key=lambda i:(raw[i]-parts[i],-i),reverse=True)[:total-sum(parts)]:parts[i]+=1
    return {k:sign*v for (k,_),v in zip(weights,parts)}


def segment(name):
    if name.startswith('Grupo'):return 'EI'
    if 'Médio' in name:return 'EM3' if name.startswith('3') else 'EM12'
    return 'FI' if int(name.split('º')[0])<=5 else 'FII'


def reconcile():
    source=ROOT/'output/reconciliacao-pendencias-pe-2027/fontes/Orçamento COLEGIO ADVENTISTA DE JUAZEIRO 2027 (1).pdf.txt'
    text=source.read_text(encoding='utf-8')
    raw=text.split('PÁGINA 6\n')[1].split('PÁGINA 8\n')[0]
    source_rates=[]
    for line in raw.splitlines():
        nums=re.findall(r'-?[\d.]+,\d{2}',line)
        if len(nums)==8:
            source_rates.append(dict(label=line[:line.index(nums[0])].strip(),values=[amount(x) for x in nums]))
    income=[212196317,478091344,482037972,160806462,77143276]
    students=[190,413,324,94,44]
    segments=['EI','FI','FII','EM12','EM3']
    accounts=[a for a in budget_accounts() if not a['isParent'] and a['code'].startswith('4')]
    ledger=[]
    for a in accounts:
        # Valor idêntico sozinho não basta para identificar uma conta.
        candidates=[x for x in source_rates if x['values'][1]==a['annualCents'] and
            (normalized(a['description'])==normalized(x['label']) or
             normalized(a['description']).replace('PROVISAO ','').replace('P/ ','').replace('PROV. ','')==normalized(x['label']).replace('PROVISAO ','').replace('P/ ','').replace('PROV. ',''))]
        test={}
        if candidates:
            v=candidates[0]['values']
            for name,weights in [('receita_prevista',income),('alunos_previstos',students)]:
                test[name]=float(max(abs(Decimal(v[1])*w/sum(weights)-actual) for w,actual in zip(weights,v[2:7])))
        matched=bool(test) and test['receita_prevista']<=1
        personnel=a['code'].startswith('411')
        rule='RECEITA_PREVISTA_SEGMENTO_P6_7' if matched else ('SEM_VALOR' if not a['monthlyCents'] else 'BLOCO_GERAL_P4' if not personnel else 'PENDENTE')
        distribution=allocation(a['monthlyCents'],list(zip(segments,income))) if matched else None
        treatment='CUSTO_ORCADO_COMPROVADO'
        if a['code']=='4124001':treatment='PCLD_NEUTRALIZADA_UMA_VEZ'
        if a['code'] in ('4126005','4126007'):treatment='ESTIMATIVA_DE_DESCONTOS_SUBSTITUIDA_PELA_BASE_INDIVIDUAL'
        ledger.append(a | dict(scope='PESSOAL_ESCOLA' if personnel else 'INSTITUCIONAL_ESCOLA',
            criterion=rule,criterionTestMaximumAnnualCents=test,segmentAllocationCents=distribution,
            sourceRateRow=candidates[0]['label'] if candidates else None,
            treatment=treatment,status='VALOR_COMPROVADO; CRITERIO '+rule,
            classAllocation='Folha: bloco documental p.4, composição por pessoa NÃO inventada. Gerais: receita bruta por turma p.4.'))
    assert sum(a['monthlyCents'] for a in ledger if a['code'].startswith('411'))==38759193
    assert sum(a['monthlyCents'] for a in ledger if not a['code'].startswith('411'))==45389507
    documentary=json.loads((ROOT/'output/auditoria-documental-41-turmas-2027/auditoria.json').read_text(encoding='utf-8'))
    rows=[r for r in documentary['sourceRows'] if r['students']>0]
    revenue_total=sum(Decimal(r['grossRevenue']) for r in rows)
    block_tests={}
    for field,total in [('support',Decimal('119961.77')),('generalExpenses',Decimal('453895.04'))]:
        errors=[abs(Decimal(r[field])-total*Decimal(r['grossRevenue'])/revenue_total)*100 for r in rows]
        block_tests[field]=dict(criterion='RECEITA_BRUTA_PREVISTA_P4',maximumDifferenceCents=float(max(errors)),verified=max(errors)<=1)
    payroll_tests={}
    for stage in segments:
        group=[r for r in rows if segment(r['sourceName'])==stage]
        total=sum(Decimal(r['payroll']) for r in group);n=sum(r['students'] for r in group)
        errors=[abs(Decimal(r['payroll'])-total*r['students']/n)*100 for r in group]
        payroll_tests[stage]=dict(criterion='ALUNOS_PREVISTOS_DENTRO_SEGMENTO_P4',totalCents=money(total*100),students=n,maxErrorCents=float(max(errors)),verified=max(errors)<=1)
    assert all(t['verified'] for t in block_tests.values())
    assert all(t['verified'] for t in payroll_tests.values())
    weights=[(r['sourceName'],Decimal(r['grossRevenue'])) for r in rows]
    # Totais oficiais prevalecem sobre soma arredondada das 38 linhas; cada ajuste é exposto.
    payroll=allocation(26763016,[(r['sourceName'],Decimal(r['payroll'])) for r in rows])
    support=allocation(11996177,weights)
    general=allocation(45389503,weights)
    pcld=allocation(4211780,weights)
    discounts=allocation(17790108,weights)
    allocations=[]
    for r in rows:
        name=r['sourceName'];cost=payroll[name]+support[name]+general[name]-pcld[name]-discounts[name]
        allocations.append(dict(sourceName=name,segment=segment(name),sourcePage=4,
            students=r['students'],weightGrossRevenue=r['grossRevenue'],
            payrollCents=payroll[name],supportCents=support[name],generalCents=general[name],
            pcldRemovedCents=pcld[name],discountReclassifiedCents=discounts[name],costCents=cost,
            printedCostCents=money(Decimal(r['totalCost'])*100),
            roundingBridgeCents=payroll[name]+support[name]+general[name]-money(Decimal(r['totalCost'])*100)))
    assert sum(r['costCents'] for r in allocations)==62146808
    mapping={r['document']['sourceName']:r['current']['classId'] for r in documentary['rows'] if r['document'] and r['document']['students']>0}
    for a in allocations:a['classId']=mapping.get(a['sourceName'])
    reserve=sum(a['costCents'] for a in allocations if not a['classId'])
    historical=json.loads((ROOT/'output/reconciliacao-pendencias-pe-2027/reconciliacao.json').read_text(encoding='utf-8'))
    known=17616080
    summary=dict(initialPendingCents=62320836,previousVerifiedCents=known,
        personnelOfficialCents=38759193,personnelPendingBeforeCents=38759193-known,
        generalPendingBeforeCents=41177723,officialMonthlyCents=84148696,
        managerialBeforeCents=79936916,pcldAlreadyNeutralizedCents=4211780,
        discountsReclassifiedCents=17790108,identityProvenDuplicateCents=0,
        costAfterReclassificationCents=62146808,
        documentedSchoolAmountCents=62146808,documentedAssignedCents=62146808-reserve,
        remainingDestinationPendingCents=reserve,
        newlyResolvedNetCents=62146808-reserve-known,
        financeCoverageKnownPercent=(62146808-reserve)/62146808*100,
        unknownAdditionalCosts='Paula e eventuais diferenças de postos/encargos sem valor. Não convertidos para zero.',
        economicClosure=False)
    assert summary['initialPendingCents']-summary['newlyResolvedNetCents']-summary['discountsReclassifiedCents']==reserve
    return dict(summary=summary,accounts=ledger,allocations=allocations,blockTests=block_tests,payrollTests=payroll_tests,
        segmentRevenueAnnualCents=dict(zip(segments,income)),segmentStudents=dict(zip(segments,students)),
        rounding=dict(analyticalGeneralToOfficialCents=-4,sourceTotalRowsToOfficialCents=-4),
        historicalPayroll=historical['people'],internBudgetCents=1775948,internNominalKnownCents=1489591,
        internUnidentifiedCents=286357,
        bridgeNote='R$ 387.591,93 é alvo financeiro do orçamento, NÃO folha de agosto. Detalhes nominais homologados são composição/controle dentro do envelope, nunca nova soma.',
        methodNote='P6/7 mostra todas as contas por receita de segmento; P4 distribui folha por alunos DENTRO do segmento, apoio/gerais por receita. São demonstrativos distintos. Não se promove rateio por capacidade nem se atribui funcionário à turma.')


def apply_costs(data,costs):
    plan={r['classId']:r for r in costs['allocations'] if r['classId']}
    for r in data['rows']:
        r.setdefault('previousPartialCostCents',r['verifiedCostCents'])
        r.setdefault('previousPendingCostCents',r['pendingCostCents'])
        r.setdefault('nominalCosts',r['costs'])
        p=plan.get(r['id'])
        if p:
            cost=p['costCents'];r['consideredCostCents']=cost;r['verifiedCostCents']=cost
            r['pendingCostCents']=None if r['unknownCosts'] else 0
            r['costCoveragePercent']=None if r['unknownCosts'] else 100
            r['costs']=[dict(kind='Folha orçada (composição nominal é controle, não acréscimo)',cents=p['payrollCents'],evidence='Orçamento 2027 p.4; critério por alunos previstos dentro do segmento'),
                dict(kind='Apoio orçado, inclui estágio sem somar nominal novamente',cents=p['supportCents'],evidence='Orçamento 2027 p.4; receita bruta prevista'),
                dict(kind='Demais contas operacionais, sem PCLD e estimativa substituída de descontos',cents=p['generalCents']-p['pcldRemovedCents']-p['discountReclassifiedCents'],evidence='Contas p.12–15; bloco gerais p.4; receita bruta prevista')]
            r['costBridge']=p;r['pendingCosts']=[]
            r['pe']=ceil_ratio(cost*r['acceptedStudentCount'],r['netRevenueCents']) if r['completeMix'] or r.get('partialMixAuthorized') else None
            r['ape']=float(Decimal(cost)/(Decimal(r['tuitionCents'])*Decimal('.955')))
            r['note']='Custo financeiro do orçamento reconciliado; distribuição real de descontos da amostra. Ponte nominal 2027 e completude do mix não certificadas. Não é PE definitivo.'
        else:
            r['consideredCostCents']=None;r['verifiedCostCents']=None;r['pendingCostCents']=None
            r['costCoveragePercent']=None;r['pe']=None;r['ape']=None
            r['costs']=[];r['pendingCosts']=[]
            r['note']='Destino do custo orçamentário sem correspondência. Custos nominais homologados preservados como referência, não somados sem abatimento demonstrado no orçamento.'
        r['status']='PE REAL PARCIALMENTE COMPROVADO' if r['pe'] is not None else 'PE AINDA EM AUDITORIA'
        if data.get('sanitation'):
            r['status']='PARCIALMENTE COMPROVADO' if r['pe'] is not None else 'EM AUDITORIA'
        r['percentCapacity']=r['pe']/r['capacity']*100 if r['pe'] is not None else None
        r['physicalMargin']=r['capacity']-r['pe'] if r['pe'] is not None else None
        r['physicallyInfeasible']=False
    data['costReconciliation']=costs
    s=data['summary'];s['verifiedCostCents']=costs['summary']['documentedAssignedCents'];s['consideredCostCents']=s['verifiedCostCents']
    s['pendingCostCents']=costs['summary']['remainingDestinationPendingCents']
    s['partial']=sum(r['pe'] is not None for r in data['rows']);s['audit']=41-s['partial']
    return data


def render_details(costs):
    text=['# Decomposição integral dos R$ 623.208,36','',
        'Pessoal: R$ 387.591,93 − R$ 176.160,80 nominal já reconhecido = R$ 211.431,13. Este saldo era R$ 202.296,04 institucional + R$ 7.771,79 residual folha G2 + R$ 1.363,30 apoio G2. Gerais: R$ 453.895,07 analítico − R$ 0,04 arredondamento − R$ 42.117,80 PCLD = R$ 411.777,23. Total: R$ 623.208,36. As deduções nominais são controles globais; não se inventou a rubrica do salário em que cada encargo já foi absorvido.','',
        costs['methodNote'],'',
        'Os valores de contas estão comprovados. O critério específico da página 6 é marcado somente quando a linha correspondente foi encontrada; nos demais gerais, a evidência é o rateio do bloco da página 4. Valor zero orçado não equivale a critério testado.','',
        '| Conta | Rubrica | Mensal R$ | Origem | Abrangência | Critério | Erro máximo anual (centavos) | Tratamento |','|---|---|---:|---|---|---|---|---|']
    for a in costs['accounts']:
        text.append(f"| {a['code']} | {a['description']} | {br(a['monthlyCents'])} | PDF p.{a['sourcePage']} | {a['scope']} | {a['criterion']} | {a['criterionTestMaximumAnnualCents']} | {a['treatment']} |")
    text+=['','## Parcelas por segmento e por turma','',
        'As cinco parcelas por conta estão em reconciliacao-custos.json → accounts[].segmentAllocationCents, com soma exata e fonte anual. A razão por turma abaixo reproduz os blocos da p.4; não equivale à lotação individual da folha.','',
        '| Turma do PDF | Segmento | Folha | Apoio | Gerais | PCLD retirada | Descontos substituídos | Custo financeiro | Destino | Ajuste arredondamento |','|---|---|---:|---:|---:|---:|---:|---:|---|---:|']
    for r in costs['allocations']:
        text.append('| '+' | '.join([r['sourceName'],r['segment']]+[br(r[k]) for k in ('payrollCents','supportCents','generalCents','pcldRemovedCents','discountReclassifiedCents','costCents')]+[r['classId'] or 'PENDENTE',str(r['roundingBridgeCents'])])+' |')
    text+=['','## Pessoal e estágio','',
        'As 19 contas de pessoal, inclusive desconto de VT negativo, somam exatamente R$ 387.591,93. A folha de agosto foi cruzada como composição nominal em historicalPayroll; ela não substitui o alvo orçado. Direção, secretaria, tesouraria e demais funções sem turma ficam compartilhadas, sem lotação fictícia.','',
        'Estágio: orçamento 4119040 R$ 17.759,48; base nominal capturada R$ 14.895,91; diferença R$ 2.863,57 dentro do envelope (não adicionada novamente). O rateio financeiro do orçamento está documentado; esse saldo não identifica Paula nem prova custo individual. Joyce/G2 A, Larissa/G2 B, posto adicional Paula/G3 B, substituição Jailane/Romilton e nova vaga Veroneide preservados. Não se somaram substituído e substituto.','',
        'Receitas 3182019 R$ 2.805,00 e 3195130 R$ 24.116,03 permanecem exclusivamente documentais: não reduzem o custo/PE real sem comprovação de recorrência e disponibilidade.','',
        'Descontos 4126005/4126007: R$ 177.901,08 são retirados do envelope utilizado junto ao ticket real como estimativas de concessões substituídas pela distribuição individual. É reclassificação econômica da estimativa, NÃO afirmação de conciliação nominal exata das contas. O valor comprovado como identidade duplicada por evento continua não determinado. A ponte individual permanece em ponte-descontos.json.']
    (AUDIT/'DECOMPOSICAO_CUSTOS_2027.md').write_text('\n'.join(text)+'\n',encoding='utf-8')


def main():
    costs=reconcile();write('reconciliacao-custos.json',costs);render_details(costs)
    data=json.loads((AUDIT/'resultado.json').read_text(encoding='utf-8'))
    data=apply_costs(data,costs);write('resultado.json',data)
    print(json.dumps(costs['summary'],ensure_ascii=True))


if __name__=='__main__':main()
