"""Cenário local aprovado: composição nominal e redistribuição quantitativa.

Não altera a fotografia documental, o banco ou as regras financeiras homologadas.
"""
from copy import deepcopy
from decimal import Decimal
from pe_real import money,ceil_ratio
from personnel_evidence import personnel_evidence

APPROVAL='Premissa administrativa aprovada pelo usuário em 22/09/2026'


def balanced_additions(a, b, capacity_a, capacity_b, count):
    """Minimiza diferença de alunos movendo somente os ingressantes autorizados."""
    feasible=[(x,count-x) for x in range(count+1)
              if a+x<=capacity_a and b+count-x<=capacity_b]
    if not feasible:raise ValueError('Capacidade física insuficiente; nenhuma movimentação aplicada')
    return min(feasible,key=lambda pair:(abs(a+pair[0]-b-pair[1]),pair[0]))


def exact_ticket(row):
    if row.get('planningAssumption'):
        return Decimal(row['planningAssumption']['ticketExactCents'])
    if row.get('acceptedStudentCount') and row.get('netRevenueCents') is not None:
        return Decimal(row['netRevenueCents'])/row['acceptedStudentCount']
    return Decimal(str(row['ticketCents'])) if row.get('ticketCents') is not None else None


def totals(rows):
    comparable=[r for r in rows if r['consideredCostCents'] is not None and r['projectedRevenueCents'] is not None]
    return dict(classes=len(rows),capacity=sum(r['capacity'] for r in rows),
                enrolled=sum(r['enrolled'] for r in rows),new=sum(r['newStudents'] for r in rows),
                re=sum(r['reenrolled'] for r in rows),vacancies=sum(r['vacancies'] for r in rows),
                costCents=sum(r['consideredCostCents'] or 0 for r in rows),
                peKnown=sum(r['pe'] or 0 for r in rows),peMissing=sum(r['pe'] is None for r in rows),
                projectedRevenueCents=sum(r['projectedRevenueCents'] or 0 for r in rows),
                missingRevenue=sum(r['projectedRevenueCents'] is None for r in rows),
                comparableRevenueCents=sum(r['projectedRevenueCents'] for r in comparable),
                comparableResultCents=sum(r['projectedRevenueCents']-r['consideredCostCents'] for r in comparable))


