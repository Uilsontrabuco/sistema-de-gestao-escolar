"""Três contratos independentes de PE. Somente leitura; sem importação ou banco."""
from private_artifacts import private_path
from copy import deepcopy
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import json
from pathlib import Path

SOURCE=private_path('pe_layers_2027_source.json')
STATUSES={'COMPROVADO','PROVISÓRIO','PENDENTE DOCUMENTAL','SEM CORRESPONDÊNCIA','INVIÁVEL FISICAMENTE'}


def ceil_ratio(cost,ticket):
    if cost is None or ticket is None or ticket<=0:return None
    return int((Decimal(cost)/Decimal(ticket)).to_integral_value(rounding=ROUND_CEILING))


def ticket_cents(tuition,discount=3,delinquency=4.5):
    if type(tuition) is not int or tuition<=0:raise ValueError('Mensalidade inválida')
    for value in (discount,delinquency):
        if not Decimal(str(value)).is_finite() or not 0<=Decimal(str(value))<100:raise ValueError('Percentual inválido')
    return int((Decimal(tuition)*(1-Decimal(str(discount))/100)*(1-Decimal(str(delinquency))/100)).quantize(Decimal(1),rounding=ROUND_HALF_UP))


def metrics(cost,ticket,capacity):
    if type(capacity) is not int or capacity<0:raise ValueError('Capacidade inválida')
    pe=ceil_ratio(cost,ticket)
    return dict(costCents=cost,ticketCents=ticket,pe=pe,capacity=capacity,
        percentCapacity=pe/capacity*100 if capacity and pe is not None else None,
        physicalMargin=capacity-pe if pe is not None else None,
        revenueAtCapacityCents=ticket*capacity,
        resultAtCapacityCents=ticket*capacity-cost if cost is not None else None,
        physicalStatus='INVIÁVEL FISICAMENTE' if pe is not None and pe>capacity else None)


def validate_recognition(events,delinquency_percent=4.5):
    """Cada evento econômico pode incidir uma vez, em um único lado."""
    seen=set()
    for event in events:
        key=event.get('economicEventId')
        if not key or key in seen:raise ValueError('Evento econômico ausente ou duplicado')
        seen.add(key)
        if event.get('side') not in ('expense','ticket','student'):raise ValueError('Incidência inválida')
        if event.get('kind')=='pcld' and event['side']=='expense' and delinquency_percent:
            raise ValueError('PCLD e inadimplência não podem incidir novamente sobre a mesma perda')
    return True


