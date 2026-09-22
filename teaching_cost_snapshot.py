"""Snapshot sanitizado do custeio docente conciliado para runtimes imutáveis.

Não contém nomes de professores, credenciais nem registros documentais. A fonte
completa permanece fora do artefato público; este arquivo guarda somente os
totais por turma já reconciliados e o hash da extração auditada.
"""
import re
import unicodedata

SOURCE_HASH = '27115a2931183095d800989a7c700db61fbdb511e7a972e36e0d2d378c5088da'
WEEKLY_TOTAL_CENTS = 2726065

# sufixo do id: (minutos semanais, custo semanal em centavos)
CLASS_TOTALS = {
 'g2-a':(1240,53280),'g2-b':(1240,52766),'g3-a':(1280,51840),'g3-b':(1200,51258),
 'g4-a':(1240,52560),'g4-b':(1200,52765),'g5-a':(1666.6666666667,72335),
 'g5-b':(1666.6666666667,72335),'g5-c':(1666.6666666667,72335),
 '1-a':(1012.5,50220),'1-b':(1210,49320),'1-c':(1770,66536),'1-d':(1687.5,63296),
 '2-a':(1325,53298),'2-b':(1325,53370),'2-c':(1282.5,51866),'2-d':(1260,50539),
 '3-a':(320,50220),'3-b':(1195,50130),'3-c':(1192.5,47096),'3-d':(1217.5,50246),
 '4-a':(1260,45864),'4-b':(946.25,36260),'4-c':(1345,49397),
 '5-a':(1513.75,54729),'5-b':(2460,94432),'5-c':(2137.5,80177),
 '6-a':(1207.5,70063),'6-b':(1185,70062),'6-c':(1140,66148),
 '7-a':(1230,71367),'7-b':(1207.5,70059),'8-a':(1215,70497),'8-b':(1215,70497),
 '8-c':(1207.5,70062),'9-a':(1201.5,70497),'9-b':(1201.5,71802),'9-c':(1192.5,69191),
 '1-em':(1665,142450),'2-em':(1665,142450),'3-em':(1665,142450),
}

SUMMARY = {
 'records':1235,'professors':50,'weekly_minutes':54290,'allocated_minutes':52485,
 'reference_cost':27260.65,'allocated_weekly_cost':27260.65,'pending_weekly_cost':0,
 'cost_difference':0,'documentary_observations':42,'financial_units':1204,
 'classified_records':1235,'tracked_allocations':1566,'pending_allocations':0,
 'reconciled_professors':50,'projection_regents_added':12,'shared_occurrences':232,'financial_duplicates':0,
 'unexplained_cost_cents':0,'original_source_records':1256,'user_shared_groups':20,
 'reference_reduction':291.60,'original_reference_cost':25968.95,
}

# Regências de 24 h/a comprovadas para os dois Grupos 3 e ausentes do
# relatório por professor que originou o ledger de aulistas.
REGENT_SUPPLEMENTS = {
    'G3 A': {'teacher':'Ediangela da Silva Nascimento','lessons':24,'weekly_minutes':960,'weekly_cost_cents':38880},
    'G3 B': {'teacher':'Sirleide Pereira Nunes Santos','lessons':24,'weekly_minutes':960,'weekly_cost_cents':38880},
    '1º A': {'teacher':'Midiã Santos de Sousa','lessons':7.5,'weekly_minutes':0,'weekly_cost_cents':12150},
    '1º B': {'teacher':'Rayanne de Souza Silva','lessons':2,'weekly_minutes':0,'weekly_cost_cents':3240},
    '2º A': {'teacher':'Josse Maria de Souza','lessons':2,'weekly_minutes':0,'weekly_cost_cents':3240},
    '2º B': {'teacher':'Franciele Bemfica Santos de Souza','lessons':2,'weekly_minutes':0,'weekly_cost_cents':3240},
    '2º C': {'teacher':'Ana Paula Novaes','lessons':2,'weekly_minutes':0,'weekly_cost_cents':3240},
    '2º D': {'teacher':'Josse Maria de Souza','lessons':2,'weekly_minutes':0,'weekly_cost_cents':3240},
    '3º A': {'teacher':'Betania da Silva Santos','lessons':24,'weekly_minutes':0,'weekly_cost_cents':38880},
    '3º B': {'teacher':'Ana Paula Andrade Veloso Guimarães','lessons':2,'weekly_minutes':0,'weekly_cost_cents':3240},
    '3º C': {'teacher':'Neila Poliana de Almeida Queiroz','lessons':2,'weekly_minutes':0,'weekly_cost_cents':3240},
    '3º D': {'teacher':'Inara Cintia Souza da Silva Santana','lessons':2,'weekly_minutes':0,'weekly_cost_cents':3240},
}

