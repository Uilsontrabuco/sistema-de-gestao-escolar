"""Benefícios previstos persistidos na lista existente; matrícula ativa, não cria."""
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal
import hashlib
from pe_real import normalized, money

KIND='planned-2027'


def is_planned(b):return b.get('sourceKind')==KIND


def import_benefits(state, records, identity_map=None):
    result=deepcopy(state);existing={b['id']:b for b in result['benefits']};identity_map=identity_map or {}
    for r in records:
        if not r['benefitValid']:continue
        identity=identity_map.get(r['studentKey'])
        key=('id:'+identity) if identity else 'name:'+r['studentKey']
        bid='planned-2027-'+hashlib.sha256(key.encode()).hexdigest()[:24]
        candidate=dict(id=bid,sourceKind=KIND,year=2027,name=r['benefit'],type='Benefício individual previsto 2027',quantity=1,
            studentId=identity,studentName=r['student'],studentKey=r['studentKey'],identityKey=key,
            classId=r['classId'],sourceClass=r['sourceClass'],rate=r['rate'],
            grossCents=r['grossCents'],discountCents=r['discountCents'],postDiscountCents=r['postDiscountCents'],
            source=r['source'],sourceRow=r['sourceRow'],recognition='REDUCAO_UNICA',
            state='PREVISTO',active=False,linkStatus='AGUARDANDO_MATRICULA' if r['classId'] else 'TURMA_INVALIDA',
            enrollmentId=None,history=[])
        if bid in existing:
            old=existing[bid]
            fixed=('studentKey','classId','sourceClass','rate','grossCents','discountCents','postDiscountCents')
            if any(old.get(k)!=candidate[k] for k in fixed):raise ValueError('Benefício existente diverge; requer conciliação: '+bid)
        else:result['benefits'].append(candidate);existing[bid]=candidate
    sync_benefits(result)
    return result


def nominal_enrollments(state):
    """Quantidades agregadas não provam identidade. Aceita roster ou lançamento unitário nominal."""
    entries=[]
    roster=state.get('enrollments',{}).get('students',[])
    cancelled={(str(x.get('studentId') or '').strip() or 'name:'+normalized(x.get('studentName')),x.get('classId')) for x in roster if x.get('year')==2027 and x.get('status')=='cancelled'}
    for x in state.get('enrollments',{}).get('students',[]):
        if x.get('year')==2027 and x.get('status')=='active':entries.append(x)
    for x in state.get('enrollments',{}).get('history',[]):
        identity=(str(x.get('studentId') or '').strip() or 'name:'+normalized(x.get('studentName')),x.get('classId'))
        if identity in cancelled:continue
        if x.get('year',state.get('academicDataYear'))==2027 and x.get('quantity')==1 and (x.get('studentId') or x.get('studentName')) and not x.get('supersededByClassUpdate') and x.get('status','active')=='active':
            entries.append(x)
    # Um mesmo vínculo pode vir no cadastro nominal e no lançamento; não são dois alunos.
    unique={}
    for x in entries:
        eid=str(x.get('id',''));sid=str(x.get('studentId') or '').strip();name=normalized(x.get('studentName'))
        key=(sid or 'entry:'+eid+':'+name,x.get('classId'))
        if not sid and not name:continue
        unique.setdefault(key,dict(id=eid,studentId=sid,studentKey=name,classId=x.get('classId')))
    return list(unique.values())


