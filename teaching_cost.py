"""Custeio docente por ocorrência; consultas puras, sem lançamentos contábeis.

Valores mensais históricos são cenários explícitos, nunca salários certificados.
Custos sem vínculo e intervalos sobrepostos permanecem em contas de conciliação.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re

CENT = Decimal('0.01')
ROOT = Path(__file__).resolve().parent
SOURCE_HASH = '27115a2931183095d800989a7c700db61fbdb511e7a972e36e0d2d378c5088da'


def money(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def split_cents(value, count):
    cents = int(money(value) * 100)
    quotient, remainder = divmod(cents, count)
    return [Decimal(quotient + (i < remainder)) / 100 for i in range(count)]


def source_segment(code):
    if re.fullmatch(r'EINFA0[2-5][MT][A-Z]', code):
        return 'Educação Infantil'
    m = re.fullmatch(r'EFUND0([1-9])[MT][A-Z]', code)
    if m:
        return 'Fundamental I' if int(m[1]) <= 5 else 'Fundamental II'
    if re.fullmatch(r'(EMERE|EMICN|EMICH)0[1-3][MT][A-Z]', code):
        return 'Ensino Médio'
    return None


def minute(value):
    h, m = map(int, value.split(':'))
    if not 0 <= h < 24 or not 0 <= m < 60:
        raise ValueError('Horário inválido')
    return h * 60 + m


def reconcile_code(code, classes):
    """Equivalência de nomenclatura na projeção, sem alterar o cadastro.

    Legendas 2026 + Grupo 2–5 / seções A do EM no orçamento 2027 +
    nomes de Matrículas 2027. Não certifica continuidade de grade entre anos.
    Itinerários conservam código próprio, mas seu custo pertence ao ano/seção.
    """
    from services import normalize_teaching_class_code
    result = normalize_teaching_class_code(code, classes)
    name = None
    match = re.fullmatch(r'EINFA0([2-5])[MT]([A-Z])',code)
    if match: name = f'G{match[1]} {match[2]}'
    match = re.fullmatch(r'(EMERE|EMICN|EMICH)0([1-3])MA',code)
    if match: name = f'{match[2]}º EM'
    if name:
        targets = [c for c in classes if c['name']==name]
        result.update(operational_class_id=targets[0]['id'] if len(targets)==1 else None,
                      status='CONCILIADO' if len(targets)==1 else 'PENDENTE')
    result['basis']='Equivalência de ano/grupo e seção; projeção da grade 2026. Legendas + Orçamento 2027 pp.4,8–9 + Matrículas 2027.'
    return result


def structural_destination(code, record, classes, evidence):
    """Só usa correspondências documentadas completas; ausência não é compatibilidade."""
    normal = reconcile_code(code, classes)
    if normal['status'] == 'CONCILIADO':
        return normal
    if code == 'EINFA05TD':
        # A/B foram confirmadas de manhã. Só cadastro explícito resolve a
        # outra turma da tarde; ausência de turno não constitui evidência.
        candidates = [c for c in classes if c['name'].startswith('G5 ')
            and c['name'] not in ('G5 A', 'G5 B', 'G5 C')
            and c.get('turno', c.get('shift')) == 'Tarde']
        normal['possible_destinations'] = [dict(class_id=c['id'],class_name=c['name']) for c in candidates]
        if len(candidates) == 1:
            normal.update(status='CONCILIADO',operational_class_id=candidates[0]['id'],
                basis='REGRA_FINAL_G5_CADASTRO_REAL',
                source_reference=[{'rule':'REGRA_FINAL_G5_CADASTRO_REAL','class':dict(candidates[0])}])
        return normal
    if code == 'EFUND05TD':
        # A confirmação do usuário define os destinos pelo turno da grade,
        # não pela letra T ou D do código legado. Não propagar entre horários.
        shift = record.get('turno')
        names = {'Manhã':('5º A','5º B'), 'Tarde':('5º B','5º C')}.get(shift, ())
        candidates = [c for c in classes if c['name'] in names]
        normal['possible_destinations'] = [{'class_id':c['id'],'class_name':c['name']} for c in candidates]
        required = ('professor_id','disciplina_componente','dia_semana','hora_inicio',
                    'source_cell_x','source_cell_y','evidencia_original')
        try:
            time_matches = (minute(record['hora_inicio']) < 12*60) == (shift == 'Manhã')
        except (KeyError,ValueError,TypeError):
            time_matches = False
        if len(candidates)==2 and time_matches and all(record.get(f) is not None for f in required):
            # Na mesma célula compartilhada, os destinos já conciliados são
            # participantes distintos. Só o complemento único pode receber D.
            companions = [reconcile_code(c, classes) for c in set(record.get('source_class_codes',[])) if c!=code]
            occupied = {c['operational_class_id'] for c in companions if c['status']=='CONCILIADO'}
            remaining = [c for c in candidates if c['id'] not in occupied]
            if record.get('aula_compartilhada') and len(remaining)==1:
                normal.update(status='CONCILIADO',operational_class_id=remaining[0]['id'],
                    basis='RESOLVIDO_POR_CORRESPONDENCIA_UNICA',
                    source_reference=[{'rule':'TURMAS_5_ANO_CONFIRMADAS_PELO_USUARIO',
                        'shift':shift,'day':record['dia_semana'],'start':record['hora_inicio'],
                        'professor_id':record['professor_id'],'disciplines':record['disciplina_componente'],
                        'source_codes':record['source_class_codes'],'evidence':record['evidencia_original'],
                        'excluded_class_ids':sorted(occupied),'destination':remaining[0]['id']}])
                return normal
    fields = ('professor_id', 'disciplina_componente', 'ano_serie', 'turno',
              'duracao_minutos', 'dia_semana', 'hora_inicio', 'source_cell_x', 'source_cell_y')
    def compatible(item):
        target_code = item.get('target_code', '')
        if not code or target_code[:-1] != code[:-1]:
            return False
        target = reconcile_code(target_code, classes)
        return target['status'] == 'CONCILIADO' and target['operational_class_id'] == item.get('class_id')
    candidates = [item for item in evidence
                  if item.get('source_code') == code and item.get('source_reference')
                  and item.get('status') == 'VERIFICADO'
                  and item.get('segment') == source_segment(code)
                  and compatible(item)
                  and all(record.get(f) is not None and item.get(f) == record[f] for f in fields)
                  and item.get('class_id') in {c['id'] for c in classes}]
    ids = {item['class_id'] for item in candidates}
    if len(ids) == 1:
        normal.update(status='CONCILIADO', operational_class_id=next(iter(ids)),
                      basis='RESOLVIDO_POR_CORRESPONDENCIA_UNICA',
                      source_reference=[item['source_reference'] for item in candidates])
    return normal


def build_cost_ledger(preview, classes):
    """Regra confirmada pelo usuário: um professor/dia/intervalo, uma aula.

    Tarifas multissegmento permanecem separadas na mesma ocorrência física.
    Transições e turno confirmado seguem as decisões finais. Compartilhamentos
    sem duração única determinada continuam em conferência.
    A extração original é preservada integralmente no rastro documental.
    """
    from services import TEACHING_HOUR_AULA_REAJUSTED_2027
    original = preview.get('records', [])
    groups = defaultdict(list)
    for i, row in enumerate(original):
        if row.get('professor_id') and row.get('dia_semana') and row.get('hora_inicio'):
            groups[(str(row['professor_id']), row['dia_semana'], row['hora_inicio'])].append(i)
    replacements, consumed, events = {}, set(), []
    for indices in groups.values():
        if len(indices) < 2:
            continue
        rows = [original[i] for i in indices]
        codes = sorted({c for r in rows for c in r.get('source_class_codes', [])})
        if len(codes) < 2 or len({r.get('duracao_minutos') for r in rows}) != 1:
            continue
        if any(r.get('status_temporal') != 'CONFIRMADO' or r.get('duracao_minutos') not in (40,45,50) for r in rows):
            continue
        try:
            if any(r.get('hora_fim') and minute(r['hora_fim']) != minute(r['hora_inicio'])+r['duracao_minutos'] for r in rows):
                continue
        except (ValueError, TypeError):
            continue
        rates = {TEACHING_HOUR_AULA_REAJUSTED_2027.get(source_segment(c)) for c in codes}
        mixed = {source_segment(c) for c in codes} == {'Fundamental II', 'Ensino Médio'}
        if None in rates or (len(rates) != 1 and not mixed):
            continue
        # Sem escolha arbitrária entre códigos que representem a mesma turma.
        targets = [reconcile_code(c, classes).get('operational_class_id') for c in codes]
        known = [t for t in targets if t is not None]
        if len(known) != len(set(known)):
            continue
        disciplines = defaultdict(set)
        for r in rows:
            components = str(r.get('disciplina_componente') or '').split(' | ')
            if len(components) != len(r.get('source_class_codes', [])):
                break
            for c, component in zip(r['source_class_codes'], components):
                disciplines[c].add(component)
        else:
            merged = dict(rows[0], source_class_codes=codes, aula_compartilhada=True,
                disciplina_componente=' | '.join(' / '.join(sorted(disciplines[c])) for c in codes),
                evidencia_original='REGRA_USUARIO_AULA_COMPARTILHADA; '+ ' || '.join(
                    f"origem {i+1}, página {original[i].get('pagina')}: {original[i].get('evidencia_original')}" for i in indices))
            replacements[indices[0]] = merged
            consumed.update(indices[1:])
            cost = sum((money(v) for v in rates), Decimal()) if mixed else money(next(iter(rates)))
            previous = sum((money(TEACHING_HOUR_AULA_REAJUSTED_2027[source_segment(r['source_class_codes'][0])]) for r in rows),Decimal())
            if mixed:
                merged['segment_costs_confirmed'] = True
            events.append({'action':'REGRA_USUARIO_AULA_COMPARTILHADA', 'source_indices':indices,
                'professor_id':str(rows[0]['professor_id']), 'day':rows[0]['dia_semana'],
                'start':rows[0]['hora_inicio'], 'duration_minutes':rows[0]['duracao_minutos'],
                'source_codes':codes, 'previous_reference_cost':float(previous),
                'new_reference_cost':float(cost), 'reference_reduction':float(previous-cost),
                'evidence':'Confirmação explícita do usuário: mesma aula compartilhada, rateio igualitário.'})
    records, provenance = [], []
    for i, row in enumerate(original):
        if i not in consumed:
            records.append(replacements.get(i, row))
            provenance.append(next((e['source_indices'] for e in events if e['source_indices'][0]==i), [i]))
    result = _build_cost_ledger({**preview, 'records':records}, classes)
    for row, indices in zip(result['occurrences'], provenance):
        row['original_source_indices'] = indices
        row['original_source_references'] = [{'source_index':i, 'page':original[i].get('pagina'),
            'evidence':original[i].get('evidencia_original')} for i in indices]
    result['audit_log'].extend(events)
    for row in result['occurrences']:
        if row.get('confirmed_shift'):
            result['audit_log'].append({'action':'TURNO_MANHA_CONFIRMADO_PELO_USUARIO',
                'source_reference':row['original_source_references'],
                'original_start':row['start'],'confirmed_shift':'Manhã'})
        if row.get('shared_confirmed'):
            result['audit_log'].append({'action':'SHARED_BLOCK_SOURCE_TIMES_DIFFER' if row.get('pool_id') else 'COMPARTILHAMENTO_CONFIRMADO_DURACAO_PENDENTE',
                'source_reference':row['original_source_references'],
                'reason':row['shared_resolution']})
    result['audit_log'].extend(result['transitions'])
    result['source_records'] = original
    result['summary']['original_source_records'] = len(original)
    result['summary']['user_shared_groups'] = len(events)
    result['summary']['reference_reduction'] = float(sum((money(e['reference_reduction']) for e in events),Decimal()))
    result['summary']['original_reference_cost'] = float(money(result['summary']['reference_weekly_cost'])+money(result['summary']['reference_reduction']))
    assert sorted(i for group in provenance for i in group) == list(range(len(original)))
    return result


def _build_cost_ledger(preview, classes):
    from services import TEACHING_HOUR_AULA_REAJUSTED_2027
    records = preview.get('records', [])
    by_id = {r['id']: r for r in classes}
    if len(by_id) != len(classes):
        raise ValueError('IDs de turma repetidos')
    intervals = defaultdict(list)
    invalid = set()
    duplicates = {}
    seen = {}
    for i, r in enumerate(records):
        # Mesma célula física e conteúdo integral: não confundir aulas distintas.
        fields = ('pagina', 'source_cell_x', 'source_cell_y', 'professor_id',
                  'dia_semana', 'hora_inicio', 'duracao_minutos', 'disciplina_componente')
        if all(r.get(f) is not None for f in fields):
            key = json.dumps([r[f] for f in fields] + [r.get('source_class_codes')], sort_keys=True)
            if key in seen:
                duplicates[i] = seen[key]
            else:
                seen[key] = i
    for i, r in enumerate(records):
        try:
            duration = r['duracao_minutos']
            if duration not in (40, 45, 50) or r.get('status_temporal') != 'CONFIRMADO' or not r.get('professor_id') or not r.get('dia_semana'):
                raise ValueError('Intervalo incompleto')
            start = minute(r['hora_inicio'])
            if r.get('hora_fim') and minute(r['hora_fim']) != start + duration:
                raise ValueError('Fim não reconcilia com duração')
            if i not in duplicates:
                # Confirmação do turno não inventa uma conversão de relógio.
                morning = (str(r['professor_id']) == '864'
                    and r.get('disciplina_componente') in ('SOCIO','DESOC','DEFIL')
                    and all(source_segment(c)=='Ensino Médio' for c in r.get('source_class_codes',[])))
                period = 'MANHA_CONFIRMADA' if morning else 'GRADE_ORIGINAL'
                intervals[(str(r['professor_id']), r['dia_semana'], period)].append((start, start+duration, i))
        except (KeyError, ValueError, TypeError):
            invalid.add(i)
    conflicts = set()
    overlap_pairs = []
    transitions = []
    for group in intervals.values():
        group.sort()
        for pos, (start, end, idx) in enumerate(group):
            for right_start, right_end, right_idx in group[pos+1:]:
                if right_start >= end:
                    break
                if (str(records[idx].get('professor_id')) in ('579','868')
                        and min(end,right_end)-right_start == 5 and start != right_start):
                    transitions.append([idx,right_idx])
                    continue
                conflicts.update((idx, right_idx))
                overlap_pairs.append([idx, right_idx])
    teachers = {}
    class_rows = {r['id']: {'class_id': r['id'], 'class_name': r['name'], 'weekly_minutes': Fraction(), 'weekly_cost': Decimal(0), 'occurrences': set(), 'teachers': set(), 'monthly_direct_cost': None, 'direct_cost_status': 'PENDENTE'} for r in classes}
    code_rows = {}
    ledger = []
    for i, r in enumerate(records):
        teacher_id = str(r.get('professor_id') or 'SEM_ID:'+r.get('professor',''))
        t = teachers.setdefault(teacher_id, {'professor_id': teacher_id, 'professor': r.get('professor'), 'records': 0, 'weekly_minutes': 0, 'reference_weekly_cost': Decimal(0), 'allocated_weekly_cost': Decimal(0), 'pending_weekly_cost': Decimal(0), 'unknown_cost_records': 0, 'conflicting_records': 0, 'monthly_salary': None})
        t['records'] += 1
        duration = r.get('duracao_minutos')
        t['weekly_minutes'] += duration if duration in (40,45,50) else 0
        t['conflicting_records'] += i in conflicts
        codes = sorted(set(str(c).strip().upper() for c in r.get('source_class_codes',[]) if c))
        segments = [source_segment(c) for c in codes]
        rates = {TEACHING_HOUR_AULA_REAJUSTED_2027[s] for s in segments if s}
        reasons = []
        if i in duplicates: reasons.append('DUPLICATA_NAO_CONTABILIZADA')
        if i in conflicts: reasons.append('SOBREPOSICAO_TEMPORAL')
        if i in invalid: reasons.append('INTERVALO_INVALIDO')
        mixed = r.get('segment_costs_confirmed') and set(segments)=={'Fundamental II','Ensino Médio'}
        if not codes or None in segments or (len(rates) != 1 and not mixed): reasons.append('TARIFA_NAO_COMPROVADA')
        if len(codes) > 1 and not r.get('aula_compartilhada'): reasons.append('COMPARTILHAMENTO_NAO_COMPROVADO')
        cost = (sum((money(v) for v in rates),Decimal()) if mixed else money(next(iter(rates)))) if codes and None not in segments and (len(rates)==1 or mixed) and i not in invalid else None
        row = {'occurrence_id': f'O{i+1:04}', 'source_index': i, 'professor_id':teacher_id, 'professor':r.get('professor'), 'page': r.get('pagina'), 'day':r.get('dia_semana'), 'start':r.get('hora_inicio'), 'duration_minutes':duration, 'disciplines':r.get('disciplina_componente'), 'source_codes':codes, 'evidence':r.get('evidencia_original'), 'reference_weekly_cost':float(cost) if cost is not None else None, 'pending_reasons':reasons, 'allocations':[]}
        if cost is None:
            t['unknown_cost_records'] += 1
        else:
            t['reference_weekly_cost'] += cost
        parts = split_cents(cost,len(codes)) if cost is not None else [None]*len(codes)
        if mixed and cost is not None:
            segment_parts = {}
            for segment in sorted(set(segments)):
                selected = [c for c in codes if source_segment(c)==segment]
                segment_parts.update(zip(selected,split_cents(TEACHING_HOUR_AULA_REAJUSTED_2027[segment],len(selected))))
            parts = [segment_parts[c] for c in codes]
        row['segment_costs_confirmed'] = bool(mixed)
        row['transition_status'] = 'TRANSICAO_ENTRE_AULAS' if any(i in pair for pair in transitions) else None
        if str(r.get('professor_id'))=='864' and r.get('disciplina_componente') in ('SOCIO','DESOC','DEFIL'):
            row.update(confirmed_shift='Manhã',clock_time_status='HORARIO_ORIGINAL_PRESERVADO_SEM_CONVERSAO',
                shift_evidence='DECISAO_FINAL_USUARIO_4')
        if str(r.get('professor_id'))=='590' and i in conflicts:
            row.update(shared_confirmed=True,shared_resolution='DURACAO_UNICA_E_LIMITES_DO_BLOCO_NAO_DETERMINADOS')
            reasons.append('DURACAO_COMPARTILHADA_NAO_DETERMINADA')
        row['duplicate_of'] = f'O{duplicates[i]+1:04}' if i in duplicates else None
        target_ids = [structural_destination(c,r,classes,preview.get('class_evidence',[])) for c in codes]
        resolved_ids = [n['operational_class_id'] for n in target_ids if n['status']=='CONCILIADO']
        if len(resolved_ids) != len(set(resolved_ids)): reasons.append('DESTINO_REPETIDO')
        destinations = []
        for code, part, norm in zip(codes, parts, target_ids):
            fraction = Fraction(1, len(codes))
            candidates = norm.get('possible_destinations', [])
            shift = r.get('turno')
            try:
                time_matches = (minute(r['hora_inicio']) < 720) == (shift == 'Manhã')
            except (KeyError, ValueError, TypeError):
                time_matches = False
            if (code == 'EFUND05TD' and norm['status'] != 'CONCILIADO'
                    and len(candidates) == 2 and not reasons and part is not None
                    and shift in ('Manhã', 'Tarde') and time_matches):
                for candidate, half in zip(candidates, split_cents(part, 2)):
                    resolved = dict(norm, status='CONCILIADO',
                        operational_class_id=candidate['class_id'],
                        basis='REGRA_USUARIO_5_ANO_RATEIO_50_50',
                        source_reference=[{'rule':'REGRA_USUARIO_5_ANO_RATEIO_50_50',
                            'shift':shift, 'source_code':code,
                            'evidence':r.get('evidencia_original'),
                            'original_share':str(fraction), 'split':'1/2',
                            'destinations':candidates}])
                    destinations.append((code, half, resolved, fraction / 2))
            else:
                destinations.append((code, part, norm, fraction))
        for code, part, norm, fraction in destinations:
            target = by_id.get(norm.get('operational_class_id')) if norm['status']=='CONCILIADO' and not reasons else None
            minutes = duration * fraction if duration in (40,45,50) else Fraction()
            status = 'ALOCADO_REFERENCIA' if target and part is not None else 'PENDENTE'
            components = str(r.get('disciplina_componente') or '').split(' | ')
            original_codes = [str(c).strip().upper() for c in r.get('source_class_codes',[])]
            disciplines = sorted({components[j] for j,c in enumerate(original_codes) if c==code}) if len(components)==len(original_codes) else []
            allocation_reasons = list(reasons)
            if norm['status']!='CONCILIADO':allocation_reasons.append('SEM_TURMA_OPERACIONAL_CORRESPONDENTE')
            if not disciplines:allocation_reasons.append('COMPONENTES_SEM_CORRESPONDENCIA_INDIVIDUAL')
            allocation = {'source_code':code, 'class_id':target['id'] if target else None, 'candidate_class_id':norm.get('operational_class_id') if norm['status']=='CONCILIADO' else None, 'fraction':float(Fraction(1,len(codes))), 'allocated_minutes':float(minutes), 'weekly_cost':float(part) if part is not None else None, 'hour_aula_rate_2027':float(cost) if cost is not None else None,'disciplines':disciplines,'shared':len(codes)>1,'pending_reasons':allocation_reasons if status=='PENDENTE' else [], 'status':status, 'link_status':norm['status'], 'link_basis':norm['basis']}
            row['allocations'].append(allocation)
            allocation.update(fraction=float(fraction), fraction_numerator=fraction.numerator,
                fraction_denominator=fraction.denominator, shared=len(destinations)>1)
            if mixed:
                allocation['hour_aula_rate_2027'] = TEACHING_HOUR_AULA_REAJUSTED_2027[source_segment(code)]
            financial_fraction = Fraction(int(part*100),int(cost*100)) if part is not None and cost else fraction
            allocation.update(financial_fraction_numerator=financial_fraction.numerator,
                financial_fraction_denominator=financial_fraction.denominator)
            allocation['link_source_reference'] = norm.get('source_reference', [])
            allocation['possible_destinations'] = norm.get('possible_destinations', [])
            c = code_rows.setdefault(code, {'source_code':code, 'weekly_minutes':Fraction(), 'reference_weekly_cost':Decimal(0), 'pending_weekly_cost':Decimal(0), 'records':0})
            c['records'] += 1; c['weekly_minutes'] += minutes
            if part is not None:
                c['reference_weekly_cost'] += part
                if status == 'ALOCADO_REFERENCIA':
                    cl = class_rows[target['id']]
                    cl['weekly_cost'] += part; cl['weekly_minutes'] += minutes
                    cl['occurrences'].add(i); cl['teachers'].add(teacher_id)
                    t['allocated_weekly_cost'] += part
                else:
                    c['pending_weekly_cost'] += part; t['pending_weekly_cost'] += part
        ledger.append(row)
    total = sum((t['reference_weekly_cost'] for t in teachers.values()),Decimal(0))
    allocated = sum((c['weekly_cost'] for c in class_rows.values()),Decimal(0))
    pending = sum((t['pending_weekly_cost'] for t in teachers.values()),Decimal(0))
    if total != allocated+pending:
        raise ArithmeticError('Custo docente não reconciliado')
    def serialize(row):
        return {k: float(v) if isinstance(v,(Decimal,Fraction)) else sorted(v) if isinstance(v,set) else v for k,v in row.items()}
    result = {'status':'PROJECAO_2026_COM_TARIFAS_2027', 'source_year':2026, 'target_year':2027,
            'calculation_basis':'Ocorrência física única; tarifas 2027 por segmento preservadas. Rateio em centavos dentro de cada segmento quando houver tarifas distintas. Minutos originais preservados; transições não acrescentam custo. Compartilhamentos conforme decisões do usuário.',
            'monthly_basis':{'status':'HISTORICAL_SCENARIO_ONLY','weeks':4.5,'dsr':0.1667,'source':'SIMULAÇÃO PROFESSOR - SALARIO DO PREFESSOR.xlsx · Plan1!D4:D6 e C8; vigência 2027 não demonstrada'},
            'professors':[serialize(t) for t in sorted(teachers.values(),key=lambda t:t['professor'] or '')],
            'classes':[serialize(c) for c in class_rows.values()], 'source_classes':[serialize(c) for c in sorted(code_rows.values(),key=lambda c:c['source_code'])],
            'occurrences':ledger, 'overlap_pairs':overlap_pairs,
            'transitions':[{'status':'TRANSICAO_ENTRE_AULAS','occurrence_ids':[f'O{x+1:04}' for x in pair], 'overlap_minutes':5,'additional_cost_cents':0} for pair in transitions],
            'summary':{'records':len(records),'professors':len(teachers),'overlap_pairs':len(overlap_pairs),'conflicting_records':len(conflicts),'invalid_records':len(invalid),'weekly_minutes':sum(t['weekly_minutes'] for t in teachers.values()),'allocated_minutes':float(sum(c['weekly_minutes'] for c in class_rows.values())),'reference_weekly_cost':float(total),'allocated_weekly_cost':float(allocated),'pending_weekly_cost':float(pending),'unknown_cost_records':sum(t['unknown_cost_records'] for t in teachers.values()),'cost_difference':float(total-allocated-pending),'monthly_direct_cost':None},
            'accounting':{'additional_expense':0,'general_expense_allocation':0,'official_total_changed':False,'method':'Consolidação analítica; não cria despesa e não distribui despesas gerais.'}}
    from teaching_pools import apply_financial_pools
    return finalize_operational_view(enrich_cost_details(apply_financial_pools(result)))


def finalize_operational_view(result):
    """Contas documentais disjuntas em centavos; somente validadas são atribuídas."""
    teachers = {t['professor_id']: t for t in result['professors']}
    occurrences = {r['occurrence_id']: r for r in result['occurrences']}
    parts = []
    logs = list(result.get('financial_closure_log',[]))
    for row in result['occurrences']:
        source = {'document_sha256': SOURCE_HASH, 'page': row['page'],
                  'occurrence_id': row['occurrence_id'], 'evidence': row['evidence']}
        row['source_reference'] = source
        row_parts = []
        allocations = row['allocations'] or [dict(status='PENDENTE', pending_reasons=row['pending_reasons'],
            shared=False, weekly_cost=None, allocated_minutes=row['duration_minutes'] or 0,
            source_code=None, class_id=None, candidate_class_id=None, link_basis='', link_source_reference=[])]
        if row.get('financial_absorbed_into'):
            allocations=[]
        for i, p in enumerate(allocations):
            reasons = p['pending_reasons']
            if p['status'] == 'ALOCADO_REFERENCIA':
                status = 'COMPARTILHADO_RATEADO' if p['shared'] else 'VALIDADO_E_ATRIBUIDO'
                bucket = 'validated'
            elif 'DUPLICATA_NAO_CONTABILIZADA' in reasons:
                status, bucket = 'DUPLICATA_NAO_CONTABILIZADA', 'unassigned'
            elif 'SOBREPOSICAO_TEMPORAL' in reasons:
                status, bucket = 'CONFLITO_DOCUMENTAL', 'conflicted'
            elif 'SEM_TURMA_OPERACIONAL_CORRESPONDENTE' in reasons:
                status, bucket = 'SEM_DESTINO', 'unassigned'
            else:
                status, bucket = 'AGUARDANDO_CONFIRMACAO', 'conflicted'
            p.update(operational_status=status, allocation_id=f"{row['occurrence_id']}:P{i+1}",
                     source_reference=source, conflict_reason=reasons,
                     fraction_numerator=p.get('fraction_numerator', 1),
                     fraction_denominator=p.get('fraction_denominator', len(allocations)))
            part = {**p, 'status': status, 'professor_id': row['professor_id'],
                    'professor': row['professor'], 'bucket': bucket,
                    'duplicate_of': row['duplicate_of']}
            cents = int(money(p['weekly_cost'])*100) if p['weekly_cost'] is not None else None
            for name in ('validated', 'conflicted', 'unassigned'):
                part[name+'_cost_cents'] = cents if bucket == name else 0
                part[name+'_cost'] = None if bucket == name and cents is None else (cents or 0)/100 if bucket == name else 0
                part[name+'_minutes'] = p['allocated_minutes'] if bucket == name else 0
            part['reference_cost'] = p['weekly_cost']
            part['reference_cost_cents'] = cents
            row_parts.append(part)
            parts.append(part)
            if status == 'DUPLICATA_NAO_CONTABILIZADA':
                logs.append({'action':status, 'allocation_id':p['allocation_id'],
                             'duplicate_of':row['duplicate_of'], 'source_reference':source,
                             'previous_documentary_cost':p['weekly_cost'], 'assigned_cost':0})
            if p['link_basis'] in ('RESOLVIDO_POR_CORRESPONDENCIA_UNICA', 'REGRA_USUARIO_5_ANO_RATEIO_50_50'):
                logs.append({'action': p['link_basis'], 'allocation_id': p['allocation_id'],
                             'class_id': p['candidate_class_id'], 'source_reference': p['link_source_reference']})
        row['status'] = next((p['status'] for p in row_parts if p['bucket'] != 'validated'),
                             row_parts[0]['status'] if row_parts else 'AGUARDANDO_CONFIRMACAO')
        if row.get('financial_absorbed_into'):
            row['status']='COMPARTILHADO_RATEADO'
        row['conflict_reason'] = sorted(set(row['pending_reasons'] + [r for p in row_parts for r in p['conflict_reason']]))
    def totals(target, selected):
        for name in ('validated', 'conflicted', 'unassigned', 'reference'):
            values = [p[name+'_cost_cents'] for p in selected]
            target[name+'_cost_cents'] = sum(values) if all(v is not None for v in values) else None
            target[name+'_cost'] = target[name+'_cost_cents']/100 if target[name+'_cost_cents'] is not None else None
        for name in ('validated', 'conflicted', 'unassigned'):
            target[name+'_minutes'] = float(sum((Fraction() if p.get('pool_id') else Fraction(occurrences[p['source_reference']['occurrence_id']]['duration_minutes'] * p['fraction_numerator'],p['fraction_denominator'])
                for p in selected if p['bucket']==name and occurrences[p['source_reference']['occurrence_id']]['duration_minutes'] in (40,45,50)), Fraction()))
        target['conflict_reason'] = sorted({r for p in selected for r in p['conflict_reason']})
        target['source_reference'] = list({p['source_reference']['occurrence_id']:p['source_reference'] for p in selected}.values())
        if target['reference_cost_cents'] is not None:
            assert sum(target[n+'_cost_cents'] for n in ('validated','conflicted','unassigned')) == target['reference_cost_cents']
    for t in teachers.values():
        selected = [p for p in parts if p['professor_id'] == t['professor_id']]
        totals(t, selected)
        t['status'] = 'PROCESSADO_CONCILIADO' if t['weekly_status'] == 'CONCILIADO' else 'PROCESSADO_COM_RESSALVAS'
    for row in result['occurrences']:
        totals(row, [p for p in parts if p['source_reference']['occurrence_id']==row['occurrence_id']])
    totals(result, parts)
    validated = [p for p in parts if p['bucket']=='validated']
    financial_duplicates = len(validated)-len({p['allocation_id'] for p in validated})
    assert financial_duplicates == 0
    valid_occurrences = {p['source_reference']['occurrence_id'] for p in validated}
    assert not any(row['duplicate_of'] and row['occurrence_id'] in valid_occurrences for row in result['occurrences'])
    assert not any(f'O{i+1:04}' in valid_occurrences for pair in result['overlap_pairs'] for i in pair)
    assert sum(int(money(c['weekly_cost'])*100) for c in result['classes']) == result['validated_cost_cents']
    result.update(basis_status=result['status'], status='FINALIZADO', processing_status='FINALIZADO', operational_allocations=parts, audit_log=logs)
    result['summary'].update(classified_records=len(result['occurrences']), tracked_allocations=len(parts),
        pending_allocations=sum(p['bucket'] != 'validated' for p in parts),
        reconciled_professors=sum(t['status']=='PROCESSADO_CONCILIADO' for t in teachers.values()),
        shared_occurrences=sum(len(r['allocations'])>1 for r in result['occurrences']),
        financial_duplicates=financial_duplicates,
        unexplained_cost_cents=0)
    assert len({p['allocation_id'] for p in parts}) == len(parts)
    for row in result['occurrences']:
        if row['allocations']:
            assert sum((Fraction(p['fraction_numerator'],p['fraction_denominator']) for p in row['allocations']),Fraction()) == 1
            assert sum((Fraction(p['financial_fraction_numerator'],p['financial_fraction_denominator']) for p in row['allocations']),Fraction()) == 1
    return result


def enrich_cost_details(result):
    """Índices verificáveis professor/turma e motivo individual de cada parcela."""
    teachers={t['professor_id']:t for t in result['professors']}
    classes={c['class_id']:c for c in result['classes']}
    groups={}
    pending=[]
    for t in teachers.values():
        t.update(disciplines=set(),source_codes=set(),occurrence_details=[],duration_counts={},class_costs=[])
    for c in classes.values():
        c.update(teacher_costs=[],disciplines=set(),weekly_lesson_equivalents=Fraction(),pending_occurrence_ids=set(),shared_allocations=[])
    for row in result['occurrences']:
        t=teachers[row['professor_id']]
        t['disciplines'].update(str(row['disciplines'] or '').split(' | '))
        t['source_codes'].update(row['source_codes'])
        duration=row['duration_minutes']
        t['duration_counts'][str(duration)]=t['duration_counts'].get(str(duration),0)+1
        t['occurrence_details'].append({k:row[k] for k in ['occurrence_id','page','day','start','duration_minutes','source_codes','disciplines','reference_weekly_cost']})
        for p in row['allocations']:
            target=classes.get(p['class_id'])
            if p['status']!='ALOCADO_REFERENCIA':
                pending.append({**{k:row[k] for k in ['occurrence_id','professor_id','professor','page','day','start','duration_minutes','evidence']},**p})
                if p['candidate_class_id'] in classes:classes[p['candidate_class_id']]['pending_occurrence_ids'].add(row['occurrence_id'])
                continue
            key=(row['professor_id'],p['class_id'])
            g=groups.setdefault(key,{'professor_id':row['professor_id'],'professor':row['professor'],'class_id':target['class_id'],'class_name':target['class_name'],'weekly_cost':Decimal(0),'weekly_minutes':Fraction(),'weekly_lesson_equivalents':Fraction(),'disciplines':set(),'source_codes':set(),'occurrence_ids':set(),'shared_occurrence_ids':set()})
            fraction=Fraction(p.get('fraction_numerator',1),p.get('fraction_denominator',len(row['allocations'])))
            g['weekly_cost']+=money(p['weekly_cost']);g['weekly_minutes']+=Fraction() if p.get('pool_id') else fraction*duration;g['weekly_lesson_equivalents']+=fraction
            g['disciplines'].update(p['disciplines']);g['source_codes'].add(p['source_code']);g['occurrence_ids'].add(row['occurrence_id'])
            target['weekly_lesson_equivalents']+=fraction;target['disciplines'].update(p['disciplines'])
            if p['shared']:
                g['shared_occurrence_ids'].add(row['occurrence_id'])
                target['shared_allocations'].append({'occurrence_id':row['occurrence_id'],'professor_id':row['professor_id'],**p})
    for g in groups.values():
        converted={k:float(v) if isinstance(v,(Decimal,Fraction)) else sorted(v) if isinstance(v,set) else v for k,v in g.items()}
        teachers[g['professor_id']]['class_costs'].append(converted)
        classes[g['class_id']]['teacher_costs'].append(converted)
    for t in teachers.values():
        t['disciplines']=sorted(t['disciplines']);t['source_codes']=sorted(t['source_codes'])
        t['weekly_lesson_equivalents']=sum(r['professor_id']==t['professor_id'] and not r.get('financial_absorbed_into') for r in result['occurrences'])
        t['clock_hours']=t['weekly_minutes']/60
        t['weekly_status']='CONCILIADO' if t['pending_weekly_cost']==0 and t['unknown_cost_records']==0 else 'REQUER REVISÃO'
        if sum((money(g['weekly_cost']) for g in t['class_costs']),Decimal(0))!=money(t['allocated_weekly_cost']):raise ArithmeticError('Professor não fecha por turma')
    for c in classes.values():
        c['disciplines']=sorted(c['disciplines']);c['pending_occurrence_ids']=sorted(c['pending_occurrence_ids'])
        c['weekly_lesson_equivalents']=float(c['weekly_lesson_equivalents'])
        c['other_direct_costs']=None;c['general_expenses_allocated']=0
        if sum((money(g['weekly_cost']) for g in c['teacher_costs']),Decimal(0))!=money(c['weekly_cost']):raise ArithmeticError('Turma não fecha por professor')
    result['pending_allocations']=pending
    return result


def direct_break_even(monthly_direct_cost, net_ticket, *, costs_complete, revenue_complete):
    if not costs_complete or not revenue_complete or monthly_direct_cost is None or net_ticket is None:
        return None
    cost, ticket = Decimal(str(monthly_direct_cost)), Decimal(str(net_ticket))
    if not cost.is_finite() or not ticket.is_finite() or cost < 0 or ticket <= 0:
        return None
    return math.ceil(cost/ticket)


def load_documentary_costs(classes):
    path = ROOT/'output/auditoria-carga-horaria/extracao.json'
    if not path.exists():
        from teaching_cost_snapshot import packaged_ledger
        return packaged_ledger(classes)
    preview = json.loads(path.read_text(encoding='utf-8'))
    result = build_cost_ledger(preview, classes)
    result['extraction_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result
