"""Camada local aditiva de custo completo; não grava estado nem importa descontos.

Consome a prévia aprovada, preserva seus valores e distribui o saldo institucional
por capacidade. Conciliação aritmética não substitui comprovação documental.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP

from budget_2027_snapshot import allocate_by_capacity, OFFICIAL_TOTAL_ANNUAL_CENTS
from financial_integration import cents, break_even_students
from scripts.generate_approved_pe_2027_preview import build_preview, G2_SUPPORT_SOURCE_CENTS


def teaching_identity_review():
    """Preserva a grade homologada, sem promover identidade histórica a 2027."""
    from server import blank
    from teaching_cost import load_documentary_costs
    source = load_documentary_costs(blank()['classes'])
    reviews = []
    for room in source['classes']:
        for teacher in room.get('teacher_costs', []):
            name = teacher.get('professor', '')
            if name.startswith(('Lohana ', 'Marcelo ')):
                reviews.append(dict(classId=room['class_id'], className=room['class_name'],
                    historicalPerson=name, projectedTeacher=None,
                    preservedWeeklyCost=teacher['weekly_cost'],
                    status='POSTO_ESTRUTURAL_PRESERVADO_IDENTIDADE_2027_NAO_ATRIBUIDA',
                    reason='Nome histórico excluído da projeção docente por decisão do responsável'))
    return reviews


def full_cost_audit(preview=None):
    data = deepcopy(build_preview() if preview is None else preview)
    rows, summary = data['classes'], data['summary']
    rooms = [dict(id=r['classId'], capacity=r['capacity']) for r in rows]
    if len(rows) != 41 or len({r['classId'] for r in rows}) != 41:
        raise ValueError('Exige 41 turmas únicas')
    if len({r['class'] for r in rows}) != 41 or sum(r['capacity'] for r in rows) != 1103:
        raise ValueError('Cadastro/capacidade homologada divergente')
    balance = cents(summary['institutionalPersonnelMonthly'])
    institutional = allocate_by_capacity(balance, rooms)
    # Cada linha desta razão é uma parcela econômica exclusiva. Controles e
    # contas sintéticas do orçamento são apresentados separadamente, sem somar.
    accounts = []
    for row in rows:
        cid = row['classId']
        support = (G2_SUPPORT_SOURCE_CENTS[row['class']] - cents(row['internsMonthly'])
                   if row['class'] in G2_SUPPORT_SOURCE_CENTS else 0)
        values = [
            ('docentes', 'A', cents(row['teachingCostMonthly'])),
            ('estagiarias', 'A', cents(row['internsMonthly'])),
            ('auxiliar-direta', 'A', cents(row['otherDirectCostsMonthly'])),
            ('residual-g2', 'F', cents(row['officialResidualMonthly'])),
            ('apoio-direto-g2', 'F', support),
            ('auxiliares-segmento', 'B', cents(row['auxiliariesMonthly'])),
            ('coordenacao-segmento', 'B', cents(row['coordinationOrientationMonthly'])),
            ('gerais-liquidos-pcld', 'B', cents(row['otherProvenAllocationsMonthly']) - support),
            ('pessoal-institucional', 'C', institutional[cid]),
        ]
        for component, category, amount in values:
            accounts.append(dict(id=f'{cid}/{component}', classId=cid,
                                 component=component, category=category, monthlyCents=amount))
        direct = sum(value for _, kind, value in values if kind in ('A', 'F')) - values[0][2]
        shared = sum(value for _, kind, value in values if kind in ('B', 'C'))
        total = sum(value for _, _, value in values)
        ticket = cents(row['netTicket'])
        pe = break_even_students(total, ticket)
        revenue = ticket * row['capacity']
        row.update(previousAttributedMonthly=row['totalCostMonthly'],
                   previousTotalCostMonthly=row['totalCostMonthly'],
                   previousBreakEvenStudents=row['breakEvenStudents'],
                   costChangeMonthly=institutional[cid]/100,
                   breakEvenChangeStudents=pe-row['breakEvenStudents'],
                   previousDocumentaryStatus=row['documentaryStatus'],
                   documentaryStatus='PARCIAL',
                   institutionalAllocationMonthly=institutional[cid]/100,
                   directCostsIncludingResidualMonthly=direct/100,
                   allocationsMonthly=shared/100, totalCostMonthly=total/100,
                   breakEvenStudents=pe, breakEvenPercentCapacity=pe/row['capacity']*100,
                   physicalMarginStudents=row['capacity']-pe,
                   capacityRevenueMonthly=revenue/100,
                   capacityResultMonthly=(revenue-total)/100,
                   tuitionRevenue11MonthsCapacity=revenue*11/100,
                   costAnnual=total*12/100,
                   resultAnnualBeforeEnrollment=(revenue*11-total*12)/100,
                   auditStatus='PROVISORIO_CONCILIADO_COM_PENDENCIAS',
                   capacityStatus=('PE_ACIMA_DA_CAPACIDADE' if pe > row['capacity'] else
                                   'SEM_FOLGA' if pe == row['capacity'] else 'COM_FOLGA'))
    distributed = sum(a['monthlyCents'] for a in accounts)
    expected = cents(summary['managerialPETotalMonthly'])
    if distributed != expected:
        raise ValueError('Razão econômico não fecha com o envelope gerencial')
    summary.update(classAttributedMonthly=distributed/100,
                   priorClassAttributedMonthly=summary['classAttributedMonthly'],
                   institutionalAllocatedMonthly=balance/100, unallocatedMonthly=0,
                   institutionalTreatment='INCLUDED_IN_CLASS_COSTS_NOT_ADDITIONAL',
                   managerialAnnual=distributed*12/100,
                   officialAnnual=OFFICIAL_TOTAL_ANNUAL_CENTS/100,
                   officialMonthlyTimes12=cents(summary['officialTotalMonthly'])*12/100,
                   annualRoundingDifferenceCents=OFFICIAL_TOTAL_ANNUAL_CENTS-cents(summary['officialTotalMonthly'])*12,
                   allocationsMonthly=sum(cents(r['allocationsMonthly']) for r in rows)/100,
                   otherDirectMonthly=sum(cents(r['directCostsIncludingResidualMonthly']) for r in rows)/100,
                   capacityRevenueMonthly=sum(cents(r['capacityRevenueMonthly']) for r in rows)/100,
                   capacityResultMonthly=sum(round(r['capacityResultMonthly']*100) for r in rows)/100,
                   sumClassBreakEvenStudents=sum(r['breakEvenStudents'] for r in rows),
                   aboveCapacity=sum(r['breakEvenStudents']>r['capacity'] for r in rows))
    data.update(title='Auditoria local de custo completo e PE estrutural 2027',
                status='CONCILIADO_ARITMETICAMENTE_NAO_FECHADO_DOCUMENTALMENTE',
                expenseLedger=accounts, readyForOfficialDiscountImport=False,
                discountProjectionContractReady=True,
                institutionalCriterion='CAPACIDADE_ESTRUTURAL_APOS_DEDUCAO_DOS_CUSTOS_JA_ATRIBUIDOS',
                revenueCalendar=dict(tuitionMonths=list(range(2,13)), installments=11,
                                     enrollmentMonth=1, enrollmentTreatment='SEPARATE_NOT_AMORTIZED'),
                financialAccountReview=dict(accounts=['4126005','4126007'],
                                           monthly=177901.08, classification='F',
                                           treatment='PRESERVADO_NO_ENVELOPE_ATE_CONCILIACAO_COM_DESCONTOS'),
                personnelDecisions=[
                    dict(person='Jailane', decision='SUBSTITUI_ROMILTON_MESMO_POSTO', additionalCost=None),
                    dict(person='Veroneide', decision='VAGA_NOVA', additionalCost=None),
                    dict(person='Lohana', decision='SOMENTE_AUXILIAR_DE_COORDENACAO', additionalCost=0),
                    dict(person='Marcelo', decision='NAO_DOCENTE', additionalCost=0),
                ], teachingIdentityReview=teaching_identity_review())
    validate_full_audit(data)
    return data


def validate_full_audit(data):
    rows, ledger, summary = data['classes'], data['expenseLedger'], data['summary']
    if len({item['id'] for item in ledger}) != len(ledger):
        raise ValueError('Parcela econômica duplicada')
    known = {r['classId'] for r in rows}
    if any(a['classId'] not in known or type(a['monthlyCents']) is not int or a['monthlyCents'] < 0 for a in ledger):
        raise ValueError('Parcela inválida ou sem vínculo')
    for row in rows:
        total = sum(a['monthlyCents'] for a in ledger if a['classId'] == row['classId'])
        if total != cents(row['totalCostMonthly']):
            raise ValueError('Razão da turma não fecha')
        if total != sum(cents(row[k]) for k in ('teachingCostMonthly','directCostsIncludingResidualMonthly','allocationsMonthly')):
            raise ValueError('Componentes da turma não fecham')
        ticket = cents(row['netTicket'])
        pe = row['breakEvenStudents']
        if ticket <= 0 or not (pe*ticket >= total and (pe == 0 or (pe-1)*ticket < total)):
            raise ValueError('PE não é o menor inteiro que cobre o custo')
    if sum(a['monthlyCents'] for a in ledger) != cents(summary['managerialPETotalMonthly']):
        raise ValueError('Despesa desapareceu ou foi duplicada')
    if cents(summary['managerialPETotalMonthly']) + cents(summary['pcldNeutralizedMonthly']) != cents(summary['officialTotalMonthly']):
        raise ValueError('Orçamento/PCLD não conciliado')


def project_real_discounts(audit, students=None, *, complete=False):
    """Contrato para futura importação, sem I/O ou alteração do PE estrutural.

    Registro: studentId, classId, discountPercent. A base real substitui os 3%
    estruturais na projeção e recebe inadimplência uma vez. Base incompleta
    mantém totais desconhecidos como None; matrícula de janeiro fica separada.
    """
    by_id = {r['classId']: r for r in audit['classes']}
    groups = {key: [] for key in by_id}
    seen = set()
    if complete and students is None:
        raise ValueError('Base completa exige registros explícitos, mesmo se vazios')
    for student in students or []:
        sid, cid = str(student.get('studentId') or '').strip(), student.get('classId')
        pct = Decimal(str(student.get('discountPercent')))
        if not sid or sid in seen or cid not in groups:
            raise ValueError('Aluno duplicado/sem identificação ou turma desconhecida')
        if not pct.is_finite() or not 0 <= pct <= 100:
            raise ValueError('Desconto inválido')
        seen.add(sid)
        gross = cents(by_id[cid]['grossTuition'])
        net = int((Decimal(gross)*(1-pct/100)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        groups[cid].append((gross, net))
    result = []
    for cid, row in by_id.items():
        group = groups[cid]
        gross, net = sum(v[0] for v in group), sum(v[1] for v in group)
        effective = int((Decimal(net)*(1-Decimal(str(row['delinquencyPercent']))/100))
                        .quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        result.append(dict(classId=cid, structuralBreakEvenStudents=row['breakEvenStudents'],
                           structuralTicket=row['netTicket'], knownStudentCount=len(group),
                           enrollmentCount=len(group) if complete else None,
                           occupancyPercent=len(group)/row['capacity']*100 if complete else None,
                           realDiscountImpactMonthly=(gross-net)/100 if complete else None,
                           projectedRevenueMonthly=effective/100 if complete else None,
                           projectedTicket=effective/100/len(group) if complete and group else None,
                           projectedMarginMonthly=(effective-cents(row['totalCostMonthly']))/100 if complete else None,
                           status='SIMULACAO_BASE_COMPLETA' if complete else 'AGUARDANDO_IMPORTACAO_COMPLETA',
                           officialUseReady=audit['readyForOfficialDiscountImport']))
    return result