def administrative_view(report,cost_ledger,*,eighth_c_exists=True):
    if report.get('administrativeApproval'):
        if report.get('eighthCExists')!=eighth_c_exists:
            raise ValueError('Decisão de estrutura mudou; reexecutar sobre a fotografia original preservada')
        return deepcopy(report)
    out=deepcopy(report);before=deepcopy(report['rows'])
    by_name={r['name']:r for r in out['rows']}
    a,b,c=(by_name[n] for n in ('8º A','8º B','8º C'))
    if c['enrolled']!=20 or c['newStudents']!=0 or c['reenrolled']!=20:
        raise ValueError('Base mudou: aprovação refere-se a vinte rematrículas do 8º C')
    if not eighth_c_exists and c['consideredCostCents'] is not None:
        raise ValueError('8º C possui custo alocado; exigir reconciliação antes da extinção')
    additions=(0,0) if eighth_c_exists else balanced_additions(a['enrolled'],b['enrolled'],a['capacity'],b['capacity'],20)
    for row,added in zip((a,b),additions):
        row['enrolled']+=added;row['reenrolled']+=added
        row['vacancies']=row['capacity']-row['enrolled']
        row['occupancyPercent']=row['enrolled']/row['capacity']*100
        row['distanceToPE']=row['enrolled']-row['pe'] if row['pe'] is not None else None
        distance=row['distanceToPE']
        row['enrollmentSituation']=('PE pendente' if distance is None else 'abaixo do ponto de equilíbrio' if distance<0 else 'no ponto de equilíbrio' if distance==0 else 'acima do ponto de equilíbrio')
        row['projectedRevenueCents']=money(exact_ticket(row)*row['enrolled'])
        row['projectedResultCents']=row['projectedRevenueCents']-row['consideredCostCents'] if row['consideredCostCents'] is not None else None
        # Quantidade aprovada não comprova identificação nominal ou receita realizada.
        if added:
            row['currentRevenueComplete']=False;row['currentRevenueCents']=None;row['currentResultCents']=None
        row['administrativeEnrollment']=dict(source=APPROVAL,fromClass='8º C',added=added,nominalEvidence=False)
    out['rows']=[r for r in out['rows'] if r['id']!=c['id']]
    out['archivedRows']=[dict(c,active=False,administrativeStatus='EXTINTA; somente memória comparativa')]
    allocations=cost_ledger['allocations']
    # Cada exclusão já integra a ponte; não pode ser aplicada outra vez.
    for entry in allocations:
        net=(entry['payrollCents']+entry['supportCents']+entry['generalCents']
             -entry['pcldRemovedCents']-entry['discountReclassifiedCents'])
        if net!=entry['costCents']:
            raise ValueError('Ponte de custo/PCLD/descontos inconsistente')
    if (sum(e['pcldRemovedCents'] for e in allocations)!=4211780 or
            sum(e['discountReclassifiedCents'] for e in allocations)!=17790108 or
            sum(e['costCents'] for e in allocations)!=62146808):
        raise ValueError('Totais orçamentários ou deduções divergentes')
    reserve=[r for r in allocations if r['classId'] is None]
    if len(reserve)!=1 or reserve[0]['costCents']!=1582705:
        raise ValueError('Reserva documental mudou; não reaplicar decisão automaticamente')
    assigned=[r for r in allocations if r['classId']]
    if len({r['classId'] for r in assigned})!=len(assigned):
        raise ValueError('Duplicidade de destino no razão documental')
    assigned_by_id={r['classId']:r for r in assigned}
    for row in out['rows']:
        if row['consideredCostCents'] is not None:
            if row['consideredCostCents']!=assigned_by_id[row['id']]['costCents']:
                raise ValueError('Custo atual diverge do razão; investigar absorção antes de distribuir reserva')
            if ceil_ratio(row['consideredCostCents'],exact_ticket(row))!=row['pe']:
                raise ValueError('PE atual não reproduz a fórmula homologada')
    out['administrativeApproval']=APPROVAL
    out['personnelConfirmations']=personnel_evidence()
    out['administrativeReconciliation']=dict(before=totals(before),after=totals(out['rows']),
        additionsCents=0,redistributedCostCents=0,duplicateExclusionsCents=0,
        redistributedStudents=20,reserveCents=1582705,
        reserveStatus='LEGADO_ORCAMENTARIO_A_REVISAR; obrigação remanescente não demonstrada',
        reserveAbsorbedInAllocatedLedger=False,reserveObligation2027Proven=False,
        sourceRows=41,activeClasses=40)
    out['enrollmentSummary']=dict(capacity=sum(r['capacity'] for r in out['rows']),
        enrolled=sum(r['enrolled'] for r in out['rows']),new=sum(r['newStudents'] for r in out['rows']),
        re=sum(r['reenrolled'] for r in out['rows']),vacancies=sum(r['vacancies'] for r in out['rows']),
        knownProjectedRevenueCents=sum(r['projectedRevenueCents'] or 0 for r in out['rows']),
        missingRevenueClasses=sum(r['projectedRevenueCents'] is None for r in out['rows']))
    out['summary']['partial']=sum(r['status']=='PARCIALMENTE COMPROVADO' for r in out['rows'])
    out['summary']['audit']=sum(r['status']=='EM AUDITORIA' for r in out['rows'])
    out['structureNotice']='Estrutura administrativa aprovada: 40 turmas ativas; 41 linhas apenas na comparação histórica. 8º C extinto; 20 rematrículas redistribuídas quantitativamente, sem identificação nominal.'
    out['eighthCExists']=eighth_c_exists
    if eighth_c_exists:
        # Correção humana posterior prevalece: não extinguir C nem redistribuir seus alunos.
        out['rows']=before
        out['archivedRows']=[]
        out['enrollmentSummary']=deepcopy(report['enrollmentSummary'])
        out['summary']=deepcopy(report['summary'])
        out['administrativeReconciliation'].update(after=totals(before),redistributedStudents=0,activeClasses=41)
        out['structureNotice']='Correção posterior do usuário: o 8º C existe. Mantida a fotografia de 41 turmas: 8º A 22, 8º B 0, 8º C 20; nenhuma redistribuição aplicada. 7º ano somente A/B.'
        out['administrativeApproval']+='; correção posterior: 8º C mantido'
    return out
