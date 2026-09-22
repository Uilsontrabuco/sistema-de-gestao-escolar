"""Consulta financeira sem lançamentos; não mensaliza uma tarifa semanal sem regra."""
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from personnel_projection import official_projection
from budget_2027_snapshot import structural_budget_allocation, OFFICIAL_TOTAL_MONTHLY_CENTS


def cents(value):
    value=Decimal(str(value))
    if not value.is_finite() or value<0:
        raise ValueError('Valor financeiro inválido')
    return int((value*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))


def break_even_students(cost_cents, net_ticket_cents, variable_per_student_cents=0):
    if cost_cents is None or net_ticket_cents is None:
        return None
    if min(cost_cents,net_ticket_cents,variable_per_student_cents)<0:
        raise ValueError('Base de PE inválida')
    contribution=Decimal(str(net_ticket_cents))-Decimal(str(variable_per_student_cents))
    if contribution<=0:return None
    return int((Decimal(cost_cents)/contribution).to_integral_value(rounding=ROUND_CEILING))


def structural_ticket_cents(tuition, discount_percent, delinquency_percent):
    """Ticket do PE sem depender de matrículas ou classificações correntes."""
    if tuition is None or discount_percent is None or delinquency_percent is None:
        return None
    if not 0 <= Decimal(str(discount_percent)) <= 100 or not 0 <= Decimal(str(delinquency_percent)) <= 100:
        raise ValueError('Premissa estrutural inválida')
    gross=Decimal(str(tuition))
    if not gross.is_finite() or gross < 0:
        raise ValueError('Mensalidade estrutural inválida')
    return cents(gross*(1-Decimal(str(discount_percent))/100)*(1-Decimal(str(delinquency_percent))/100))


def monthly_teaching_base_cents(weekly_cost_cents, weeks=Decimal('4.5')):
    """Mensalização oficial do PE 2027, sem DSR, encargos ou outras verbas."""
    if not isinstance(weekly_cost_cents,int) or weekly_cost_cents < 0:
        raise ValueError('Custo docente semanal inválido')
    factor=Decimal(str(weeks))
    if not factor.is_finite() or factor <= 0:
        raise ValueError('Fator de mensalização inválido')
    return int((Decimal(weekly_cost_cents)*factor).quantize(Decimal('1'),rounding=ROUND_HALF_UP))


