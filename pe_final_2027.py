"""Regras finais aditivas; os marcos anteriores de auditoria permanecem imutáveis."""
from copy import deepcopy
from decimal import Decimal
from pe_real import ceil_ratio,money

RULES={'caj-2027-caj-g5-c':96467,'caj-2027-caj-8-c':123981}

def final_view(report,state):
    out=deepcopy(report);classes={c['id']:c for c in state['classes']}
    from benefits_2027 import summarize
    finance={b['classId']:b['planned'] for b in summarize(state)['rows']}
    for r in out['rows']:
        if r['id'] not in RULES:continue
        c=classes[r['id']]
        enough=r.get('plannedBenefitCount',0)>0 and (r.get('currentRevenueComplete') or c.get('benefitMix2027Confirmed') is True)
        r['documentaryTuitionCents']=r['tuitionCents']
        if not enough:
            tuition=RULES[r['id']];ticket=Decimal(tuition)*Decimal('.88')*Decimal('.955')
            r['planningAssumption']=dict(tuitionCents=tuition,discountPercent=12,delinquencyPercent=4.5,ticketExactCents=str(ticket),source='Comando financeiro final: 12% G5 C e 8º C; matrícula não cria benefício',replacedBy='Mix válido da própria turma com cobertura nominal completa ou base prevista expressamente homologada')
            r['ticketCents']=r['plannedTicketCents']=float(ticket)
            r['averageFinancialDiscountCents']=tuition*.12;r['plannedMixConfirmed']=False
        else:
            r.pop('planningAssumption',None)
            mix=finance[r['id']]
            if mix['count']:
                r.update(acceptedStudentCount=mix['count'],sourceStudentCount=mix['count'],grossCents=mix['grossCents'],discountCents=mix['discountCents'],postDiscountCents=mix['grossCents']-mix['discountCents'],netRevenueCents=mix['netCents'],averageFinancialDiscountCents=mix['discountCents']/mix['count'],ticketCents=mix['ticketCents'],plannedTicketCents=mix['ticketCents'])
                r['delinquencyCents']=r['postDiscountCents']-r['netRevenueCents']
            ticket=Decimal(str(r['plannedTicketCents'])) if r['plannedTicketCents'] is not None else None
        r['planningTuitionCents']=RULES[r['id']] if r.get('planningAssumption') else r['tuitionCents']
        r['pe']=ceil_ratio(r['consideredCostCents'],ticket)
        r['distanceToPE']=r['enrolled']-r['pe'] if r['pe'] is not None else None
        r['physicalMargin']=r['capacity']-r['pe'] if r['pe'] is not None else None
        r['percentCapacity']=r['pe']/r['capacity']*100 if r['pe'] is not None else None
        r['status']='PARCIALMENTE COMPROVADO' if r['pe'] is not None else 'EM AUDITORIA'
        r['enrollmentSituation']=('abaixo do ponto de equilíbrio' if r['distanceToPE']<0 else 'no ponto de equilíbrio' if r['distanceToPE']==0 else 'acima do ponto de equilíbrio') if r['pe'] is not None else 'PE pendente'
        r['projectedRevenueCents']=money(ticket*r['enrolled']) if ticket is not None else None
        r['projectedResultCents']=r['projectedRevenueCents']-r['consideredCostCents'] if r['projectedRevenueCents'] is not None and r['consideredCostCents'] is not None else None
        r['revenueProjectionStatus']='PREMISSA_FINAL_12' if r.get('planningAssumption') else 'MIX_INDIVIDUAL_SUFFICIENTE'
        r['note']='Premissa final de 12% substituída integralmente pelo mix suficiente da própria turma; inadimplência 4,5% uma vez. Não altera benefícios, matrículas ou custo.'
        if r['name']=='G5 C':r['note']+=' Mensalidade de planejamento R$ 964,67 expressamente solicitada; cadastro documental EI R$ 930,69 preservado. Não é comprovação de mudança de segmento.'
        else:r['note']+=' Custo não transferido: orçamento p.8 registra 7º C em 2027 e 8º C em 2026, contrariando a ponte proposta.'
    out['summary']['partial']=sum(r['status']=='PARCIALMENTE COMPROVADO' for r in out['rows'])
    out['summary']['audit']=sum(r['status']=='EM AUDITORIA' for r in out['rows'])
    out['enrollmentSummary']['knownProjectedRevenueCents']=sum(r['projectedRevenueCents'] or 0 for r in out['rows'])
    out['enrollmentSummary']['missingRevenueClasses']=sum(r['projectedRevenueCents'] is None for r in out['rows'])
    from personnel_confirmations_2027 import personnel_evidence
    out['personnelConfirmations']=personnel_evidence()
    out['finalRuleVersion']='final-planning-12-v1'
    out['structureNotice']='ESTRUTURA EM REVISÃO FINANCEIRA: correção administrativa mais recente confirma 41 turmas, com 7º A/B e 8º A/B/C. O 8º C mantém 20 matriculados e capacidade 28; nenhuma redistribuição. A composição de custos ainda requer fechamento.'
    return out

