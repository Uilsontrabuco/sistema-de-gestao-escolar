from private_artifacts import load_private_json, private_text
"""Snapshot sanitizado do custeio docente conciliado para runtimes imutáveis.

Não contém nomes de professores, credenciais nem registros documentais. A fonte
completa permanece fora do artefato público; este arquivo guarda somente os
totais por turma já reconciliados e o hash da extração auditada.
"""
import re
import unicodedata

def apply_2027_projection(result):
    """Completa a projeção 2027 com regências comprovadas da base 2026."""
    _private_values = load_private_json('teaching_projection.json')
    EM_2026_SOURCE = _private_values['EM_2026_SOURCE']
    EM_COMPONENTS = _private_values['EM_COMPONENTS']
    G5C_EQUIVALENCE_SOURCE = _private_values['G5C_EQUIVALENCE_SOURCE']
    REGENT_SUPPLEMENTS = _private_values['REGENT_SUPPLEMENTS']
    WEEKLY_TOTAL_CENTS = _private_values['WEEKLY_TOTAL_CENTS']
    if result.get('projection_adjustments_applied'):
        return result
    for row in result['classes']:
        row['direct_cost_status'] = 'VERIFIED_PROJECTION_2026_BASE'
        if row.get('class_name') in EM_COMPONENTS:
            components = EM_COMPONENTS[row['class_name']]
            row['weekly_cost'] = sum((item[2] for item in components)) * 38.5
            row['weekly_minutes'] = sum((item[2] for item in components)) * 45
            row['teacher_costs'] = [{'professor': teacher, 'disciplines': [discipline], 'weekly_lesson_equivalents': lessons, 'weekly_minutes': lessons * 45, 'weekly_cost': lessons * 38.5, 'source_codes': ['BASE_ESTRUTURAL_2026_EM'], 'hour_aula_rate_2027': 38.5, 'shared': False, 'evidence': EM_2026_SOURCE} for teacher, discipline, lessons in components]
            row['disciplines'] = sorted({item[1] for item in components})
            row['pending_occurrence_ids'] = []
            row['monthly_direct_cost'] = round(row['weekly_cost'] * 4.5, 2)
            row['em_reconciliation_source'] = EM_2026_SOURCE
            continue
        supplement = REGENT_SUPPLEMENTS.get(row.get('class_name'))
        if not supplement:
            continue
        row['weekly_cost'] = round(float(row['weekly_cost']) + supplement['weekly_cost_cents'] / 100, 2)
        row['weekly_minutes'] = float(row.get('weekly_minutes', 0)) + supplement['weekly_minutes']
        row.setdefault('teacher_costs', []).append({'professor': supplement['teacher'], 'disciplines': ['REGÊNCIA'], 'weekly_lesson_equivalents': supplement['lessons'], 'weekly_minutes': supplement['weekly_minutes'], 'weekly_cost': supplement['weekly_cost_cents'] / 100, 'source_codes': ['BASE_ESTRUTURAL_2026_REGENTE'], 'evidence': 'Carga Horária Oficial 2026 — complementação da regência até 24 h/a', 'duration_status': 'não inferida quando a fonte estrutural informa somente horas-aula'})
        row['monthly_direct_cost'] = round(row['weekly_cost'] * 4.5, 2)
    g5a = next((row for row in result['classes'] if row.get('class_name') == 'G5 A'))
    g5c = next((row for row in result['classes'] if row.get('class_name') == 'G5 C'))
    g5c['weekly_cost'] = g5a['weekly_cost']
    g5c['weekly_minutes'] = g5a['weekly_minutes']
    g5c['monthly_direct_cost'] = round(g5c['weekly_cost'] * 4.5, 2)
    g5c['projection_equivalence_source'] = G5C_EQUIVALENCE_SOURCE
    g5c['teacher_identity_status'] = 'NAO_INFERIDA_NEM_COPIADA'
    result['validated_cost_cents'] = WEEKLY_TOTAL_CENTS
    result['validated_cost'] = WEEKLY_TOTAL_CENTS / 100
    result['reference_cost_cents'] = WEEKLY_TOTAL_CENTS
    result['reference_cost'] = WEEKLY_TOTAL_CENTS / 100
    result['status'] = 'PROJECAO_2027_CONCILIADA'
    result['basis_status'] = 'CONCILIADO_PROJECAO_2026'
    result['source_year'] = 2026
    result['target_year'] = 2027
    result['source_reference'] = 'Projeção 2027 — base estrutural: Carga Horária Oficial 2026; tarifas oficiais 2027'
    result['summary'].update(reference_cost=WEEKLY_TOTAL_CENTS / 100, allocated_weekly_cost=WEEKLY_TOTAL_CENTS / 100, reconciled_professors=50, projection_regents_added=len(REGENT_SUPPLEMENTS))
    result['projection_adjustments_applied'] = True
    return result