def sync_benefits(state):
    records=[b for b in state.get('benefits',[]) if is_planned(b)]
    if not records:return []
    enrollments=nominal_enrollments(state)
    names=Counter(e['studentKey'] for e in enrollments if e['studentKey'])
    ids=Counter(e['studentId'] for e in enrollments if e['studentId'])
    benefit_names=Counter(b['studentKey'] for b in records)
    rooms={c['id']:c for c in state['classes']}
    class_counts=Counter(e['classId'] for e in enrollments)
    changes=[]
    for b in records:
        previous=(b['state'],b.get('enrollmentId'),b.get('linkStatus'))
        matched=[];status='AGUARDANDO_MATRICULA'
        if b['classId'] not in rooms:status='TURMA_INVALIDA'
        else:
            # ID conhecido divergente nunca é vencido por semelhança/igualdade de nome.
            if b.get('studentId'):
                matched=[e for e in enrollments if e['studentId']==b['studentId']]
                if not matched:
                    matched=[e for e in enrollments if not e['studentId'] and e['studentKey']==b['studentKey']]
            else:matched=[e for e in enrollments if e['studentKey']==b['studentKey']]
            if len(matched)>1 or (matched and (benefit_names[b['studentKey']]>1 or (not b.get('studentId') and names[b['studentKey']]>1))):
                status='IDENTIDADE_AMBIGUA';matched=[]
            elif matched and matched[0]['classId']!=b['classId']:status='TURMA_DIVERGENTE';matched=[]
            elif matched and class_counts[b['classId']]>rooms[b['classId']].get('students',0):status='ROSTER_EXCEDE_MATRICULAS';matched=[]
            elif matched:status='VINCULADO'
        b['active']=bool(matched);b['state']='ATIVO' if matched else 'PREVISTO'
        b['enrollmentId']=matched[0]['id'] if matched else None;b['linkStatus']=status
        current=(b['state'],b['enrollmentId'],b['linkStatus'])
        if current!=previous:
            event=dict(action='VINCULO_AUTOMATICO',before=list(previous),after=list(current),
                identityRule='ID exato; ou nome normalizado exato e único, sem ID conflitante; turma 2027 idêntica')
            b.setdefault('history',[]).append(event);changes.append(dict(id=b['id'],**event))
    return changes


def summarize(state):
    records=[b for b in state.get('benefits',[]) if is_planned(b)]
    groups=defaultdict(list)
    for b in records:
        if b['classId']:groups[b['classId']].append(b)
    rows=[]
    nominal=nominal_enrollments(state)
    for c in state['classes']:
        group=groups[c['id']];active=[b for b in group if b['state']=='ATIVO'];count=c.get('students',0)
        def finances(items):
            gross=sum(b['grossCents'] for b in items);discount=sum(b['discountCents'] for b in items)
            net=money(Decimal(gross-discount)*Decimal('.955')) if items else None
            return dict(count=len(items),grossCents=gross,discountCents=discount,netCents=net,ticketCents=net/len(items) if items else None)
        planned=finances(group);actual=finances(active)
        # Ticket atual da turma exige cobertura de todos os matriculados; não extrapola benefícios previstos.
        complete=(len(active)==count and len([e for e in nominal if e['classId']==c['id']])==count)
        rows.append(dict(classId=c['id'],name=c['name'],plannedCount=len(group),activeCount=len(active),
            waitingCount=sum(b['state']=='PREVISTO' and b['linkStatus']=='AGUARDANDO_MATRICULA' for b in group),
            pendingCount=sum(b['linkStatus'] not in ('VINCULADO','AGUARDANDO_MATRICULA') for b in group),
            planned=planned,active=actual,currentComplete=complete,
            currentTicketCents=actual['ticketCents'] if complete and count else None,
            currentRevenueCents=(actual['netCents'] if count else 0) if complete else None,
            mix=dict(Counter(b['name']+' / '+str(Decimal(b['rate'])*100)+'%' for b in group))))
    return dict(total=len(records),active=sum(b['state']=='ATIVO' for b in records),
        waiting=sum(b['state']=='PREVISTO' and b['linkStatus']=='AGUARDANDO_MATRICULA' for b in records),
        pending=sum(b['linkStatus'] not in ('VINCULADO','AGUARDANDO_MATRICULA') for b in records),
        classifications=dict(Counter('B' if b['state']=='ATIVO' else 'A' if b['linkStatus']=='AGUARDANDO_MATRICULA' else 'C' if b['linkStatus']=='TURMA_INVALIDA' else 'D' for b in records)),rows=rows)