def diagnostic(r):
    cost=r['consideredCostCents'];ticket=r['ticketCents'];pe=r['pe'];distance=r['distanceToPE']
    def br(c):return 'não determinado' if c is None else 'R$ '+f'{c/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')
    parts=[f"{r['name']}: {r['enrolled']} matriculados para {r['capacity']} vagas ({format(r['occupancyPercent'],'.2f').replace('.',',')}% de ocupação)."]
    if pe is None:parts.append('O PE não pode ser determinado porque o custo integral não tem destino documental comprovado. Ticket calculável não comprova o numerador.')
    else:
        parts.append(f"O custo mensal de {br(cost)} dividido pelo ticket de {br(ticket)}, arredondado para cima, exige {pe} alunos.")
        parts.append(f"São necessárias mais {-distance} matrículas para atingir o equilíbrio." if distance<0 else 'A turma está no ponto de equilíbrio.' if distance==0 else f'A turma está {distance} alunos acima do equilíbrio.')
    if r.get('planningAssumption'):parts.append('PREMISSA: desconto de planejamento de 12%; inadimplência de 4,5% uma única vez. O mix individual suficiente substituirá a premissa, sem acumulação.')
    else:parts.append(f"O desconto médio financeiro de {br(r.get('averageFinancialDiscountCents'))} reduz a mensalidade antes da inadimplência de 4,5%, aplicada uma vez.")
    if r['costs']:
        top=max(r['costs'],key=lambda c:c['cents']);parts.append(f"Maior componente: {top['kind']}, {br(top['cents'])}. Estes blocos já incluem os rateios documentais; composição nominal não é acréscimo.")
    parts.append(f"Receita projetada: {br(r['projectedRevenueCents'])}; resultado projetado: {br(r['projectedResultCents'])}. Trata-se de planejamento, não caixa realizado.")
    parts.append(r['note'])
    parts.append('Nível de comprovação: '+r['status']+'. Composição nominal 2027 não encerrada; nenhum custo desconhecido foi presumido zero.')
    return ' '.join(parts)

def executive(report):
    rows=report['rows'];known=[r for r in rows if r['consideredCostCents'] is not None and r['projectedRevenueCents'] is not None]
    return dict(classes=len(rows),capacity=sum(r['capacity'] for r in rows),enrolled=sum(r['enrolled'] for r in rows),
        peKnown=sum(r['pe'] or 0 for r in rows),peMissing=sum(r['pe'] is None for r in rows),
        revenue=sum(r['projectedRevenueCents'] or 0 for r in rows),cost=sum(r['consideredCostCents'] or 0 for r in rows),
        comparableRevenue=sum(r['projectedRevenueCents'] for r in known),result=sum(r['projectedResultCents'] for r in known),comparableClasses=len(known),
        above=sum(r['distanceToPE'] is not None and r['distanceToPE']>0 for r in rows),at=sum(r['distanceToPE']==0 for r in rows),below=sum(r['distanceToPE'] is not None and r['distanceToPE']<0 for r in rows),overcrowded=sum(r['vacancies']<0 for r in rows),audit=sum(r['status']=='EM AUDITORIA' for r in rows))
