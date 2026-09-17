"""Snapshot sanitizado do custeio docente conciliado para runtimes imutáveis.

Não contém nomes de professores, credenciais nem registros documentais. A fonte
completa permanece fora do artefato público; este arquivo guarda somente os
totais por turma já reconciliados e o hash da extração auditada.
"""
import re
import unicodedata

SOURCE_HASH = '27115a2931183095d800989a7c700db61fbdb511e7a972e36e0d2d378c5088da'
WEEKLY_TOTAL_CENTS = 2567735

# sufixo do id: (minutos semanais, custo semanal em centavos)
CLASS_TOTALS = {
 'g2-a':(1240,53280),'g2-b':(1240,52766),'g3-a':(320,12960),'g3-b':(240,12378),
 'g4-a':(1240,52560),'g4-b':(1200,52765),'g5-a':(1666.6666666667,72335),
 'g5-b':(1666.6666666667,72335),'g5-c':(626.6666666667,30215),
 '1-a':(1012.5,38070),'1-b':(1210,46080),'1-c':(1770,66536),'1-d':(1687.5,63296),
 '2-a':(1325,50058),'2-b':(1325,50130),'2-c':(1282.5,48626),'2-d':(1260,47299),
 '3-a':(320,11340),'3-b':(1195,46890),'3-c':(1192.5,43856),'3-d':(1217.5,47006),
 '4-a':(1260,45864),'4-b':(946.25,36260),'4-c':(1345,49397),
 '5-a':(1513.75,54729),'5-b':(2460,94432),'5-c':(2137.5,80177),
 '6-a':(1207.5,70063),'6-b':(1185,70062),'6-c':(1140,66148),
 '7-a':(1230,71367),'7-b':(1207.5,70059),'8-a':(1215,70497),'8-b':(1215,70497),
 '8-c':(1207.5,70062),'9-a':(1201.5,70497),'9-b':(1201.5,71802),'9-c':(1192.5,69191),
 '1-em':(1764,151434),'2-em':(1786.5,155283),'3-em':(1831.5,159133),
}

SUMMARY = {
 'records':1235,'professors':50,'weekly_minutes':54290,'allocated_minutes':52485,
 'reference_cost':25677.35,'allocated_weekly_cost':25677.35,'pending_weekly_cost':0,
 'cost_difference':0,'documentary_observations':42,'financial_units':1204,
 'classified_records':1235,'tracked_allocations':1566,'pending_allocations':0,
 'reconciled_professors':50,'shared_occurrences':232,'financial_duplicates':0,
 'unexplained_cost_cents':0,'original_source_records':1256,'user_shared_groups':20,
 'reference_reduction':291.60,'original_reference_cost':25968.95,
}


def packaged_ledger(classes):
    rows=[]
    for room in classes:
        label=unicodedata.normalize('NFKD',str(room['name'])).encode('ascii','ignore').decode().lower()
        suffix=re.sub(r'[^a-z0-9]+','-',label).strip('-').replace('-em','-em')
        suffix=suffix.replace('o-','-').replace('grupo-','g')
        if suffix not in CLASS_TOTALS:
            raise ValueError(f'Turma ausente no snapshot docente sanitizado: {room["id"]}')
        minutes,cost=CLASS_TOTALS[suffix]
        rows.append({'class_id':room['id'],'class_name':room['name'],
                     'weekly_minutes':minutes,'weekly_cost':cost/100,
                     'direct_cost_status':'VERIFIED','monthly_direct_cost':cost*4.5/100,
                     'teacher_costs':[],'disciplines':[],'pending_occurrence_ids':[]})
    if len(rows)!=41 or sum(round(row['weekly_cost']*100) for row in rows)!=WEEKLY_TOTAL_CENTS:
        raise ValueError('Snapshot docente sanitizado não reconcilia as 41 turmas')
    return {'status':'FINALIZADO','processing_status':'FINALIZADO','basis_status':'CONCILIADO',
            'target_year':2027,'source_year':2026,'source_reference':'extração documental auditada',
            'extraction_sha256':SOURCE_HASH,'classes':rows,'summary':dict(SUMMARY),
            'validated_cost':WEEKLY_TOTAL_CENTS/100,'validated_cost_cents':WEEKLY_TOTAL_CENTS,
            'conflicted_cost':0,'conflicted_cost_cents':0,'unassigned_cost':0,'unassigned_cost_cents':0,
            'reference_cost':WEEKLY_TOTAL_CENTS/100,'reference_cost_cents':WEEKLY_TOTAL_CENTS,
            'professors':[],'operational_allocations':[],'pending_allocations':[],
            'occurrences':[],'accounting':{'additional_expense':0},
            'runtime_source':'PACKAGED_SANITIZED_RECONCILED_SNAPSHOT'}