def build_layers(source=None,capacities=None):
    source=deepcopy(source) if source is not None else json.loads(SOURCE.read_text(encoding='utf-8'))
    inputs=source['rows']
    if len(inputs)!=41 or len({r['id'] for r in inputs})!=41 or sum(r['capacity'] for r in inputs)!=1103:
        raise ValueError('Cadastro homologado divergente')
    if source['pcld']['managementIncludedCents']!=0:raise ValueError('PCLD duplicaria inadimplência no ticket')
    if source['institutionalRevenue']['availableForManagement']:raise ValueError('Receita institucional requer contrato gerencial específico comprovado')
    if capacities is not None and set(capacities)!=set(r['id'] for r in inputs):raise ValueError('Capacidades incompletas')
    rows=[];ids=set()
    for original in inputs:
        pending=[];verified=[]
        for part in original['components']:
            if part['id']!=original['id']+'/'+part['kind']:raise ValueError('Identidade da parcela inválida')
            if part['id'] in ids:raise ValueError('Despesa/rateio duplicado')
            ids.add(part['id'])
            if type(part['cents']) is not int or part['cents']<0:raise ValueError('Custo inválido')
            if part['verified'] and (part['kind'] not in source['verifiedComponents'] or not part['evidence']):
                raise ValueError('Comprovação do custo ausente')
            (verified if part['verified'] else pending).append(part)
        # Sem evidência não se cria um custo zero; zero exige evidência explícita.
        known=sum(p['cents'] for p in verified) if verified else None
        pending_total=sum(p['cents'] for p in pending)
        ticket=ticket_cents(original['tuitionCents'])
        capacity=original['capacity'] if capacities is None else capacities[original['id']]
        management=metrics(known,ticket,capacity)
        management.update(status='COMPROVADO' if known is not None else 'PENDENTE DOCUMENTAL',
            completeCostCoverage=not pending_total and not original['unknownCosts'],
            basis='Custos comprovados da base homologada; valor parcial enquanto houver pendências',
            costs=verified,pcldIncludedCents=0,institutionalRevenueIncludedCents=0,
            discountPercent=3,delinquencyPercent=4.5)
        provisional=metrics(sum(p['cents'] for p in original['components']),ticket,capacity)
        provisional.update(status='PROVISÓRIO',aboveCapacityWarning=provisional['pe']>capacity,
            physicalStatus=None,basis='Simulação histórica com pendências; não certifica inviabilidade')
        doc=original['document']
        documentary=dict(status='SEM CORRESPONDÊNCIA',pe=None,printedPE=None,mathematicalCeiling=None,
            source=source['source'],page=4,formula='teto(alunos previstos × custo documental / receita líquida documental)',
            sourceValues=doc,precision='Valores impressos; planilha geradora 2027 não disponível')
        if doc and doc['students']>0 and Decimal(doc['netRevenue'])>0:
            ceiling=ceil_ratio(Decimal(doc['students'])*Decimal(doc['totalCost']),Decimal(doc['netRevenue']))
            printed=int(doc['pe'])
            documentary.update(pe=ceiling,mathematicalCeiling=ceiling,printedPE=printed,
                status='COMPROVADO' if ceiling==printed else 'PENDENTE DOCUMENTAL',
                printedValueStatus='COMPROVADO',roundingDifference=ceiling-printed,
                observation='PDF impresso preservado; teto reconstruído separado, não substitui a fonte' if ceiling!=printed else 'Valor impresso e teto reconstruído coincidem')
        elif doc:
            documentary.update(printedPE=int(doc['pe']),observation='SEM CORRESPONDÊNCIA DOCUMENTAL DIRETA: linha zerada, turma atual ativa')
        real=dict(status='PENDENTE DOCUMENTAL',studentCount=None,revenueCents=None,costCents=known,
            marginCents=None,averageTicketCents=None,discountImpactCents=None,distanceToPE=None,
            feedEnabled=False,reason='Base real não importada; cobertura de descontos pendente')
        rows.append(dict(id=original['id'],name=original['name'],capacity=capacity,
            tuitionCents=original['tuitionCents'],tuitionSource=source['tuitionSource'],
            documentary=documentary,managerial=management,provisional=provisional,realProjection=real,
            pendingCosts=dict(label='CUSTO PENDENTE DE COMPROVAÇÃO',knownCents=pending_total,
                items=pending,unknownItems=original['unknownCosts'],completeAmount=not original['unknownCosts']),
            status=management['physicalStatus'] or ('PROVISÓRIO' if pending_total or original['unknownCosts'] else management['status']),
            documentaryManagerialDifference=management['pe']-documentary['pe'] if management['pe'] is not None and documentary['pe'] is not None else None))
    summary=dict(classes=41,capacity=sum(r['capacity'] for r in rows),
        documentaryConfirmed=sum(r['documentary']['status']=='COMPROVADO' for r in rows),
        printedDocumentaryConfirmed=sum(r['documentary']['printedPE'] is not None and r['documentary']['status']!='SEM CORRESPONDÊNCIA' for r in rows),
        managerialConfirmed=sum(r['managerial']['status']=='COMPROVADO' for r in rows),
        managerialCompletelyClosed=sum(r['managerial']['completeCostCoverage'] for r in rows),
        provisional=sum(r['status']=='PROVISÓRIO' for r in rows),
        pendingDocumentary=sum(bool(r['pendingCosts']['knownCents'] or r['pendingCosts']['unknownItems']) for r in rows),
        unmatched=sum(r['documentary']['status']=='SEM CORRESPONDÊNCIA' for r in rows),
        physicallyInfeasible=sum(r['managerial']['physicalStatus']=='INVIÁVEL FISICAMENTE' for r in rows),
        verifiedMonthlyCents=sum(r['managerial']['costCents'] or 0 for r in rows),
        pendingKnownMonthlyCents=sum(r['pendingCosts']['knownCents'] for r in rows),
        provisionalMonthlyCents=sum(r['provisional']['costCents'] for r in rows),
        unknownCostCount=sum(len(r['pendingCosts']['unknownItems']) for r in rows))
    if summary['verifiedMonthlyCents']+summary['pendingKnownMonthlyCents']!=summary['provisionalMonthlyCents']:
        raise ValueError('Conciliação de componentes não fecha')
    return dict(contractVersion='pe-2027-three-layers-v1',year=2027,rows=rows,summary=summary,
        source=source['source'],costBasis=source['costBasis'],pcld=source['pcld'],
        discountCoverage=source['discountCoverage'],institutionalRevenue=source['institutionalRevenue'],
        unmatchedSourceRows=source['unmatchedSourceRows'],definitivelyClosed=False)