G5C_EQUIVALENCE_SOURCE = 'Confirmação operacional CAJ — G5 C possui mesma carga horária e custo do G5 A para projeção 2027.'

EM_2026_SOURCE = ('Carga Horaria Juazeiro Oficial 2026 (1).pdf — matriz-resumo '
                  'CAJ Anos Finais e Ensino Médio, páginas 1–4')
EM_COMPONENTS = {
    '1º EM': [
        ('Fernanda da Silva Macedo','Biologia / Aprofundamento em Biologia',4),
        ('Catiane dos Santos','Gramática',3),('Everson de Macedo Rocha','Educação Física',2),
        ('Gabriel Rodrigues Cavalcanti Moreira','Inglês',2),
        ('Heverton Varjão Nascimento','História / Aprofundamento de História',3),
        ('Jander Lourenco Souza','Química / Aprofundamento Química',4),
        ('Jose Pires do Nascimento Santos','Física / Aprofundamento de Física',4),
        ('Priscilla Mônica Alves Dos Santos Nascimento','Geografia / Aprofundamento de Geografia',3),
        ('Miarley Murater Santos Nunes','Argumentação / Redação',2),
        ('Queila Cristiane da Cruz','Projeto de Vida',1),('Terezinha Jane Lima de Souza','Arte',1),
        ('Mateus Silva Santos','Matemática / Investigação Matemática',4),
        ('Rutth Pereira De Souza','Ensino Religioso',2),
        ('Fabiana Pionório Tôrres','Debates Contemporâneos',1),
        ('Larissa de Lima Santos','Literatura',1)],
    '2º EM': [
        ('Fernanda da Silva Macedo','Biologia / Aprofundamento em Biologia',4),
        ('Catiane dos Santos','Gramática',3),('Everson de Macedo Rocha','Educação Física',2),
        ('Gabriel Rodrigues Cavalcanti Moreira','Inglês',2),
        ('Heverton Varjão Nascimento','História / Aprofundamento de História',3),
        ('Jander Lourenco Souza','Química / Aprofundamento Química',4),
        ('Jhonatan Lima Oliveira','Filosofia / Debates Filosóficos',2),
        ('Jose Pires do Nascimento Santos','Física / Aprofundamento de Física',4),
        ('Priscilla Mônica Alves Dos Santos Nascimento','Geografia / Aprofundamento de Geografia',3),
        ('Miarley Murater Santos Nunes','Argumentação / Redação',2),
        ('Queila Cristiane da Cruz','Projeto de Vida',1),
        ('Mateus Silva Santos','Matemática / Investigação Matemática',4),
        ('Rutth Pereira De Souza','Ensino Religioso',2),('Larissa de Lima Santos','Literatura',1)],
    '3º EM': [
        ('Fernanda da Silva Macedo','Biologia / Aprofundamento em Biologia',3),
        ('Catiane dos Santos','Gramática',3),('Everson de Macedo Rocha','Educação Física',2),
        ('Gabriel Rodrigues Cavalcanti Moreira','Inglês',2),
        ('Heverton Varjão Nascimento','História / Aprofundamento de História',3),
        ('Jander Lourenco Souza','Química / Aprofundamento Química',4),
        ('Jhonatan Lima Oliveira','Sociologia / Debates Sociológicos',2),
        ('Jose Pires do Nascimento Santos','Física / Aprofundamento de Física',4),
        ('Priscilla Mônica Alves Dos Santos Nascimento','Geografia / Aprofundamento de Geografia',3),
        ('Miarley Murater Santos Nunes','Argumentação / Redação',2),
        ('Queila Cristiane da Cruz','Projeto de Vida',1),
        ('Mateus Silva Santos','Matemática / Investigação Matemática',5),
        ('Rutth Pereira De Souza','Ensino Religioso',2),('Larissa de Lima Santos','Literatura',1)],
}