def apply_benefit_view(report,state):
    """PE usa mix previsto; caixa atual usa somente vínculos nominais efetivos."""
    result=deepcopy(report);summary=summarize(state);by_id={r['classId']:r for r in summary['rows']}
    from pe_real import ceil_ratio
    for r in result['rows']:
        b=by_id[r['id']];planned=b['planned']
        r.update(plannedBenefitCount=b['plannedCount'],activeBenefitCount=b['activeCount'],waitingBenefitCount=b['waitingCount'],
            pendingBenefitCount=b['pendingCount'],plannedTicketCents=planned['ticketCents'],currentTicketCents=b['currentTicketCents'],
            activeCoveredRevenueCents=b['active']['netCents'],currentRevenueCents=b['currentRevenueCents'],currentRevenueComplete=b['currentComplete'],
            plannedMixConfirmed=True,plannedBenefitMix=b['mix'])
        r['ticketCents']=planned['ticketCents']
        r['pe']=ceil_ratio(r['consideredCostCents']*planned['count'],planned['netCents']) if r['consideredCostCents'] is not None and planned['count'] else None
        previous_assumption=r.pop('planningAssumption',None)
        if previous_assumption:
            r['averageFinancialDiscountCents']=planned['discountCents']/planned['count'] if planned['count'] else None
        # Premissa exclusiva dos ingressantes 2027; qualquer mix individual a substitui.
        if r['id'] in ('caj-2027-caj-g2-a','caj-2027-caj-g2-b') and not planned['count']:
            ticket=Decimal('93069')*Decimal('.88')*Decimal('.955')
            r['planningAssumption']=dict(discountPercent=12,delinquencyPercent=4.5,
                tuitionCents=93069,ticketExactCents=str(ticket),
                source='Regra do usuário confirmada em 21/09/2026: ingressantes G2 2027',
                replacedBy='Mix individual previsto da própria turma, quando cadastrado')
            r['ticketCents']=r['plannedTicketCents']=float(ticket)
            r['averageFinancialDiscountCents']=float(Decimal('93069')*Decimal('.12'))
            r['plannedMixConfirmed']=False
            r['pe']=ceil_ratio(Decimal(r['consideredCostCents']),ticket) if r['consideredCostCents'] is not None else None
        if r['id'] in ('caj-2027-caj-g2-a','caj-2027-caj-g2-b'):
            r['status']='PARCIALMENTE COMPROVADO' if r['pe'] is not None else 'EM AUDITORIA'
            r['physicalMargin']=r['capacity']-r['pe'] if r['pe'] is not None else None
            r['percentCapacity']=r['pe']/r['capacity']*100 if r['pe'] is not None and r['capacity'] else None
            ticket=Decimal(r['planningAssumption']['ticketExactCents']) if r.get('planningAssumption') else (Decimal(planned['netCents'])/planned['count'] if planned['count'] else None)
            revenue=money(ticket*r['enrolled']) if ticket is not None else (0 if not r['enrolled'] else None)
            r['projectedRevenueCents']=revenue
            r['projectedResultCents']=revenue-r['consideredCostCents'] if revenue is not None and r['consideredCostCents'] is not None else None
            r['revenueProjectionStatus']='ESTIMATIVA_PREMISSA_G2_12' if r.get('planningAssumption') else 'ESTIMATIVA_COM_MIX_DA_PLANILHA'
        r['distanceToPE']=r['enrolled']-r['pe'] if r['pe'] is not None else None
        r['enrollmentSituation']=('abaixo do ponto de equilíbrio' if r['distanceToPE']<0 else 'no ponto de equilíbrio' if r['distanceToPE']==0 else 'acima do ponto de equilíbrio') if r['pe'] is not None else 'PE pendente'
        r['currentResultCents']=b['currentRevenueCents']-r['consideredCostCents'] if b['currentRevenueCents'] is not None and r['consideredCostCents'] is not None else None
        r['note']='PE de planejamento pelo mix completo de benefícios previstos 2027, confirmado pelo financeiro. Matrículas ativam benefícios, sem excluir previstos. Custo ainda sujeito à ponte nominal/documental. Receita atual exige vínculo nominal.'
        r['confidenceReason']='Mix previsto confirmado pelo financeiro. A classificação parcial decorre da conciliação de custos ainda não integral; confiança não é probabilidade estatística.'
        if r.get('planningAssumption'):
            r['note']='Planejamento G2 2027: R$ 930,69 × 0,88 × 0,955 = R$ 782,151876; PE = teto(custo / ticket exato). Premissa de 12% aplicada uma única vez, substituída pelo mix individual quando existir. Não cria benefícios nem comprova caixa atual.'
            r['confidenceReason']='Premissa G2 confirmada pelo usuário; composição nominal dos custos ainda pendente. PE documental 15 preservado como referência histórica.'
    result['summary']['partial']=sum(r['status']=='PARCIALMENTE COMPROVADO' for r in result['rows'])
    result['summary']['audit']=sum(r['status']=='EM AUDITORIA' for r in result['rows'])
    result['enrollmentSummary']['knownProjectedRevenueCents']=sum(r['projectedRevenueCents'] or 0 for r in result['rows'])
    result['enrollmentSummary']['missingRevenueClasses']=sum(r['projectedRevenueCents'] is None for r in result['rows'])
    result['benefitSummary']={k:v for k,v in summary.items() if k!='rows'}
    result['benefitPolicy']='Base antecipada confirmada; 1016 versus 775 não é divergência. Não criar matrículas. 114 casos têm turma ausente, não falta de matrícula.'
    return result
