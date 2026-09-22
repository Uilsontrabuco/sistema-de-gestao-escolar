"""Fotografia documental de matrículas; projeção não altera o custo ou PE."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
from pe_real import money

SOURCE=Path(__file__).with_name('enrollment_2027_source.json')


def snapshot():return json.loads(SOURCE.read_text(encoding='utf-8'))


def apply_snapshot_to_state(state, data=None):
    data=data or snapshot();result=deepcopy(state)
    by_id={r['id']:r for r in data['rows']}
    if set(by_id)!=set(c['id'] for c in result['classes']):raise ValueError('Cadastro de turmas divergente')
    for c in result['classes']:
        row=by_id[c['id']]
        history=[h for h in result['enrollments']['history'] if h.get('classId')==c['id']]
        new=sum(h['quantity'] for h in history if h['type']=='new')
        re=sum(h['quantity'] for h in history if h['type']=='re')
        if new>row['new'] or re>row['re']:raise ValueError('Histórico excede fotografia; requer conciliação sem apagar lançamentos')
        c.update(capacity=row['capacity'],opening={'new':row['new']-new,'re':row['re']-re},
            unclassified=0,students=row['students'],source=data['source'])
    if any(result['enrollments'].get('unallocated',{}).values()):raise ValueError('Matrícula não alocada impede fotografia completa')
    result['enrollments']['new']=sum(r['new'] for r in data['rows'])
    result['enrollments']['re']=sum(r['re'] for r in data['rows'])
    result['enrollmentDocumentarySource']={k:data[k] for k in ('source','sha256','totals')}
    return result


def project_current(report,state=None,data=None):
    result=deepcopy(report)
    if state is None:
        data=data or snapshot();by_id={r['id']:r for r in data['rows']}
    else:
        by_id={}
        for c in state['classes']:
            h=[x for x in state.get('enrollments',{}).get('history',[]) if x.get('classId')==c['id']]
            new=c.get('opening',{}).get('new',0)+sum(x['quantity'] for x in h if x['type']=='new')
            re=c.get('opening',{}).get('re',0)+sum(x['quantity'] for x in h if x['type']=='re')
            by_id[c['id']]=dict(capacity=c['capacity'],students=new+re+c.get('unclassified',0),new=new,re=re)
    for r in result['rows']:
        c=by_id[r['id']];count=c['students'];pe=r['pe']
        r.update(capacity=c['capacity'],enrolled=count,newStudents=c['new'],reenrolled=c['re'],
            vacancies=c['capacity']-count,occupancyPercent=count/c['capacity']*100 if c['capacity'] else None,
            distanceToPE=count-pe if pe is not None else None,
            enrollmentSituation=('abaixo do ponto de equilíbrio' if count<pe else 'no ponto de equilíbrio' if count==pe else 'acima do ponto de equilíbrio') if pe is not None else 'PE pendente',
            physicalMargin=c['capacity']-pe if pe is not None else None,
            percentCapacity=pe/c['capacity']*100 if pe is not None and c['capacity'] else None)
        # Mix é uma hipótese de projeção, não afirmação de identidade da matrícula.
        revenue=money(Decimal(r['netRevenueCents'])*count/r['acceptedStudentCount']) if (r['completeMix'] or r.get('partialMixAuthorized')) and r['acceptedStudentCount'] else (0 if count==0 else None)
        if r.get('planningAssumption'):
            revenue=money(Decimal(r['planningAssumption']['ticketExactCents'])*count)
        r['projectedRevenueCents']=revenue
        r['projectedResultCents']=revenue-r['consideredCostCents'] if revenue is not None and r['consideredCostCents'] is not None else None
        r['revenueProjectionStatus']='ESTIMATIVA_COM_MIX_DA_PLANILHA' if revenue is not None else 'MIX_PENDENTE'
        if r.get('planningAssumption'):r['revenueProjectionStatus']='ESTIMATIVA_PREMISSA_G2_12'
    result['enrollmentSummary']=dict(capacity=sum(r['capacity'] for r in result['rows']),
        enrolled=sum(r['enrolled'] for r in result['rows']),new=sum(r['newStudents'] for r in result['rows']),
        re=sum(r['reenrolled'] for r in result['rows']),vacancies=sum(r['vacancies'] for r in result['rows']),
        knownProjectedRevenueCents=sum(r['projectedRevenueCents'] or 0 for r in result['rows']),
        missingRevenueClasses=sum(r['projectedRevenueCents'] is None for r in result['rows']))
    return result