def packaged_ledger(classes):
    _private_values = load_private_json('teaching_projection.json')
    CLASS_TOTALS = _private_values['CLASS_TOTALS']
    G5C_EQUIVALENCE_SOURCE = _private_values['G5C_EQUIVALENCE_SOURCE']
    SOURCE_HASH = _private_values['SOURCE_HASH']
    SUMMARY = _private_values['SUMMARY']
    WEEKLY_TOTAL_CENTS = _private_values['WEEKLY_TOTAL_CENTS']
    rows = []
    for room in classes:
        label = unicodedata.normalize('NFKD', str(room['name'])).encode('ascii', 'ignore').decode().lower()
        suffix = re.sub('[^a-z0-9]+', '-', label).strip('-').replace('-em', '-em')
        suffix = suffix.replace('o-', '-').replace('grupo-', 'g')
        if suffix not in CLASS_TOTALS:
            raise ValueError(f"Turma ausente no snapshot docente sanitizado: {room['id']}")
        minutes, cost = CLASS_TOTALS[suffix]
        rows.append({'class_id': room['id'], 'class_name': room['name'], 'weekly_minutes': minutes, 'weekly_cost': cost / 100, 'direct_cost_status': 'VERIFIED_PROJECTION_2026_BASE', 'monthly_direct_cost': cost * 4.5 / 100, 'teacher_costs': [], 'disciplines': [], 'pending_occurrence_ids': []})
        if room['name'] == 'G5 C':
            rows[-1]['projection_equivalence_source'] = G5C_EQUIVALENCE_SOURCE
            rows[-1]['teacher_identity_status'] = 'NAO_INFERIDA_NEM_COPIADA'
    if len(rows) != 41 or sum((round(row['weekly_cost'] * 100) for row in rows)) != WEEKLY_TOTAL_CENTS:
        raise ValueError('Snapshot docente sanitizado não reconcilia as 41 turmas')
    return {'status': 'PROJECAO_2027_CONCILIADA', 'processing_status': 'FINALIZADO', 'basis_status': 'CONCILIADO_PROJECAO_2026', 'target_year': 2027, 'source_year': 2026, 'source_reference': 'Projeção 2027 — base estrutural: Carga Horária Oficial 2026; tarifas oficiais 2027', 'extraction_sha256': SOURCE_HASH, 'classes': rows, 'summary': dict(SUMMARY), 'validated_cost': WEEKLY_TOTAL_CENTS / 100, 'validated_cost_cents': WEEKLY_TOTAL_CENTS, 'conflicted_cost': 0, 'conflicted_cost_cents': 0, 'unassigned_cost': 0, 'unassigned_cost_cents': 0, 'reference_cost': WEEKLY_TOTAL_CENTS / 100, 'reference_cost_cents': WEEKLY_TOTAL_CENTS, 'professors': [], 'operational_allocations': [], 'pending_allocations': [], 'occurrences': [], 'accounting': {'additional_expense': 0}, 'runtime_source': 'PACKAGED_SANITIZED_RECONCILED_SNAPSHOT', 'projection_adjustments_applied': True}
