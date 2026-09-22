import copy
import unittest
from server import blank
from teaching_cost import load_documentary_costs
from financial_integration import integration_snapshot, consolidate_expenses, break_even_students, structural_ticket_cents, monthly_teaching_base_cents, allocate_direct_personnel
from direct_personnel_snapshot import official_projection, projection_from_rows, PROJECTION_LABEL
from budget_2027_snapshot import structural_budget_allocation, allocate_by_capacity, allocate_by_segment, allocate_per_class


class FinancialIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.ledger=load_documentary_costs(blank()['classes'])
    def test_closed_weekly_projection_41_classes_and_official_monthly_factor(self):
        state=blank();before=copy.deepcopy(state);d=integration_snapshot(state,self.ledger,2027)
        self.assertEqual(state,before)
        self.assertEqual(d['teachingCostWeekly'],27260.65)
        self.assertEqual(sum(r['teachingCostWeeklyCents'] for r in d['classes']),2726065)
        self.assertEqual(len(d['classes']),41)
        self.assertEqual(self.ledger['summary']['reconciled_professors'],50)
        self.assertEqual(self.ledger['summary']['projection_regents_added'],12)
        self.assertEqual(d['teachingCostMonthly'],122673.00);self.assertIsNone(d['teachingCostAnnual'])
        self.assertEqual(d['monthlyFactor'],4.5);self.assertEqual(d['monthlyMethod'],'CUSTO_SEMANAL_CONFIRMADO_X_4_5')
        self.assertIsNone(d['breakEvenStudents']);self.assertEqual(d['classBreakEvenCounts']['undetermined'],0)
        self.assertEqual(sum(row['structuralStatus']=='DEFINITIVO' for row in d['classes']),41)
        self.assertEqual(sum(row['structuralStatus']=='PENDENTE' for row in d['classes']),0)
        self.assertEqual(d['expenseReconciliation']['pendingClassification'],0)
    def test_tuition_discounts_scholarships_and_enrollment_separate(self):
        state=blank();room=state['classes'][0];room['opening']={'new':1,'re':2}
        state['academicYears'][0]['classifications'][room['id']]={'fixed':{'noDiscount':1,'philanthropic100':1,'philanthropic50':1}}
        row=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(row['netRevenueMonthly'],1396.04)
        self.assertEqual(row['tuitionRevenueAnnual'],15356.44)
        self.assertEqual(row['students'],3)
        self.assertEqual(row['netTicketMonthly'],1396.04/3)
        state['enrollments']['history']=[{'classId':room['id'],'type':'new','quantity':1}]
        row=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(row['students'],4);self.assertIsNone(row['netRevenueMonthly'])
    def test_capacity_and_students_recompute_weekly_metrics_without_changing_cost(self):
        state=blank();before=integration_snapshot(state,self.ledger,2027)['classes'][0]
        state['classes'][0]['capacity']*=2;state['classes'][0]['opening']={'new':0,'re':5}
        after=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(after['teachingCostWeekly'],before['teachingCostWeekly'])
        self.assertEqual(after['teachingCostPerCapacityWeekly'],before['teachingCostPerCapacityWeekly']/2)
        self.assertAlmostEqual(after['teachingCostPerStudentWeekly'],after['teachingCostWeekly']/5)
    def test_no_future_year_fallback(self):
        with self.assertRaises(ValueError):integration_snapshot(blank(),self.ledger,2028)
    def test_corrupt_sum_or_duplicate_class_fails(self):
        ledger=copy.deepcopy(self.ledger);ledger['classes'][0]['weekly_cost']+=.02
        with self.assertRaises(ValueError):integration_snapshot(blank(),ledger,2027)
    def test_embedded_payroll_cannot_be_added_twice(self):
        parts=[dict(id='payroll',amount_cents=100000,contains_teaching=True),dict(id='operating',amount_cents=20000)]
        with self.assertRaises(ValueError):consolidate_expenses(parts,50000)
        self.assertEqual(consolidate_expenses(parts,50000,40000),130000)
        with self.assertRaises(ValueError):consolidate_expenses(parts+parts,50000,40000)
    def test_pe_rounding_and_cost_scenarios(self):
        self.assertEqual(break_even_students(182000,10000),19)
        self.assertEqual(break_even_students(182000+10000+20000,10000),22)
        self.assertEqual(break_even_students(182000,10000,1000),21)
        self.assertIsNone(break_even_students(None,10000))
        self.assertIsNone(break_even_students(10000,0))
    def test_official_total_is_reference_and_never_incremented(self):
        state=blank();state['breakEven']['plans']=[dict(id='p',year=2027,version=1,officialTotals=dict(totalExpensesMonthly=841486.96))]
        d=integration_snapshot(state,self.ledger,2027)
        self.assertEqual(d['totalExpensesMonthly'],841486.96)
        self.assertEqual(d['totalExpensesMonthlyDifference'],0)
        self.assertEqual(d['additionalExpenseCents'],0)
    def test_existing_budget_cost_enables_class_pe_without_monthly_teaching(self):
        state=blank();room=state['classes'][0]
        room['opening']={'new':0,'re':10}
        state['academicYears'][0]['classifications'][room['id']]={'fixed':{'noDiscount':10}}
        state['breakEven']['plans']=[dict(year=2027,version=1,delinquency={'officialPercent':0},structuralTicket={'discountPercent':0,'origin':'fixture'},
            mappings=[dict(operationalClassId=room['id'],status='mapped',costEvidence={'status':'verified'},costMonthly=10000,sourceRowId='b',budgetClassName=room['name'])],
            officialBudget={'classRows':[dict(id='b',className=room['name'],status='recognized')]})]
        d=integration_snapshot(state,self.ledger,2027);r=d['classes'][0]
        self.assertEqual(r['totalCostMonthly'],10000)
        self.assertEqual(r['breakEvenStudents'],11)
        self.assertEqual(r['studentsNeeded'],1)
        self.assertAlmostEqual(r['operatingResultMonthly'],-693.10)
        self.assertEqual(r['teachingCostMonthly'],2397.60)
        self.assertLess(r['safetyMarginStudents'],0)

    def test_structural_pe_does_not_depend_on_current_students_or_classifications(self):
        state=blank();room=state['classes'][0]
        state['breakEven']['plans']=[dict(year=2027,version=1,delinquency={'officialPercent':4.5},
            structuralTicket={'discountPercent':3,'origin':'fixture oficial'},
            mappings=[dict(operationalClassId=room['id'],status='mapped',costEvidence={'status':'verified'},costMonthly=5000,sourceRowId='b',budgetClassName=room['name'])],
            officialBudget={'classRows':[dict(id='b',className=room['name'],status='recognized')]})]
        before=integration_snapshot(state,self.ledger,2027)['classes'][0]
        room['opening']={'new':0,'re':0};room['unclassified']=0
        state['academicYears'][0]['classifications'][room['id']]={'fixed':{}}
        after=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(after['breakEvenStudents'],before['breakEvenStudents'])
        self.assertEqual(after['structuralTicketMonthly'],before['structuralTicketMonthly'])

    def test_capacity_changes_only_structural_percentage_and_physical_margin(self):
        state=blank();room=state['classes'][0]
        state['breakEven']['plans']=[dict(year=2027,version=1,delinquency={'officialPercent':0},structuralTicket={'discountPercent':0,'origin':'fixture'},
            mappings=[dict(operationalClassId=room['id'],status='mapped',costEvidence={'status':'verified'},costMonthly=20000,sourceRowId='b',budgetClassName=room['name'])],
            officialBudget={'classRows':[dict(id='b',className=room['name'],status='recognized')]})]
        before=integration_snapshot(state,self.ledger,2027)['classes'][0];room['capacity']*=2
        after=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(after['breakEvenStudents'],before['breakEvenStudents'])
        self.assertEqual(after['breakEvenPercentCapacity'],before['breakEvenPercentCapacity']/2)
        self.assertEqual(after['physicalMarginStudents']-before['physicalMarginStudents'],before['capacity'])

    def test_proven_cost_and_structural_ticket_change_pe(self):
        self.assertEqual(break_even_students(100000,50000),2)
        self.assertEqual(break_even_students(100001,50000),3)
        self.assertEqual(break_even_students(100000,25000),4)

    def test_unclassified_students_do_not_become_zero_discount_and_unassigned_costs_are_zero(self):
        state=blank();room=state['classes'][0];room['opening']={'new':0,'re':1}
        state['breakEven']['plans']=[dict(year=2027,version=1,delinquency={'officialPercent':0},structuralTicket={'discountPercent':0,'origin':'fixture'})]
        row=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertIsNone(row['netRevenueMonthly']);self.assertIsNone(row['totalCostMonthly'])
        self.assertIsNone(row['breakEvenStudents']);self.assertEqual(len(row['componentPendingReasons']),1)
        self.assertIn('despesas oficiais elegíveis',row['componentPendingReasons'][0])
        self.assertEqual(row['otherDirectCostsMonthly'],750);self.assertIsNone(row['indirectExpensesMonthly'])
        self.assertEqual(row['structuralStatus'],'PENDENTE')

    def test_pe_above_capacity_has_explicit_alert(self):
        state=blank();room=state['classes'][0]
        state['breakEven']['plans']=[dict(year=2027,version=1,delinquency={'officialPercent':0},structuralTicket={'discountPercent':0,'origin':'fixture'},
            mappings=[dict(operationalClassId=room['id'],status='mapped',costEvidence={'status':'verified'},costMonthly=999999,sourceRowId='b',budgetClassName=room['name'])],
            officialBudget={'classRows':[dict(id='b',className=room['name'],status='recognized')]})]
        row=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertGreater(row['breakEvenStudents'],row['capacity'])
        self.assertEqual(row['structuralAlert'],'PE acima da capacidade física da turma')

    def test_reconciled_weekly_teaching_cost_reaches_every_pe_row_without_manual_entry(self):
        rows=integration_snapshot(blank(),self.ledger,2027)['classes']
        self.assertEqual(len(rows),41);self.assertTrue(all(row['teachingCostWeekly'] is not None for row in rows))
        self.assertEqual(next(row for row in rows if row['name']=='G2 A')['teachingCostWeekly'],532.80)

    def test_structural_ticket_requires_explicit_discount_premise(self):
        self.assertIsNone(structural_ticket_cents(930.69,None,4.5))
        self.assertEqual(structural_ticket_cents(930.69,3,4.5),86214)

    def test_official_monthly_factor_is_exact_and_adds_no_dsr_or_charges(self):
        self.assertEqual(monthly_teaching_base_cents(53280),239760)
        state=blank();state['breakEven']['plans']=[dict(year=2027,version=1,
            delinquency={'officialPercent':4.5},structuralTicket={'discountPercent':3,'origin':'fixture oficial'})]
        row=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(row['teachingCostMonthly'],2397.60)
        self.assertEqual(row['teachingMonthlyFactor'],4.5)
        self.assertEqual(row['structuralDelinquencyPercent'],4.5)
        self.assertEqual(row['structuralStatus'],'PENDENTE')
        self.assertEqual(row['dsrStatus'],'NAO_APLICADO_COMPOSICAO_NAO_COMPROVADA')
        self.assertEqual(row['chargesStatus'],'NAO_APLICADOS_COMPOSICAO_NAO_COMPROVADA')

    def test_direct_and_shared_assigned_costs_integrate_without_duplication(self):
        state=blank();g2=state['classes'][0];g2b=state['classes'][1]
        state['breakEven']['plans']=[dict(year=2027,version=1,
            delinquency={'officialPercent':4.5},structuralTicket={'discountPercent':3,'origin':'fixture oficial'},
            expenseReconciliation={'status':'complete'},
            costLines=[
                dict(id='direct-g2',label='Auxiliar G2 A',amount=1200,classification='direct_class',targetClassId=g2['id'],reconciliation='mapped'),
                dict(id='shared-ei',label='Rateio EI',amount=1200,classification='shared',rateioRuleId='r-ei',reconciliation='mapped')],
            rateioRules=[dict(id='r-ei',name='Rateio fixture',driver='custom',status='active',allocations=[
                dict(classId=g2['id'],weight=50),dict(classId=g2b['id'],weight=50)])])]
        data=integration_snapshot(state,self.ledger,2027);first=data['classes'][0];second=data['classes'][1]
        self.assertEqual(first['otherDirectCostsMonthly'],850)
        self.assertEqual(first['indirectExpensesMonthly'],50)
        self.assertEqual(first['totalCostMonthly'],first['teachingCostMonthly']+900)
        self.assertEqual(second['otherDirectCostsMonthly'],750)
        self.assertEqual(second['indirectExpensesMonthly'],50)
        self.assertEqual(sum(row['indirectExpensesMonthly'] for row in data['classes']),100)
        self.assertEqual(first['attributedCostLineIds'],['direct-g2','shared-ei'])
        plan=state['breakEven']['plans'][0]
        plan['mappings']=[dict(operationalClassId=g2['id'],status='mapped',costEvidence={'status':'verified'},
            costMonthly=5000,sourceRowId='total-g2',budgetClassName=g2['name'])]
        plan['officialBudget']={'classRows':[dict(id='total-g2',className=g2['name'],status='recognized')]}
        mapped=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(mapped['totalCostMonthly'],5000)
        self.assertEqual(mapped['otherDirectCostsMonthly'],850)
        self.assertEqual(mapped['indirectExpensesMonthly'],50)
        self.assertEqual(mapped['costBasis'],'TOTAL_ORCAMENTARIO_VINCULADO_SEM_ADICAO_DOCENTE')

    def test_official_budget_is_reconciled_without_fake_zero(self):
        data=integration_snapshot(blank(),self.ledger,2027);g2=next(row for row in data['classes'] if row['name']=='G2 A')
        self.assertEqual(g2['teachingCostWeekly'],532.80)
        self.assertEqual(g2['teachingCostMonthly'],2397.60)
        self.assertEqual(g2['otherDirectCostsMonthly'],750)
        self.assertEqual(g2['indirectExpensesMonthly'],10395.49)
        self.assertEqual(g2['totalCostMonthly'],13543.09)
        self.assertEqual(g2['breakEvenStudents'],16)
        self.assertEqual(g2['knownCostSubtotalMonthly'],13543.09)
        self.assertEqual(g2['componentContracts']['otherDirect']['status'],'loaded')
        self.assertEqual(g2['componentContracts']['sharedAllocation']['status'],'loaded')
        self.assertEqual(g2['componentPendingReasons'],[])
        self.assertEqual(g2['componentContracts']['teachingWeekly']['status'],'loaded')

    def test_g3_regents_are_restored_from_2026_structural_base(self):
        data=integration_snapshot(blank(),self.ledger,2027)
        g3a=next(row for row in data['classes'] if row['name']=='G3 A')
        g3b=next(row for row in data['classes'] if row['name']=='G3 B')
        self.assertEqual((g3a['teachingCostWeekly'],g3a['teachingCostMonthly']),(518.40,2332.80))
        self.assertEqual((g3b['teachingCostWeekly'],g3b['teachingCostMonthly']),(512.58,2306.61))

    def test_regency_complements_cover_all_proven_deficits(self):
        data=integration_snapshot(blank(),self.ledger,2027)
        expected={'1º A':(502.20,2259.90),'1º B':(493.20,2219.40),
            '2º A':(532.98,2398.41),'2º B':(533.70,2401.65),'2º C':(518.66,2333.97),'2º D':(505.39,2274.26),
            '3º A':(502.20,2259.90),'3º B':(501.30,2255.85),'3º C':(470.96,2119.32),'3º D':(502.46,2261.07)}
        for name,values in expected.items():
            row=next(item for item in data['classes'] if item['name']==name)
            self.assertEqual((row['teachingCostWeekly'],row['teachingCostMonthly']),values)

    def test_g5c_uses_authorized_g5a_cost_without_copying_teacher_identity(self):
        data=integration_snapshot(blank(),self.ledger,2027)
        g5a=next(row for row in data['classes'] if row['name']=='G5 A')
        g5c=next(row for row in data['classes'] if row['name']=='G5 C')
        self.assertEqual((g5c['teachingCostWeekly'],g5c['teachingCostMonthly']),(g5a['teachingCostWeekly'],g5a['teachingCostMonthly']))
        self.assertEqual((g5c['teachingCostWeekly'],g5c['teachingCostMonthly']),(723.35,3255.08))
        source_row=next(row for row in self.ledger['classes'] if row['class_name']=='G5 C')
        self.assertEqual(source_row['teacher_identity_status'],'NAO_INFERIDA_NEM_COPIADA')
        self.assertIn('mesma carga horária e custo do G5 A',source_row['projection_equivalence_source'])
        self.assertEqual(sum(row['componentContracts']['teachingWeekly']['status']=='loaded' for row in data['classes']),41)

    def test_direct_people_rules_rateio_and_personal_deductions_not_added(self):
        ids=[room['id'] for room in blank()['classes'][:3]]
        rows,pending=allocate_direct_personnel([
            dict(person='Estagiária Fixture',shifts=['manhã'],classIds=ids[:2],personalDeductions=[134.43,176.40]),
            dict(person='Auxiliar Fixture',shifts=['manhã','tarde'],classIds=ids[1:]),
        ],ids)
        self.assertEqual(pending,[])
        self.assertEqual(sum(row['intern'] for row in rows.values()),75000)
        self.assertEqual(sum(row['assistant'] for row in rows.values()),176400)
        self.assertTrue(all(not detail['personalDeductionsAdded'] for row in rows.values() for detail in row['details']))

    def test_official_intern_roster_integrates_19_posts_without_changing_teaching(self):
        state=blank();projection=official_projection(state['classes'])
        self.assertEqual(len(projection),19)
        self.assertEqual(len({row['person'] for row in projection}),19)
        self.assertTrue(all(len(row['shifts'])==1 for row in projection))
        data=integration_snapshot(state,self.ledger,2027)
        summary=data['directPersonnelSummary']
        self.assertEqual(summary['interns'],19);self.assertEqual(summary['fixedAssistants'],0)
        self.assertEqual(summary['internMonthly'],14250);self.assertEqual(summary['fixedAssistantMonthly'],0)
        self.assertEqual(sum((row['internCostMonthly'] or 0) for row in data['classes']),14250)
        self.assertEqual(data['teachingCostMonthly'],122673.00)
        self.assertEqual(len(data['classes']),41)
        self.assertEqual(sum(row['structuralStatus']=='DEFINITIVO' for row in data['classes']),41)

    def test_official_budget_reconciliation_prevents_teacher_and_intern_duplication(self):
        state=blank();data=integration_snapshot(state,self.ledger,2027);audit=data['budgetReconciliation']
        self.assertEqual(audit['officialMonthly'],841486.96)
        self.assertEqual(audit['teachingCaptured'],122673.00)
        self.assertEqual(audit['internsCaptured'],14250)
        self.assertEqual(audit['sharedDistributed'],704563.96)
        self.assertEqual(audit['excluded'],0);self.assertEqual(audit['pending'],0);self.assertEqual(audit['difference'],0)
        self.assertEqual(round(sum(row['totalCostMonthly'] for row in data['classes']),2),841486.96)
        self.assertEqual(round(sum(row['indirectExpensesMonthly'] for row in data['classes']),2),704563.96)

    def test_structural_allocation_closes_capacity_segment_class_and_rounding(self):
        classes=blank()['classes']
        for allocator,args in ((allocate_by_capacity,(classes,)),(allocate_per_class,(classes,))):
            result=allocator(10001,*args);self.assertEqual(sum(result.values()),10001)
        segment=allocate_by_segment(10001,classes,'Educação Infantil')
        self.assertEqual(sum(segment.values()),10001)
        self.assertEqual(set(segment),{room['id'] for room in classes if room['stage']=='Educação Infantil'})
        capacity=allocate_by_capacity(10001,classes)
        largest=max(classes,key=lambda room:room['capacity']);smallest=min(classes,key=lambda room:room['capacity'])
        self.assertGreater(capacity[largest['id']],capacity[smallest['id']])

    def test_g2a_structural_pe_uses_full_cost_and_official_ticket(self):
        data=integration_snapshot(blank(),self.ledger,2027);g2=next(row for row in data['classes'] if row['name']=='G2 A')
        self.assertEqual(g2['structuralGrossTicket'],930.69)
        self.assertEqual(g2['structuralDiscountPercent'],3)
        self.assertEqual(g2['structuralDelinquencyPercent'],4.5)
        self.assertEqual(g2['structuralTicketMonthly'],862.14)
        self.assertEqual((g2['teachingCostMonthly'],g2['internCostMonthly'],g2['assistantCostMonthly']),(2397.60,750,None))
        self.assertEqual(g2['indirectExpensesMonthly'],10395.49)
        self.assertEqual(g2['totalCostMonthly'],13543.09)
        self.assertEqual(g2['breakEvenStudents'],16)
        self.assertAlmostEqual(g2['breakEvenPercentCapacity'],16/18*100)
        self.assertEqual(g2['physicalMarginStudents'],2)
        self.assertEqual(g2['structuralStatus'],'DEFINITIVO')
        self.assertEqual(len(g2['structuralAllocationDetails']),3)
        self.assertTrue(all(item['criterion']=='ALOCACAO_DIRETA_ORCAMENTO_OFICIAL'
                            for item in g2['structuralAllocationDetails']))

    def test_g2_official_rows_replace_global_capacity_without_double_counting(self):
        data=integration_snapshot(blank(),self.ledger,2027)
        expected={'G2 A':(2397.60,10395.49),'G2 B':(2374.47,10418.62)}
        for name,(teacher,shared) in expected.items():
            row=next(item for item in data['classes'] if item['name']==name)
            self.assertEqual(row['teachingCostMonthly'],teacher)
            self.assertEqual(row['internCostMonthly'],750)
            self.assertEqual(row['indirectExpensesMonthly'],shared)
            self.assertEqual(row['totalCostMonthly'],13543.09)
            details={item['id']:item for item in row['structuralAllocationDetails']}
            self.assertEqual(details['payroll-class']['sourceClassMonthly'],6271.93)
            self.assertEqual(details['payroll-class']['capturedInClass'],teacher)
            self.assertEqual(details['support-payroll']['sourceClassMonthly'],1520)
            self.assertEqual(details['support-payroll']['capturedInClass'],750)
            self.assertEqual(details['general-expenses']['assignedValue'],5751.16)
        self.assertEqual(round(sum(row['totalCostMonthly'] for row in data['classes']),2),841486.96)

    def test_ensino_medio_is_rebuilt_from_official_2026_matrix(self):
        data=integration_snapshot(blank(),self.ledger,2027)
        source_rows={row['class_name']:row for row in self.ledger['classes']}
        for name in ('1º EM','2º EM','3º EM'):
            row=next(item for item in data['classes'] if item['name']==name)
            source=source_rows[name]
            self.assertEqual((row['teachingCostWeekly'],row['teachingCostMonthly']),(1424.50,6410.25))
            self.assertEqual(sum(item['weekly_lesson_equivalents'] for item in source['teacher_costs']),37)
            self.assertEqual(sum(item['weekly_cost'] for item in source['teacher_costs']),1424.50)
            self.assertTrue(all(item['weekly_cost']==item['weekly_lesson_equivalents']*38.50
                                for item in source['teacher_costs']))
            self.assertTrue(all(item['weekly_minutes']==item['weekly_lesson_equivalents']*45
                                for item in source['teacher_costs']))
            self.assertEqual(source['pending_occurrence_ids'],[])
        first=source_rows['1º EM']
        self.assertTrue(any(item['professor']=='Terezinha Jane Lima de Souza' and
                            item['disciplines']==['Arte'] for item in first['teacher_costs']))

    def test_two_interns_in_same_class_are_1500_and_source_is_auditable(self):
        data=integration_snapshot(blank(),self.ledger,2027)
        for name in ('G4 A','G4 B'):
            row=next(item for item in data['classes'] if item['name']==name)
            self.assertEqual(row['internCostMonthly'],1500)
            self.assertEqual(len(row['directPersonnelDetails']),2)
            self.assertTrue(all(detail['monthlyIndividualCost']==750 for detail in row['directPersonnelDetails']))
            self.assertTrue(all(detail['source']=='Relação Estagiárias OF.xlsx' for detail in row['directPersonnelDetails']))
            self.assertTrue(all(detail['nature']=='custo direto' for detail in row['directPersonnelDetails']))
            self.assertTrue(all(detail['projectionLabel']==PROJECTION_LABEL for detail in row['directPersonnelDetails']))

    def test_name_normalization_detects_future_two_shift_fixed_assistant(self):
        state=blank();room=state['classes'][0]
        projection=projection_from_rows([
            dict(sourceRow=1,person='Áurea  da Silva',shift='MANHÃ',className=room['name']),
            dict(sourceRow=2,person='aurea da silva',shift='TARDE',className=room['name']),
        ],state['classes'])
        self.assertEqual(len(projection),1);self.assertEqual(len(projection[0]['shifts']),2)
        costs,pending=allocate_direct_personnel(projection,[room['id']])
        self.assertEqual(pending,[]);self.assertEqual(costs[room['id']]['assistant'],176400)
        detail=costs[room['id']]['details'][0]
        self.assertEqual(detail['type'],'AUXILIAR_FIXA');self.assertEqual(detail['monthlyIndividualCost'],1764)
        self.assertFalse(detail['personalDeductionsAdded'])

    def test_capacity_revenue_pe_percentage_and_margin_ignore_enrollment(self):
        state=blank();room=state['classes'][0]
        state['breakEven']['plans']=[dict(year=2027,version=1,
            delinquency={'officialPercent':4.5},structuralTicket={'discountPercent':3,'origin':'fixture oficial'})]
        before=integration_snapshot(state,self.ledger,2027)['classes'][0]
        room['opening']={'new':0,'re':0};room['unclassified']=0
        after=integration_snapshot(state,self.ledger,2027)['classes'][0]
        self.assertEqual(after['structuralPotentialRevenueMonthly'],room['capacity']*after['tuition'])
        for field in ('breakEvenStudents','breakEvenPercentCapacity','physicalMarginStudents','totalCostMonthly','structuralTicketMonthly'):
            self.assertEqual(after[field],before[field])
    def test_general_pe_uses_current_complete_revenue_and_existing_expenses(self):
        state=blank()
        for room in state['classes']:
            state['academicYears'][0]['classifications'][room['id']]={'fixed':{'noDiscount':room['students']}}
        state['breakEven']['plans']=[dict(year=2027,version=1,officialTotals={'totalExpensesMonthly':841486.96},delinquency={'officialPercent':0})]
        d=integration_snapshot(state,self.ledger,2027)
        self.assertIsNotNone(d['breakEvenStudents'])
        self.assertEqual(d['totalExpensesMonthly'],841486.96)
        self.assertEqual(d['teachingCostMonthly'],122673.00)
        self.assertEqual(d['additionalExpenseCents'],0)
