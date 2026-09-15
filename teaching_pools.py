"""Fechamento financeiro autorizado; tempos documentais não viram duração presumida."""
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction


def apply_financial_pools(result):
    from teaching_cost import money, split_cents
    rows = result['occurrences']
    classes = {c['class_id']: c for c in result['classes']}
    g5 = sorted(c['class_id'] for c in classes.values() if c['class_name'] in ('G5 A','G5 B','G5 C'))
    logs, pools = [], []

    def allocate(template, ids, amount, fraction, minutes, rule):
        parts = []
        for cid, cost in zip(sorted(ids), split_cents(amount, len(ids))):
            f = fraction / len(ids)
            p = dict(template, class_id=cid, candidate_class_id=cid,
                weekly_cost=float(cost), fraction=float(f), fraction_numerator=f.numerator,
                fraction_denominator=f.denominator, allocated_minutes=float(minutes / len(ids)),
                shared=True, status='ALOCADO_REFERENCIA', pending_reasons=[],
                link_status='CONCILIADO', link_basis=rule)
            parts.append(p)
        return parts

    # Blocos são os componentes conexos dos cruzamentos já identificados.
    adjacency = {}
    for a,b in result['overlap_pairs']:
        if rows[a]['professor_id']=='590' and rows[b]['professor_id']=='590':
            adjacency.setdefault(a,set()).add(b)
            adjacency.setdefault(b,set()).add(a)
    consumed = set()
    for first in sorted(adjacency):
        if first in consumed:
            continue
        block, stack = set(), [first]
        while stack:
            i=stack.pop()
            if i not in block:
                block.add(i); stack.extend(adjacency[i]-block)
        members=[rows[i] for i in sorted(block)]
        original_parts=[p for r in members for p in r['allocations']]
        if any(p['status']!='PENDENTE' or p['weekly_cost'] is None for p in original_parts):
            continue
        ids=set()
        source_destinations={}
        for p in original_parts:
            if p['source_code'].startswith('EINFA05') and len(g5)==3:
                targets=set(g5)
            elif p['candidate_class_id']:
                targets={p['candidate_class_id']}
            else:
                targets={c['class_id'] for c in p.get('possible_destinations',[])}
            ids.update(targets)
            source_destinations.setdefault(p['source_code'],set()).update(targets)
        if not ids or any(not p['candidate_class_id'] and not p.get('possible_destinations')
                and not (p['source_code'].startswith('EINFA05') and len(g5)==3) for p in original_parts):
            continue
        amount=sum((money(p['weekly_cost']) for p in original_parts),Decimal())
        pool_id='SHARED_POOL_'+members[0]['occurrence_id']
        pool=dict(pool_id=pool_id,professor_id='590',
            occurrence_ids=[r['occurrence_id'] for r in members],
            source_allocations=deepcopy(original_parts),
            source_times=[{k:r[k] for k in ('occurrence_id','start','duration_minutes','page','evidence')} for r in members],
            cost_cents=int(amount*100),participant_class_ids=sorted(ids),
            documentary_status='SOURCE_TIME_REVIEW',reason='SHARED_BLOCK_SOURCE_TIMES_DIFFER',
            duration_minutes=None)
        template=dict(original_parts[0],source_codes=sorted({p['source_code'] for p in original_parts}),
            disciplines=sorted({d for p in original_parts for d in p['disciplines']}),
            pool_id=pool_id,minutes_status='SOURCE_TIME_REVIEW',
            link_source_reference=[{'pool_id':pool_id,'occurrence_ids':pool['occurrence_ids']}])
        for r in members:
            r.update(documentary_allocations=deepcopy(r['allocations']),
                documentary_reference_weekly_cost=r['reference_weekly_cost'],
                documentary_status='SOURCE_TIME_REVIEW',documentary_reason='SHARED_BLOCK_SOURCE_TIMES_DIFFER',
                pool_id=pool_id,allocations=[],pending_reasons=[],reference_weekly_cost=0,
                financial_absorbed_into=members[0]['occurrence_id'])
        representative=members[0]
        representative.pop('financial_absorbed_into')
        representative['reference_weekly_cost']=float(amount)
        representative['allocations']=allocate(template,ids,amount,Fraction(1),Fraction(),
            'POOL_COMPARTILHADO_CONFIRMADO_PELO_USUARIO')
        for p in representative['allocations']:
            p['source_codes']=sorted(code for code,targets in source_destinations.items() if p['class_id'] in targets)
            p['source_code']=p['source_codes'][0]
        assert sum(int(money(p['weekly_cost'])*100) for p in representative['allocations']) == pool['cost_cents']
        pools.append(pool);consumed.update(block)
        logs.append(dict(action='POOL_COMPARTILHADO_CONFIRMADO_PELO_USUARIO',**pool))
        if any(p['source_code'].startswith('EINFA05') for p in original_parts):
            logs.append(dict(action='RATEIO_G5_ABC_CONFIRMADO_PELO_USUARIO',pool_id=pool_id,class_ids=g5))

    for r in rows:
        allocations=[]
        for p in r['allocations']:
            if (p['status']=='PENDENTE' and p['source_code'].startswith('EINFA05')
                    and not r['pending_reasons'] and len(g5)==3 and p['weekly_cost'] is not None):
                r.setdefault('documentary_allocations',deepcopy(r['allocations']))
                allocations.extend(allocate(p,g5,money(p['weekly_cost']),
                    Fraction(p['fraction_numerator'],p['fraction_denominator']),
                    Fraction(str(p['allocated_minutes'])),'RATEIO_G5_ABC_CONFIRMADO_PELO_USUARIO'))
                logs.append(dict(action='RATEIO_G5_ABC_CONFIRMADO_PELO_USUARIO',
                    occurrence_id=r['occurrence_id'],source_allocation=deepcopy(p),class_ids=g5))
            else:
                allocations.append(p)
        r['allocations']=allocations
        for p in allocations:
            f=Fraction(int(money(p['weekly_cost'])*100),int(money(r['reference_weekly_cost'])*100)) if p['weekly_cost'] is not None and r['reference_weekly_cost'] else Fraction(p['fraction_numerator'],p['fraction_denominator'])
            p.update(financial_fraction_numerator=f.numerator,financial_fraction_denominator=f.denominator)

    result['documentary_overlap_pairs']=[p for p in result['overlap_pairs'] if set(p)<=consumed]
    result['overlap_pairs']=[p for p in result['overlap_pairs'] if not set(p)<=consumed]
    result['financial_pools']=pools
    result['financial_closure_log']=logs
    # Reconstituir os índices exclusivamente a partir das parcelas canônicas.
    for c in classes.values():
        c.update(weekly_cost=Decimal(),weekly_minutes=Fraction(),occurrences=set(),teachers=set())
    teachers={t['professor_id']:t for t in result['professors']}
    for t in teachers.values():
        t.update(allocated_weekly_cost=Decimal(),pending_weekly_cost=Decimal())
    for r in rows:
        for p in r['allocations']:
            if p['weekly_cost'] is None:continue
            t=teachers[r['professor_id']];cost=money(p['weekly_cost'])
            if p['status']=='ALOCADO_REFERENCIA':
                c=classes[p['class_id']];c['weekly_cost']+=cost
                c['weekly_minutes']+=Fraction() if p.get('pool_id') else Fraction(r['duration_minutes']*p['fraction_numerator'],p['fraction_denominator'])
                c['occurrences'].add(r['source_index']);c['teachers'].add(r['professor_id'])
                t['allocated_weekly_cost']+=cost
            else:t['pending_weekly_cost']+=cost
    for c in classes.values():
        c.update(weekly_cost=float(c['weekly_cost']),weekly_minutes=float(c['weekly_minutes']),
            occurrences=sorted(c['occurrences']),teachers=sorted(c['teachers']))
    for t in teachers.values():
        t.update(allocated_weekly_cost=float(t['allocated_weekly_cost']),pending_weekly_cost=float(t['pending_weekly_cost']))
    for c in result['source_classes']:
        c['pending_weekly_cost']=float(sum((money(p['weekly_cost']) for r in rows for p in r['allocations']
            if p['source_code']==c['source_code'] and p['status']=='PENDENTE' and p['weekly_cost'] is not None),Decimal()))
    for r in rows:
        if r.get('pool_id'):
            r['physical_minutes_status']='SOURCE_TIME_REVIEW'
    for t in teachers.values():
        if any(r.get('pool_id') and r['professor_id']==t['professor_id'] for r in rows):
            t['minutes_basis']='DOCUMENTARY_SOURCE_MINUTES_NOT_UNIQUE_PHYSICAL_DURATION'
            t['physical_weekly_minutes']=None
            t['documentary_records']=t['records']
    result['summary'].update(allocated_weekly_cost=sum(int(money(c['weekly_cost'])*100) for c in classes.values())/100,
        pending_weekly_cost=sum(int(money(t['pending_weekly_cost'])*100) for t in teachers.values())/100,
        allocated_minutes=sum(c['weekly_minutes'] for c in classes.values()),
        overlap_pairs=len(result['overlap_pairs']),conflicting_records=len({i for p in result['overlap_pairs'] for i in p}),
        documentary_time_observations=sum(r.get('documentary_status')=='SOURCE_TIME_REVIEW' for r in rows))
    result['summary']['financial_units']=sum(not r.get('financial_absorbed_into') for r in rows)
    return result