def project_real(layers,students=None,*,complete=False,recognitions=(),coverage=None):
    """Contrato futuro sem I/O. A base real substitui os 3%; não altera os PEs."""
    if students is None:return [deepcopy(r['realProjection'])|{'classId':r['id']} for r in layers['rows']]
    if not complete:raise ValueError('Base real incompleta')
    if not coverage or coverage.get('status')!='RECONCILIADA' or not coverage.get('source'):
        raise ValueError('COBERTURA DE DESCONTOS PENDENTE DE RECONCILIAÇÃO')
    events=list(recognitions);by_id={r['id']:r for r in layers['rows']};groups={k:[] for k in by_id};seen=set()
    for s in students:
        sid=s.get('studentId');cid=s.get('classId')
        if not sid or sid in seen or cid not in by_id:raise ValueError('Aluno duplicado ou turma desconhecida')
        seen.add(sid);gross=by_id[cid]['tuitionCents'];benefits=s.get('benefits',[])
        discount=0
        for benefit in benefits:
            value=benefit.get('discountCents')
            if type(value) is not int or value<0:raise ValueError('Benefício inválido')
            events.append(dict(economicEventId=benefit.get('economicEventId'),side='student',kind='discount'))
            discount+=value
        if discount>gross:raise ValueError('Benefícios excedem mensalidade')
        # Bolsa integral é permitida. Nenhum desconto estrutural de 3% é aplicado aqui.
        net=int((Decimal(gross-discount)*Decimal('.955')).quantize(Decimal(1),rounding=ROUND_HALF_UP))
        groups[cid].append((gross,discount,net))
    validate_recognition(events)
    output=[]
    for cid,r in by_id.items():
        group=groups[cid];revenue=sum(x[2] for x in group);cost=r['managerial']['costCents'];pe=r['managerial']['pe']
        output.append(dict(classId=cid,status='COMPROVADO' if r['managerial']['completeCostCoverage'] else 'PROVISÓRIO',studentCount=len(group),revenueCents=revenue,
            costCents=cost,marginCents=revenue-cost if cost is not None else None,
            averageTicketCents=revenue/len(group) if group else None,discountImpactCents=sum(x[1] for x in group),
            distanceToPE=max(0,pe-len(group)) if pe is not None else None,
            structuralPE=pe,completeCostCoverage=r['managerial']['completeCostCoverage'],
            note='Distância ao PE estrutural não garante equilíbrio com o ticket real; conferir margem'))
    return output
