"""Cenário de aprovação humana; função pura, sem gravação operacional.

Ordem administrativa: financiar quotas nominais já comprovadas dentro do
envelope, depois distribuir apenas o remanescente global por capacidade.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_CEILING
from administrative_pe_2027 import exact_ticket
from series_budget_simulation import distribute

BLOCKS = {'payrollCents / saldo':'folha', 'supportCents / saldo':'apoio', 'generalNetCents / saldo':'gerais'}
AUTHORIZED = {'folha':3775406, 'apoio':2476030, 'gerais':6161766}

def reconcile(checkpoint):
    original = checkpoint['conservativeRows']
    rows = deepcopy(original)
    removed = {r['name']:dict.fromkeys(AUTHORIZED,0) for r in rows}
    for c in checkpoint['components']:
        if c['component'] in BLOCKS:
            removed[c['turma']][BLOCKS[c['component']]] += c['cents']
    totals = {k:sum(r[k] for r in removed.values()) for k in AUTHORIZED}
    if totals != AUTHORIZED:
        raise ValueError('Checkpoint não corresponde aos três saldos aprovados')
    if len(rows)!=41 or sum(r['capacity'] for r in rows)!=1103:
        raise ValueError('Estrutura física diferente da autorização')
    earmarked = dict.fromkeys(AUTHORIZED,0)
    records = []
    for r in rows:
        teacher = r['teacherCents']-(27414 if r['name']=='8º C' else 0)
        exclusive = sum(c['cents'] for c in r['nominalCosts'] if c['kind'] in ('estagiarias','auxiliar-direta'))
        segment = sum(c['cents'] for c in r['nominalCosts'] if c['kind'] in ('auxiliares-segmento','coordenacao-segmento'))
        anchor = teacher+exclusive+segment
        need = r['consideredCostCents'] is None
        coverage = {'folha':teacher if need else 0, 'apoio':exclusive+segment if need else 0, 'gerais':0}
        for k in earmarked:
            earmarked[k] += coverage[k]
        base = (r['consideredCostCents'] or 0)-sum(removed[r['name']].values())
        # Quotas das 37 linhas já estão cobertas. As quatro restantes recebem
        # cobertura do MESMO envelope; não são somadas sobre o total da escola.
        if not need and base<anchor:
            raise ValueError('Saída invade quota nominal protegida')
        records.append(dict(id=r['id'],name=r['name'],teacherCents=teacher,
            exclusiveCents=exclusive,segmentCents=segment,anchorCents=anchor,
            inheritedCoverageCents=base-(0 if need else anchor),
            removed=removed[r['name']],nominalCoverageFromAuthorized=coverage,
            costBeforeCents=r['consideredCostCents'],peBefore=r['pe']))
    remaining={k:AUTHORIZED[k]-earmarked[k] for k in AUTHORIZED}
    if any(v<0 for v in remaining.values()):
        raise ValueError('Envelope insuficiente para preservar todos os nominais')
    weights=[(r['id'],r['capacity']) for r in rows]
    allocated={k:distribute(v,weights) for k,v in remaining.items()}
    by_id={r['id']:r for r in rows}
    for d in records:
        r=by_id[d['id']]
        d['globalAllocation']={k:allocated[k][r['id']] for k in AUTHORIZED}
        d['costAfterCents']=d['anchorCents']+d['inheritedCoverageCents']+sum(d['globalAllocation'].values())
        ticket=exact_ticket(r)
        if ticket is None or ticket<=0:
            raise ValueError('Ticket não calculável')
        d['ticketExactCents']=str(ticket)
        d['peAfter']=int((Decimal(d['costAfterCents'])/ticket).to_integral_value(rounding=ROUND_CEILING))
        d['peDelta']=None if d['peBefore'] is None else d['peAfter']-d['peBefore']
        d['costDeltaCents']=d['costAfterCents']-(d['costBeforeCents'] or 0)
        d['material']=d['peBefore'] is None or abs(d['peDelta'])>=3 or abs(d['costDeltaCents'])>=Decimal(str(d['costBeforeCents']))*Decimal('.20')
        d['capacity']=r['capacity'];d['enrolled']=r['enrolled']
        d['peCapacityPercent']=d['peAfter']/r['capacity']*100
        d['situation']='abaixo do PE' if r['enrolled']<d['peAfter'] else 'no PE' if r['enrolled']==d['peAfter'] else 'acima do PE'
        d['structurallyInfeasible']=d['peAfter']>r['capacity']
        # Saída própria de auditoria: não reaproveitar indicadores derivados
        # antigos (resultado, margem ou confiança) com um custo novo.
        identity={k:r[k] for k in ('id','name','capacity','enrolled','newStudents','reenrolled','vacancies','tuitionCents') if k in r}
        r.clear()
        r.update(identity,consideredCostCents=d['costAfterCents'],pe=d['peAfter'],
                 ticketExactCents=d['ticketExactCents'],percentCapacity=d['peCapacityPercent'],
                 distanceToPE=d['enrolled']-d['peAfter'],physicalMargin=d['capacity']-d['peAfter'],
                 physicallyInfeasible=d['structurallyInfeasible'],situation=d['situation'],approvalScenarioOnly=True)
    before=sum(r['consideredCostCents'] or 0 for r in original)
    after=sum(r['consideredCostCents'] for r in rows)
    if before!=60564103 or after!=before:
        raise ValueError(f'NO-GO: total antes {before}, depois {after}')
    bridges={k:dict(initialCents=AUTHORIZED[k],nominalCoverageCents=earmarked[k],
                   globalDistributedCents=sum(allocated[k].values()),
                   distributedCents=earmarked[k]+sum(allocated[k].values()),differenceCents=0) for k in AUTHORIZED}
    for k,b in bridges.items():
        if b['distributedCents']!=AUTHORIZED[k]:
            raise ValueError('Bloco não conserva o total')
    return dict(rows=rows,details=records,bridges=bridges,schoolBeforeCents=before,
        schoolAfterCents=after,differenceCents=after-before,reserveCents=checkpoint['partition']['reserveCents'],
        nominalCoverageCents=sum(earmarked.values()),globalResidualCents=sum(remaining.values()),
        inheritedCoverageCents=sum(d['inheritedCoverageCents'] for d in records),
        nominalTotalCents=sum(d['anchorCents'] for d in records),unidentifiedAuthorizedResidualCents=0,
        appliedToDatabase=False,rule='A/B/C antes do residual D/E; capacidade, maiores restos, desempate por id')
