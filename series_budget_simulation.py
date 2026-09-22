"""Simulação em centavos: conserva os envelopes existentes, sem I/O operacional."""
from copy import deepcopy
from decimal import Decimal
from pe_real import money,ceil_ratio
from administrative_pe_2027 import exact_ticket

GRADES=('1º','2º','3º','8º')

def distribute(total,weights):
    if total<0 or not weights or any(w<=0 for _,w in weights):
        raise ValueError('Montante/peso inválido para repartição')
    denominator=sum(w for _,w in weights)
    floor={key:total*w//denominator for key,w in weights}
    order=sorted(weights,key=lambda pair:(-(total*pair[1]%denominator),pair[0]))
    for key,_ in order[:total-sum(floor.values())]:floor[key]+=1
    assert sum(floor.values())==total
    return floor

def simulate(report,ledger):
    before=deepcopy(report['rows']);after=deepcopy(before)
    by_id={r['id']:r for r in after}
    allocations={r['classId']:r for r in ledger['allocations'] if r['classId']}
    if sum(a['costCents'] for a in allocations.values())!=60564103:
        raise ValueError('Envelope distribuído mudou; conferir base')
    reserve=sum(a['costCents'] for a in ledger['allocations'] if not a['classId'])
    if reserve!=1582705:raise ValueError('Reserva divergente')
    series=[]
    for grade in GRADES:
        rooms=[r for r in before if r['name'].split()[0]==grade and 'EM' not in r['name']]
        donors=[allocations[r['id']] for r in rooms if r['id'] in allocations]
        pools=dict(payroll=sum(a['payrollCents'] for a in donors),support=sum(a['supportCents'] for a in donors),
                   generalNet=sum(a['generalCents']-a['pcldRemovedCents']-a['discountReclassifiedCents'] for a in donors))
        total=sum(a['costCents'] for a in donors)
        assert total==sum(pools.values())
        teachers={r['id']:r['teacherCents']-(27414 if r['name']=='8º C' else 0) for r in rooms}
        anchors={r['id']:sum(p['cents'] for p in r['nominalCosts'] if p['kind']!='docentes') for r in rooms}
        if sum(teachers.values())>pools['payroll'] or sum(anchors.values())>pools['support']:
            raise ValueError('Rubrica insuficiente para preservar parcelas conhecidas; não redistribuir')
        # Bases nominais + resíduo: não soma orçamento novo.
        payroll_residual=distribute(pools['payroll']-sum(teachers.values()),list(teachers.items()))
        support_residual=distribute(pools['support']-sum(anchors.values()),[(r['id'],r['capacity']) for r in rooms])
        general=distribute(pools['generalNet'],[(r['id'],r['capacity']) for r in rooms])
        proposals=[]
        for r in rooms:
            cid=r['id'];payroll=teachers[cid]+payroll_residual[cid];support=anchors[cid]+support_residual[cid]
            cost=payroll+support+general[cid];ticket=exact_ticket(r);pe=ceil_ratio(cost,ticket)
            proposal=dict(id=cid,name=r['name'],costBeforeCents=r['consideredCostCents'],costAfterCents=cost,
                deltaFromPreviouslyAllocatedCents=cost-(r['consideredCostCents'] or 0),
                previouslyUnknown=r['consideredCostCents'] is None,
                teacherAnchorCents=teachers[cid],otherNominalAnchorCents=anchors[cid],
                payrollCents=payroll,supportCents=support,generalNetCents=general[cid],
                payrollResidualCents=payroll_residual[cid],supportResidualCents=support_residual[cid],
                historicalNonAdditiveControlCents=27414 if r['name']=='8º C' else 0,
                capacity=r['capacity'],enrolled=r['enrolled'],ticketExactCents=str(ticket),
                peBefore=r['pe'],peAfter=pe,peDelta=None if r['pe'] is None else pe-r['pe'])
            proposals.append(proposal)
            out=by_id[cid];out.update(consideredCostCents=cost,pe=pe,
                sourceConsideredCostCents=r['consideredCostCents'],sourcePE=r['pe'],
                verifiedCostCents=None,costCoveragePercent=None,completeCostCoverage=False,
                costs=[dict(kind='Folha — repartição proposta',cents=payroll,evidence='SIMULAÇÃO: âncora docente e saldo pelo mesmo peso'),
                       dict(kind='Apoio — repartição proposta',cents=support,evidence='SIMULAÇÃO: nominal preservado e saldo por capacidade'),
                       dict(kind='Gerais líquidos — repartição proposta',cents=general[cid],evidence='SIMULAÇÃO: capacidade')],
                note='Somente simulação: não substitui valor vigente nem certifica nova distribuição documental.',
                simulationCostComponents=dict(payrollCents=payroll,supportCents=support,generalNetCents=general[cid]),
                simulationOnly=True,status='SIMULAÇÃO; CRITÉRIOS DE REPARTIÇÃO AGUARDAM APROVAÇÃO',
                distanceToPE=r['enrolled']-pe,physicalMargin=r['capacity']-pe,
                percentCapacity=pe/r['capacity']*100,physicallyInfeasible=pe>r['capacity'],
                projectedResultCents=r['projectedRevenueCents']-cost if r['projectedRevenueCents'] is not None else None)
        assert sum(p['costAfterCents'] for p in proposals)==total
        assert sum(p['deltaFromPreviouslyAllocatedCents'] for p in proposals)==0
        series.append(dict(grade=grade,sourceRows=[a['sourceName'] for a in donors],pools=pools,
            budgetBeforeCents=total,budgetAfterCents=sum(p['costAfterCents'] for p in proposals),differenceCents=0,
            proposals=proposals))
    assert sum(r['consideredCostCents'] for r in after)==60564103
    return dict(kind='SIMULACAO_NAO_APLICADA',series=series,rows=after,
        originalRows=before,globalBeforeAssignedCents=60564103,globalAfterAssignedCents=60564103,
        reserveBeforeCents=reserve,reserveAfterCents=reserve,globalDifferenceCents=0,
        mathReconciled=True,documentaryAmountsAndNominalAnchorsVerified=True,
        proposedAllocationAlreadyDocumented=False,administrativeApprovalRequired=True,
        integralDocumentaryClosure=False,addedSchoolCostCents=0,
        note='Os quatro custos ausentes eram indefinidos, não zero; zero apenas como contribuição ao total já distribuído. Valores novos por turma são reatribuição simulada com contrapartida nas paralelas.')