def allocated_costs_by_class(plan, class_ids):
    """Custos conciliados atribuídos diretamente ou por rateio ativo, em centavos/mês."""
    class_ids={str(value) for value in class_ids}
    result={value:{'direct':0,'shared':0,'sources':[]} for value in class_ids}
    rules={str(rule.get('id')):rule for rule in plan.get('rateioRules',[]) if rule.get('status')=='active'}
    for line in plan.get('costLines',[]):
        if line.get('reconciliation')!='mapped' or line.get('classification') not in ('direct_class','direct_segment','shared'):
            continue
        amount=cents(line.get('amount',0))
        monthly=amount if line.get('period')=='monthly' else int((Decimal(amount)/12).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        target=str(line.get('targetClassId') or line.get('operationalClassId') or '')
        if target in result and line.get('classification')=='direct_class':
            result[target]['direct']+=monthly;result[target]['sources'].append(str(line.get('id')))
            continue
        rule=rules.get(str(line.get('rateioRuleId')))
        if not rule:continue
        weighted=[]
        for allocation in rule.get('allocations',[]):
            target=str(allocation.get('classId') or allocation.get('operationalClassId') or allocation.get('targetClassId') or '')
            if target in result:weighted.append((target,Decimal(str(allocation.get('weight',0)))))
        if not weighted or sum(weight for _,weight in weighted)!=Decimal('100'):continue
        raw=[Decimal(monthly)*weight/100 for _,weight in weighted]
        parts=[int(value) for value in raw]
        remainder=monthly-sum(parts)
        order=sorted(range(len(raw)),key=lambda index:(raw[index]-parts[index],-index),reverse=True)
        for index in order[:remainder]:parts[index]+=1
        bucket='shared' if line.get('classification')=='shared' else 'direct'
        for (target,_),value in zip(weighted,parts):
            result[target][bucket]+=value;result[target]['sources'].append(str(line.get('id')))
    return result


def allocate_direct_personnel(records, class_ids):
    """Rateia estagiárias/auxiliares por pessoa sem somar descontos pessoais."""
    class_ids={str(value) for value in class_ids}
    result={value:{'intern':0,'assistant':0,'details':[]} for value in class_ids}
    pending=[]
    from personnel_projection import normalized_person_name
    seen=set()
    for record in records:
        person=str(record.get('person') or '').strip()
        normalized=normalized_person_name(person)
        if not person or normalized in seen:
            raise ValueError('Pessoa direta ausente ou duplicada')
        seen.add(normalized)
        targets=sorted({str(value) for value in record.get('classIds',[]) if str(value) in class_ids})
        shifts=sorted({str(value).strip().casefold() for value in record.get('shifts',[]) if str(value).strip()})
        if not targets or len(shifts) not in (1,2):
            pending.append(dict(person=person,reason='turno ou turmas atendidas sem comprovação suficiente'))
            continue
        kind='intern' if len(shifts)==1 else 'assistant'
        amount=75000 if kind=='intern' else 176400
        base,remainder=divmod(amount,len(targets))
        for index,target in enumerate(targets):
            value=base+(1 if index<remainder else 0)
            result[target][kind]+=value
            result[target]['details'].append(dict(type='ESTAGIARIA' if kind=='intern' else 'AUXILIAR_FIXA',
                person=person,name=person,shifts=shifts,originalValue=amount/100,
                monthlyIndividualCost=amount/100,criterion=f'rateio igualitário entre {len(targets)} turma(s) comprovadas',
                servedClasses=targets,assignedValue=value/100,personalDeductionsAdded=False,
                source=record.get('source'),nature=record.get('nature','custo direto'),
                projectionLabel=record.get('projectionLabel'),sourceClasses=record.get('sourceClasses',[]),
                personnelIdentityUse=record.get('personnelIdentityUse')))
    return result,pending


def consolidate_expenses(components, teaching_monthly_cents, embedded_teaching_cents=None):
    """Substituição só com componente docente identificado dentro da folha."""
    if len({r['id'] for r in components})!=len(components):raise ValueError('Componente duplicado')
    if any(not isinstance(r['amount_cents'],int) or r['amount_cents']<0 for r in components):raise ValueError('Componentes devem estar em centavos')
    embedded=[r for r in components if r.get('contains_teaching')]
    if teaching_monthly_cents is None:return None
    if embedded:
        if len(embedded)!=1 or embedded_teaching_cents is None:raise ValueError('Identifique o custo docente já incluído na folha')
        if not 0<=embedded_teaching_cents<=embedded[0]['amount_cents']:raise ValueError('Componente docente incompatível com folha')
    elif embedded_teaching_cents is not None:raise ValueError('Substituição sem folha identificada')
    return sum(r['amount_cents'] for r in components)-(embedded_teaching_cents or 0)+teaching_monthly_cents


def integration_snapshot(state, ledger, year):
    from server import FINANCIAL_CATEGORIES
    if int(year)!=ledger.get('target_year'):raise ValueError('Custeio docente não validado para este exercício')
    if ledger['conflicted_cost_cents'] or ledger['unassigned_cost_cents']:raise ValueError('Custeio docente não conciliado')
    costs={r['class_id']:cents(r['weekly_cost']) for r in ledger['classes']}
    if len(costs)!=len(ledger['classes']) or set(costs)!={r['id'] for r in state['classes']}:raise ValueError('Turmas do custeio divergem do cadastro')
    if sum(costs.values())!=ledger['validated_cost_cents']:raise ValueError('Custos das turmas não reconciliam')
    teaching_basis_accepted=ledger.get('basis_status') in ('CONCILIADO','CONCILIADO_PROJECAO_2026')
    teaching_status_by_class={row['class_id']:row.get('direct_cost_status') for row in ledger['classes']}
    academic=next((r for r in state.get('academicYears',[]) if int(r['year'])==int(year)),{})
    plans=[p for p in state.get('breakEven',{}).get('plans',[]) if int(p['year'])==int(year)]
    if not plans and int(year)==2027:
        plans=[dict(id='official-2027-read-only',year=2027,version=1,
            officialTotals={'commercialDiscountPercent':3,'delinquencyPercent':4.5,'totalExpensesMonthly':841486.96,
                            'netRevenueMonthly':905152.16,'breakEvenStudents':1000},
            delinquency={'officialPercent':4.5,'scenarioPercent':None},costLines=[],rateioRules=[],mappings=[],
            structuralTicket={'discountPercent':3,'origin':'Orçamento oficial 2027 · desconto comercial'})]
    plan=max(plans,key=lambda p:p.get('version',1),default={})
    totals=plan.get('officialBudget',{}).get('totals') or plan.get('officialTotals',{})
    personnel=plan.get('personnelCostAudit',{})
    delinquency=plan.get('delinquency',{}).get('scenarioPercent')
    if delinquency is None:delinquency=plan.get('delinquency',{}).get('officialPercent')
    if delinquency is None:delinquency=state.get('delinquency',{}).get('financialPercent')
    if delinquency is not None and not 0<=delinquency<=100:raise ValueError('Inadimplência inválida')
    structural=plan.get('structuralTicket',{})
    structural_discount=structural.get('discountPercent')
    structural_discount_origin=structural.get('origin')
    if structural_discount is None:
        structural_discount=totals.get('commercialDiscountPercent')
        structural_discount_origin='Orçamento oficial 2027 · desconto comercial' if structural_discount is not None else None
    expense=totals.get('totalExpensesMonthly')
    expense_reconciliation=plan.get('expenseReconciliation',{})
    official_allocation_complete=(expense_reconciliation.get('status')=='complete')
    assigned_costs=allocated_costs_by_class(plan,(room['id'] for room in state['classes']))
    personnel_projection=plan.get('directPersonnelProjection') or official_projection(state['classes'])
    personnel_costs,personnel_pending=allocate_direct_personnel(personnel_projection,(room['id'] for room in state['classes']))
    verified_mappings=[m for m in plan.get('mappings',[]) if m.get('status')=='mapped' and m.get('costEvidence',{}).get('status')=='verified']
    has_custom_allocation=bool(verified_mappings or any(line.get('reconciliation')=='mapped' for line in plan.get('costLines',[])))
    budget_allocation=None
    if not has_custom_allocation and expense is not None and cents(expense)==OFFICIAL_TOTAL_MONTHLY_CENTS:
        budget_allocation=structural_budget_allocation(state['classes'],
            sum(monthly_teaching_base_cents(cost) for cost in costs.values()),
            sum(bucket['intern']+bucket['assistant'] for bucket in personnel_costs.values()),cents(expense))
    rows=[]
    for room in state['classes']:
        history=[r for r in state.get('enrollments',{}).get('history',[]) if str(r.get('classId'))==str(room['id'])]
        students=sum(room.get('opening',{}).get(k,0)+sum(r['quantity'] for r in history if r.get('type')==k) for k in ('new','re'))+room.get('unclassified',0)
        stage=room['stage']
        segment={'Educação Infantil':'early','Fundamental Anos Iniciais':'fundamental1','Fundamental Anos Finais':'fundamental2'}.get(stage,'secondary3' if room['name'].startswith('3º') else 'secondary12')
        tuition=next((r.get('tuition') for r in academic.get('parameters',[]) if r['id']==segment),None)
        classification=academic.get('classifications',{}).get(room['id'],{})
        groups=[(classification.get('fixed',{}).get(k,0),pct) for k,_,pct in FINANCIAL_CATEGORIES]
        groups.extend((r['quantity'],r['percent']) for r in classification.get('variables',[]))
        classified=sum(n for n,_ in groups)
        if any(n<0 or not 0<=pct<=100 for n,pct in groups) or classified>students:raise ValueError('Classificação de alunos inválida')
        known=None if tuition is None else sum(cents(Decimal(str(tuition))*n*(1-Decimal(str(pct))/100)) for n,pct in groups)
        complete=tuition is not None and classified==students
        weekly=costs[room['id']];capacity=room['capacity']
        teaching_verified=teaching_basis_accepted and teaching_status_by_class[room['id']] in ('VERIFIED','VERIFIED_PROJECTION_2026_BASE')
        teaching_monthly=monthly_teaching_base_cents(weekly)
        mappings=[m for m in plan.get('mappings',[]) if str(m.get('operationalClassId'))==str(room['id']) and m.get('status')=='mapped' and m.get('costEvidence',{}).get('status')=='verified']
        mapping=mappings[0] if len(mappings)==1 else None
        source=next((r for r in plan.get('officialBudget',{}).get('classRows',[]) if mapping and r.get('id')==mapping.get('sourceRowId') and r.get('className')==mapping.get('budgetClassName') and r.get('status')=='recognized'),None)
        mapped_total_cost=cents(mapping['costMonthly']) if source and mapping.get('costMonthly') is not None else None
        assigned=assigned_costs[str(room['id'])]
        direct_people=personnel_costs[str(room['id'])]
        budget_row=budget_allocation['rows'][str(room['id'])] if budget_allocation else {'shared':0,'details':[]}
        other_direct=assigned['direct']+direct_people['intern']+direct_people['assistant'];shared=assigned['shared']+budget_row['shared']
        cost_coverage_complete=mapped_total_cost is not None or official_allocation_complete or budget_allocation is not None
        # Um custo total orçamentário comprovado prevalece; na ausência dele, o
        # PE usa somente a base docente mensal agora homologada, sem somar DSR,
        # encargos ou custos não comprovados.
        known_cost_subtotal=teaching_monthly+other_direct+shared
        total_cost=mapped_total_cost if mapped_total_cost is not None else (known_cost_subtotal if cost_coverage_complete else None)
        # O vínculo é custo total orçamentário, não uma nova parcela docente.
        net_effective=cents(Decimal(known)/100*(1-Decimal(str(delinquency))/100)) if complete and delinquency is not None else None
        structural_ticket=structural_ticket_cents(tuition,structural_discount,delinquency)
        pe=break_even_students(total_cost,structural_ticket)
        pe_percent=None if pe is None or not capacity else pe/capacity*100
        physical_margin=None if pe is None else capacity-pe
        structural_pending=[]
        if tuition is None:structural_pending.append('mensalidade oficial 2027 não configurada')
        if structural_discount is None:structural_pending.append('premissa de ticket estrutural pendente')
        if delinquency is None:structural_pending.append('inadimplência do PE não configurada')
        component_pending=[]
        if not teaching_verified:
            component_pending.append('G5 C: EINFA05TC possui aulistas, mas a regente de 24 h/a não está identificada; EINFA05TD pertence à seção D e não pode ser transferido por inferência')
        if not cost_coverage_complete:
            component_pending.append('despesas oficiais elegíveis ainda sem classificação e critério de atribuição às turmas')
        if personnel_pending:
            component_pending.append('estagiárias/auxiliares sem turno e turmas atendidas integralmente comprovados')
        component_contracts={
            'teachingWeekly':dict(value=weekly/100,status='loaded' if teaching_verified else 'pending',source='Carga horária 2026 conciliada com tarifas 2027',reason=None if teaching_verified else component_pending[0]),
            'teachingMonthly':dict(value=teaching_monthly/100,status='loaded' if teaching_verified else 'pending',source='Custo semanal de referência × 4,5',reason=None if teaching_verified else component_pending[0]),
            'otherDirect':dict(value=other_direct/100 if other_direct or cost_coverage_complete else None,status='loaded' if other_direct else ('zero_real' if cost_coverage_complete else 'pending'),source='Linhas de custo atribuídas e conciliadas do plano',reason=None if cost_coverage_complete else component_pending[0]),
            'sharedAllocation':dict(value=shared/100 if shared or cost_coverage_complete else None,status='loaded' if shared else ('zero_real' if cost_coverage_complete else 'pending'),source='Rateios ativos com alocações explícitas de 100%',reason=None if cost_coverage_complete else component_pending[0]),
        }
        rows.append(dict(class_id=room['id'],name=room['name'],students=students,capacity=capacity,
            vacancies=max(0,capacity-students),tuition=tuition,
            occupancy=None if not capacity else students/capacity*100,
            teachingCostWeekly=weekly/100,teachingCostWeeklyCents=weekly,
            teachingSharePercent=weekly/ledger['validated_cost_cents']*100,
            teachingCostMonthly=teaching_monthly/100,teachingCostAnnual=None,
            teachingMonthlyFactor=4.5,
            teachingMonthlyMethod='CUSTO_SEMANAL_CONFIRMADO_X_4_5',
            teachingMonthlyOrigin='Regra oficial confirmada pelo responsável financeiro para o PE 2027',
            dsrStatus='NAO_APLICADO_COMPOSICAO_NAO_COMPROVADA',
            chargesStatus='NAO_APLICADOS_COMPOSICAO_NAO_COMPROVADA',
            activityHourStatus='NAO_APLICADA_COMPOSICAO_NAO_COMPROVADA',
            teachingCostPerStudentWeekly=None if not students else float(Decimal(weekly)/students/100),
            teachingCostPerCapacityWeekly=None if not capacity else float(Decimal(weekly)/capacity/100),
            knownNetRevenueMonthly=None if known is None else known/100,
            netRevenueMonthly=known/100 if complete else None,
            netTicketMonthly=known/students/100 if complete and students else None,
            tuitionRevenueAnnual=known*11/100 if complete and int(year)==2027 else None,
            classifiedStudents=classified,unclassifiedStudents=students-classified,
            otherDirectCostsMonthly=other_direct/100 if other_direct or cost_coverage_complete else None,
            assistantCostMonthly=direct_people['assistant']/100 if direct_people['assistant'] else None,
            internCostMonthly=direct_people['intern']/100 if direct_people['intern'] else None,
            directPersonnelDetails=direct_people['details'],
            structuralAllocationDetails=budget_row['details'],
            indirectExpensesMonthly=shared/100 if shared or cost_coverage_complete else None,totalCostMonthly=None if total_cost is None else total_cost/100,
            knownCostSubtotalMonthly=known_cost_subtotal/100,
            costBasis='TOTAL_ORCAMENTARIO_VINCULADO_SEM_ADICAO_DOCENTE' if mapped_total_cost is not None else 'DOCENTE_X_4_5_MAIS_DIRETOS_E_RATEIOS_ATRIBUIDOS',
            costCompositionStatus='COMPLETA_CUSTOS_ATRIBUIDOS',
            attributedCostLineIds=assigned['sources'],
            componentContracts=component_contracts,
            componentPendingReasons=component_pending,
            netRevenueAfterDelinquency=None if net_effective is None else net_effective/100,
            operatingResultMonthly=(net_effective-total_cost)/100 if net_effective is not None and total_cost is not None else None,
            breakEvenStudents=pe,studentsNeeded=None if pe is None else max(0,pe-students),safetyMarginStudents=None if pe is None else students-pe,
            structuralGrossTicket=None if tuition is None else tuition,
            structuralPotentialRevenueMonthly=None if tuition is None or not capacity else tuition*capacity,
            structuralDiscountPercent=structural_discount,
            structuralDiscountOrigin=structural_discount_origin,
            structuralDelinquencyPercent=delinquency,
            structuralTicketMonthly=None if structural_ticket is None else structural_ticket/100,
            breakEvenPercentCapacity=pe_percent,physicalMarginStudents=physical_margin,
            structuralAlert='PE acima da capacidade física da turma' if physical_margin is not None and physical_margin<0 else None,
            structuralPendingReasons=structural_pending,
            structuralStatus='DEFINITIVO' if pe is not None and not structural_pending and not component_pending else 'PENDENTE',
            status='PE_ESTRUTURAL_CALCULADO' if pe is not None else 'PENDENTE_BASE_MENSAL_E_COMPOSICAO_DE_CUSTOS'))
    complete=all(r['netRevenueMonthly'] is not None for r in rows)
    count=sum(r['students'] for r in rows)
    net_effective=sum(cents(r['netRevenueAfterDelinquency']) for r in rows) if all(r['netRevenueAfterDelinquency'] is not None for r in rows) else None
    general_pe=break_even_students(cents(expense),Decimal(net_effective)/count) if expense is not None and net_effective is not None and count else None
    revenues=state.get('revenuePlanning',{}).get('years',{}).get(str(year),{}).get('records',[])
    imported={kind:sum(cents(r.get('net',0))*r.get('direction',1) for r in revenues if r.get('eventType')==kind)/100 for kind in ('enrollment','tuition')}
    monthly_total=sum(monthly_teaching_base_cents(cost) for cost in costs.values())
    monthly_global_reference=monthly_teaching_base_cents(ledger['validated_cost_cents'])
    attributed_total=sum(cents(row['totalCostMonthly']) for row in rows if row['totalCostMonthly'] is not None)
    official_cents=cents(expense) if expense is not None else None
    pending_official=None if official_cents is None else max(0,official_cents-attributed_total)
    return dict(year=int(year),status='MONTHLY_BASE_INTEGRATED',teachingCostWeekly=ledger['validated_cost_cents']/100,
        teachingCostMonthly=monthly_total/100,teachingCostAnnual=None,monthlyMethod='CUSTO_SEMANAL_CONFIRMADO_X_4_5',
        monthlyFactor=4.5,
        monthlyRounding='HALF_UP_EM_CENTAVOS_POR_TURMA',
        monthlyGlobalReference=monthly_global_reference/100,
        monthlyClassRoundingDifferenceCents=monthly_total-monthly_global_reference,
        monthlyDecision='Regra oficial do PE 2027: custo semanal confirmado × 4,5. DSR, encargos e hora-atividade não aplicados sem comprovação de composição.',
        totalExpensesMonthlyBefore=expense,totalExpensesMonthly=expense,totalExpensesMonthlyDifference=0 if expense is not None else None,
        totalExpensesStatus='OFFICIAL_REFERENCE_UNCHANGED' if expense is not None else 'NO_OFFICIAL_PLAN_IN_STATE',
        nonTeachingPayrollMonthly=None,chargesMonthly=personnel.get('personalChargesAndBenefitsMonthly'),
        otherOperatingExpensesMonthly=None,
        payrollMonthly=personnel.get('payrollMonthly'),personnelTotalMonthly=personnel.get('totalMonthly'),
        nonPersonnelExpensesMonthly=(cents(expense)-cents(personnel['totalMonthly']))/100 if expense is not None and personnel.get('totalMonthly') is not None else None,
        officialBreakEvenStudents=totals.get('breakEvenStudents'),officialNetRevenueMonthly=totals.get('netRevenueMonthly'),
        recurringNetRevenueMonthly=sum(r['netRevenueMonthly'] for r in rows) if complete else None,
        knownNetRevenueMonthly=sum(r['knownNetRevenueMonthly'] or 0 for r in rows),
        enrollmentRevenueMonthly=None,enrollmentRevenueTreatment='SEPARATE_NOT_AMORTIZED',
        importedEnrollmentRevenue=imported['enrollment'],importedTuitionRevenue=imported['tuition'],importedRevenueRecords=len(revenues),
        tuitionInstallments=11 if int(year)==2027 else plan.get('installments'),
        operatingResultMonthly=(net_effective-cents(expense))/100 if net_effective is not None and expense is not None else None,
        breakEvenStudents=general_pe,breakEvenMonthly=expense if general_pe is not None else None,safetyMargin=None if general_pe is None else count-general_pe,
        peBasis='SIMULACAO_CUSTO_ORCAMENTARIO_PRESERVADO' if general_pe is not None else 'DADOS_INSUFICIENTES',
        classBreakEvenCounts=dict(above=sum(r['safetyMarginStudents'] is not None and r['safetyMarginStudents']>0 for r in rows),at=sum(r['safetyMarginStudents']==0 for r in rows),below=sum(r['safetyMarginStudents'] is not None and r['safetyMarginStudents']<0 for r in rows),undetermined=sum(r['breakEvenStudents'] is None for r in rows)),
        classesBelowBreakEven=[r['name'] for r in rows if r['safetyMarginStudents'] is not None and r['safetyMarginStudents']<0],
        maxDeficit=min((r['operatingResultMonthly'] for r in rows if r['operatingResultMonthly'] is not None and r['operatingResultMonthly']<0),default=None),
        maxSurplus=max((r['operatingResultMonthly'] for r in rows if r['operatingResultMonthly'] is not None and r['operatingResultMonthly']>0),default=None),classes=rows,weeklyDifferenceCents=0,
        teachingAlreadyInPayroll='NOT_SEPARATELY_IDENTIFIED',additionalExpenseCents=0,
        contractVersion='pe-2027-v1',integrationStatus='loaded',
        expenseReconciliation=dict(official=None if official_cents is None else official_cents/100,
            attributed=attributed_total/100,institutionalNonAttributable=None,
            pendingClassification=None if pending_official is None else pending_official/100,
            difference=0 if official_cents is not None else None,
            reason='Saldo oficial ainda não possui critério comprovado de atribuição por turma; não foi rateado artificialmente.'),
        directPersonnelSummary=dict(
            interns=sum(len(record.get('shifts',[]))==1 for record in personnel_projection),
            fixedAssistants=sum(len(record.get('shifts',[]))==2 for record in personnel_projection),
            internMonthly=sum(cents(row['internCostMonthly']) for row in rows if row['internCostMonthly'] is not None)/100,
            fixedAssistantMonthly=sum(cents(row['assistantCostMonthly']) for row in rows if row['assistantCostMonthly'] is not None)/100,
            source='Relação Estagiárias OF.xlsx',projectionLabel='Projeção 2027 — estrutura de estagiárias baseada na relação vigente 2026'),
        budgetReconciliation=budget_allocation,
        projectionLabel='Projeção 2027 — base estrutural: Carga Horária Oficial 2026',
        directPersonnelPending=personnel_pending,
        source=dict(weekly='Carga Horária Oficial 2026 aplicada às tarifas 2027',monthly='Regra oficial confirmada pelo responsável financeiro: × 4,5 semanas; sem DSR ou adicionais',officialPlanId=plan.get('id')))
