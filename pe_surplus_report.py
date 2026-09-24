"""Read-only results and allocation diagnostics over the existing PE model."""
from copy import deepcopy
from decimal import Decimal
from statistics import mean

D = Decimal
PENDING_CURRENT = 'RESULTADO ATUAL PENDENTE DE VÍNCULO DE BENEFÍCIOS'
PENDING_ALLOCATION = 'PARCELA GERENCIAL PENDENTE DOCUMENTAL'
CONCENTRATION_THRESHOLD = D('25')
REQUESTED = {'G5 A','G5 B','G4 A','4º B','4º C','6º C','9º C','3º EM'}

def money(value):
    return 'R$ '+f'{D(str(value))/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')

def comparison_group(row):
    return 'EM' if 'EM' in row['turma'] else row['turma'].split()[0]

def build_surplus_report(analytic):
    result=deepcopy(analytic)
    rows=result['rows']
    if len(rows)!=41 or sum(r['capacidade'] for r in rows)!=1103:
        raise ValueError('Estrutura da candidata divergente.')
    for index,r in enumerate(rows):
        r['analyticIndex']=index
        r['segmentCode']={'Educação Infantil':'EI','Fundamental I':'FI','Fundamental II':'FII','Ensino Médio':'EM'}[r['segment']]
        r['comparisonGroup']=comparison_group(r)
        r['studentsVersusPE']=r['matriculados']-r['peCorrigido']
        r['currentRevenueCents']=None
        r['currentBalanceCents']=None
        r['currentStatus']='PENDENTE DE VÍNCULO'
        r['currentNote']=PENDING_CURRENT
        # Zero enrollment is sufficient for zero tuition revenue, without using
        # any planned discount as an active benefit. No nominal roster inferred.
        if r['matriculados']==0:
            r['currentRevenueCents']='0'
            r['currentBalanceCents']=str(-r['custoTotalCentavos'])
            r['currentStatus']='DEFICITÁRIA'
            r['currentNote']='Receita de mensalidades zero: nenhuma matrícula no snapshot. Custo econômico preservado; não é fluxo de caixa realizado.'
        r['structuralStatus']=('ESTRUTURALMENTE SUPERAVITÁRIA' if r['peCorrigido']<r['capacidade'] else 'NO LIMITE DO EQUILÍBRIO' if r['peCorrigido']==r['capacidade'] else 'ESTRUTURALMENTE DEFICITÁRIA')
        r['documentaryPending']=bool(r['dentroGrupo15'])
        r['documentaryNote']=r['status']+'; parcelas gerenciais sem vínculo analítico permanecem pendentes.'
        r['componentPercentages']={c['label']:str(D(c['cents'])/r['custoTotalCentavos']*100) for c in r['components']}
        r['allocationCents']=r['rateioSegmentoCentavos']+r['rateioGlobalCentavos']
        r['allocationPercent']=str(D(r['allocationCents'])/r['custoTotalCentavos']*100)
        r['allocationPerSeatCents']=str(D(r['allocationCents'])/r['capacidade'])
        r['allocationAuditRequired']=r['turma'] in REQUESTED or D(r['allocationPercent'])>70
        r['planningTicketNote']=('TICKET DE PLANEJAMENTO — INCLUI BENEFÍCIOS PREVISTOS' if r['revenue']['quantity'] else 'TICKET DE PLANEJAMENTO — PREMISSA GERENCIAL; não equivale a benefício ativo')
        r['structuralExplanation']=(f"Com capacidade de {r['capacidade']} alunos e PE de {r['peCorrigido']}, a turma tem margem estrutural de {r['margemFisica']} alunos. "
            f"Na lotação máxima, receita projetada de {money(r['capacityRevenueCents'])} contra custo de {money(r['custoTotalCentavos'])}, "
            f"com {'déficit' if D(r['capacityBalanceCents'])<0 else 'superávit'} mensal de {money(abs(D(r['capacityBalanceCents'])))}. "
            f"Os rateios representam {D(r['allocationPercent']):.2f}% do custo atribuído. {r['structuralStatus']}.")
    for r in rows:
        peers=[p for p in rows if p['comparisonGroup']==r['comparisonGroup'] and p['id']!=r['id']]
        average=mean(D(p['allocationPerSeatCents']) for p in peers) if peers else None
        diff=D(r['allocationPerSeatCents'])-average if average is not None else None
        percent=diff/average*100 if average else None
        r['concentration']=dict(peerIds=[p['id'] for p in peers],peerMeanCents=str(average) if average is not None else None,
            differenceCents=str(diff) if diff is not None else None,differencePercent=str(percent) if percent is not None else None,
            flagged=percent is not None and percent>CONCENTRATION_THRESHOLD)
    known=[r for r in rows if r['currentBalanceCents'] is not None]
    balances=[D(r['capacityBalanceCents']) for r in rows]
    current=[D(r['currentBalanceCents']) for r in known]
    result['surplusSummary']=dict(classes=len(rows),capacity=sum(r['capacidade'] for r in rows),
        currentKnown=len(known),currentPending=len(rows)-len(known),currentSurplus=sum(v>0 for v in current),currentDeficit=sum(v<0 for v in current),currentEqual=sum(v==0 for v in current),
        currentSurplusCents=str(sum((v for v in current if v>0),D(0))),currentDeficitCents=str(-sum((v for v in current if v<0),D(0))),
        currentKnownNetCents=str(sum(current,D(0))),currentAllNetCents=str(sum(current,D(0))) if len(known)==len(rows) else None,
        belowCapacity=sum(r['peCorrigido']<r['capacidade'] for r in rows),equalCapacity=sum(r['peCorrigido']==r['capacidade'] for r in rows),aboveCapacity=sum(r['peCorrigido']>r['capacidade'] for r in rows),
        structuralSurplusCents=str(sum((v for v in balances if v>0),D(0))),structuralDeficitCents=str(-sum((v for v in balances if v<0),D(0))),structuralNetCents=str(sum(balances,D(0))),
        costCents=sum(r['custoTotalCentavos'] for r in rows),documentaryPending=sum(r['documentaryPending'] for r in rows),allocationAuditClasses=sum(r['allocationAuditRequired'] for r in rows))
    if result['surplusSummary']['costCents']!=analytic['summary']['soma41Centavos']:
        raise ValueError('Consolidação divergente.')
    result['auditRule']=dict(thresholdPercent=str(CONCENTRATION_THRESHOLD),criterion='Rateio por vaga mais de 25% acima da média aritmética dos outros pares da mesma série; EM comparado dentro do segmento. Alerta de triagem, não prova de erro.',automaticCorrection=False)
    result['currentResultNote']='Visão atual limitada ao snapshot local. Sem vínculo nominal suficiente, não usar o ticket de planejamento como receita atual. Turmas com zero matrícula têm receita de mensalidade zero demonstrável.'
    if analytic.get('presentationLabel'):
        result['currentResultNote']='Visão referente aos resultados validados na data indicada. Sem vínculo nominal suficiente, não usar o ticket de planejamento como receita atual. Não representa posição de matrículas em tempo real.'
    result['roundingNote']='Totais somam valores integrais antes do arredondamento. A soma visual das linhas arredondadas pode diferir por centavos. Reserva fora dos custos das turmas.'
    return result