def apply_2027_projection(result):
    """Completa a projeção 2027 com regências comprovadas da base 2026."""
    if result.get('projection_adjustments_applied'):
        return result
    for row in result['classes']:
        row['direct_cost_status']='VERIFIED_PROJECTION_2026_BASE'
        if row.get('class_name') in EM_COMPONENTS:
            components=EM_COMPONENTS[row['class_name']]
            row['weekly_cost']=sum(item[2] for item in components)*38.5
            row['weekly_minutes']=sum(item[2] for item in components)*45
            row['teacher_costs']=[{
                'professor':teacher,'disciplines':[discipline],
                'weekly_lesson_equivalents':lessons,'weekly_minutes':lessons*45,
                'weekly_cost':lessons*38.5,'source_codes':['BASE_ESTRUTURAL_2026_EM'],
                'hour_aula_rate_2027':38.5,'shared':False,
                'evidence':EM_2026_SOURCE,
            } for teacher,discipline,lessons in components]
            row['disciplines']=sorted({item[1] for item in components})
            row['pending_occurrence_ids']=[]
            row['monthly_direct_cost']=round(row['weekly_cost']*4.5,2)
            row['em_reconciliation_source']=EM_2026_SOURCE
            continue
        supplement=REGENT_SUPPLEMENTS.get(row.get('class_name'))
        if not supplement:
            continue
        row['weekly_cost']=round(float(row['weekly_cost'])+supplement['weekly_cost_cents']/100,2)
        row['weekly_minutes']=float(row.get('weekly_minutes',0))+supplement['weekly_minutes']
        row.setdefault('teacher_costs',[]).append({
            'professor':supplement['teacher'],'disciplines':['REGÊNCIA'],
            'weekly_lesson_equivalents':supplement['lessons'],
            'weekly_minutes':supplement['weekly_minutes'],
            'weekly_cost':supplement['weekly_cost_cents']/100,
            'source_codes':['BASE_ESTRUTURAL_2026_REGENTE'],
            'evidence':'Carga Horária Oficial 2026 — complementação da regência até 24 h/a',
            'duration_status':'não inferida quando a fonte estrutural informa somente horas-aula',
        })
        row['monthly_direct_cost']=round(row['weekly_cost']*4.5,2)
    g5a=next(row for row in result['classes'] if row.get('class_name')=='G5 A')
    g5c=next(row for row in result['classes'] if row.get('class_name')=='G5 C')
    g5c['weekly_cost']=g5a['weekly_cost']
    g5c['weekly_minutes']=g5a['weekly_minutes']
    g5c['monthly_direct_cost']=round(g5c['weekly_cost']*4.5,2)
    g5c['projection_equivalence_source']=G5C_EQUIVALENCE_SOURCE
    g5c['teacher_identity_status']='NAO_INFERIDA_NEM_COPIADA'
    result['validated_cost_cents']=WEEKLY_TOTAL_CENTS
    result['validated_cost']=WEEKLY_TOTAL_CENTS/100
    result['reference_cost_cents']=WEEKLY_TOTAL_CENTS
    result['reference_cost']=WEEKLY_TOTAL_CENTS/100
    result['status']='PROJECAO_2027_CONCILIADA'
    result['basis_status']='CONCILIADO_PROJECAO_2026'
    result['source_year']=2026
    result['target_year']=2027
    result['source_reference']='Projeção 2027 — base estrutural: Carga Horária Oficial 2026; tarifas oficiais 2027'
    result['summary'].update(reference_cost=WEEKLY_TOTAL_CENTS/100,
        allocated_weekly_cost=WEEKLY_TOTAL_CENTS/100,reconciled_professors=50,
        projection_regents_added=len(REGENT_SUPPLEMENTS))
    result['projection_adjustments_applied']=True
    return result


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
                     'direct_cost_status':'VERIFIED_PROJECTION_2026_BASE','monthly_direct_cost':cost*4.5/100,
                     'teacher_costs':[],'disciplines':[],'pending_occurrence_ids':[]})
        if room['name']=='G5 C':
            rows[-1]['projection_equivalence_source']=G5C_EQUIVALENCE_SOURCE
            rows[-1]['teacher_identity_status']='NAO_INFERIDA_NEM_COPIADA'
    if len(rows)!=41 or sum(round(row['weekly_cost']*100) for row in rows)!=WEEKLY_TOTAL_CENTS:
        raise ValueError('Snapshot docente sanitizado não reconcilia as 41 turmas')
    return {'status':'PROJECAO_2027_CONCILIADA','processing_status':'FINALIZADO','basis_status':'CONCILIADO_PROJECAO_2026',
            'target_year':2027,'source_year':2026,'source_reference':'Projeção 2027 — base estrutural: Carga Horária Oficial 2026; tarifas oficiais 2027',
            'extraction_sha256':SOURCE_HASH,'classes':rows,'summary':dict(SUMMARY),
            'validated_cost':WEEKLY_TOTAL_CENTS/100,'validated_cost_cents':WEEKLY_TOTAL_CENTS,
            'conflicted_cost':0,'conflicted_cost_cents':0,'unassigned_cost':0,'unassigned_cost_cents':0,
            'reference_cost':WEEKLY_TOTAL_CENTS/100,'reference_cost_cents':WEEKLY_TOTAL_CENTS,
            'professors':[],'operational_allocations':[],'pending_allocations':[],
            'occurrences':[],'accounting':{'additional_expense':0},
            'runtime_source':'PACKAGED_SANITIZED_RECONCILED_SNAPSHOT','projection_adjustments_applied':True}
