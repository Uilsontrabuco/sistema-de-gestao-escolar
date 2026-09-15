import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import blank
from teaching_cost import build_cost_ledger, direct_break_even, reconcile_code, split_cents


def lesson(codes, start='07:20', duration=45, **kw):
    return dict(professor='Teste',professor_id='1',dia_semana='Segunda',hora_inicio=start,
                duracao_minutos=duration,status_temporal='CONFIRMADO',source_class_codes=codes,
                aula_compartilhada=len(set(codes))>1,**kw)


class TeachingCostTests(unittest.TestCase):
    def test_bottom_up_different_classes_never_school_average(self):
        state=blank(); before=copy.deepcopy(state)
        result=build_cost_ledger({'records':[lesson(['EFUND01MA']),lesson(['EFUND06MA'],'08:05')]},state['classes'])
        costs={r['class_name']:r['weekly_cost'] for r in result['classes']}
        self.assertEqual(costs['1º A'],16.2);self.assertEqual(costs['6º A'],26.11)
        self.assertEqual(costs['2º A'],0)
        self.assertEqual(result['accounting']['additional_expense'],0)
        self.assertEqual(result['accounting']['general_expense_allocation'],0)
        self.assertEqual(state,before)

    def test_overlap_quarantines_both_without_deleting_records(self):
        result=build_cost_ledger({'records':[lesson(['EFUND01MA']),lesson(['EFUND01MB'],'07:40')]},blank()['classes'])
        self.assertEqual(result['summary']['records'],2)
        self.assertEqual(result['summary']['conflicting_records'],2)
        self.assertEqual(result['summary']['allocated_weekly_cost'],0)
        self.assertEqual(result['summary']['pending_weekly_cost'],32.4)

    def test_shared_duration_and_cent_residues(self):
        for duration in (40,45,50):
            result=build_cost_ledger({'records':[lesson(['EFUND06MA','EFUND06MB','EFUND06TC'],duration=duration)]},blank()['classes'])
            row=result['occurrences'][0]
            self.assertEqual(sum(Decimal(str(p['weekly_cost'])) for p in row['allocations']),Decimal('26.11'))
            self.assertAlmostEqual(sum(p['allocated_minutes'] for p in row['allocations']),duration)
            self.assertAlmostEqual(sum(p['fraction'] for p in row['allocations']),1)
            self.assertEqual(result['professors'][0]['reference_weekly_cost'],26.11)

    def test_missing_class_stays_pending_and_equal_share_is_preserved(self):
        result=build_cost_ledger({'records':[lesson(['EFUND05TC','EFUND05TD'])]},blank()['classes'])
        self.assertEqual(result['summary']['allocated_weekly_cost'],8.1)
        self.assertEqual(result['summary']['pending_weekly_cost'],8.1)
        self.assertEqual(result['summary']['cost_difference'],0)

    def test_repeated_component_is_one_lesson(self):
        r=build_cost_ledger({'records':[lesson(['EFUND01MA','EFUND01MA'])]},blank()['classes'])
        self.assertEqual(len(r['occurrences'][0]['allocations']),1)
        self.assertEqual(r['summary']['reference_weekly_cost'],16.2)

    def test_unknown_and_incompatible_tariff_are_not_zero_certified(self):
        for codes in (['XYZ'],['EINFAINVALID'],['EFUND01MA','EMERE01MA']):
            result=build_cost_ledger({'records':[lesson(codes)]},blank()['classes'])
            self.assertIsNone(result['occurrences'][0]['reference_weekly_cost'])
            self.assertEqual(result['summary']['unknown_cost_records'],1)

    def test_documented_projection_equivalences_and_missing_sections(self):
        classes=blank()['classes']
        for code in ('EINFA02MA','EINFA05TC','EMERE01MA','EMICN02MA','EMICH03MA'):
            self.assertEqual(reconcile_code(code,classes)['status'],'CONCILIADO')
        for code in ('EINFA05TD','EFUND05TD','EMERE01MB'):
            self.assertEqual(reconcile_code(code,classes)['status'],'PENDENTE')

    def test_pe_requires_complete_comparable_bases(self):
        self.assertEqual(direct_break_even('1000','300',costs_complete=True,revenue_complete=True),4)
        for cost,ticket,complete,revenue in [(None,300,True,True),(1000,0,True,True),(1000,300,False,True),(1000,300,True,False),(float('nan'),300,True,True)]:
            self.assertIsNone(direct_break_even(cost,ticket,costs_complete=complete,revenue_complete=revenue))

    def test_real_source_all_records_reconcile_without_mutation(self):
        source=Path(__file__).resolve().parents[1]/'output/auditoria-carga-horaria/extracao.json'
        preview=json.loads(source.read_text(encoding='utf-8'));before=copy.deepcopy(preview)
        result=build_cost_ledger(preview,blank()['classes']);summary=result['summary']
        self.assertEqual(summary['original_source_records'],1256);self.assertEqual(summary['professors'],50)
        self.assertEqual(summary['weekly_minutes'],54290)
        self.assertEqual(len(result['classes']),41)
        self.assertEqual(summary['cost_difference'],0)
        self.assertEqual(preview,before)
        for row in result['occurrences']:
            if row['reference_weekly_cost'] is not None:
                self.assertEqual(sum(Decimal(str(p['weekly_cost'])) for p in row['allocations']),Decimal(str(row['reference_weekly_cost'])))
            if row['allocations'] and not row.get('pool_id'):
                self.assertAlmostEqual(sum(p['allocated_minutes'] for p in row['allocations']),row['duration_minutes'])
        self.assertTrue(all(r['monthly_direct_cost'] is None for r in result['classes']))

    def test_pending_class_has_explicit_reason_and_tariff(self):
        result=build_cost_ledger({'records':[lesson(['EFUND05TD'],disciplina_componente='ARTE')]},blank()['classes'])
        p,=result['pending_allocations']
        self.assertIn('SEM_TURMA_OPERACIONAL_CORRESPONDENTE',p['pending_reasons'])
        self.assertEqual(p['hour_aula_rate_2027'],16.2)
        self.assertEqual(p['disciplines'],['ARTE'])

    def test_shared_components_belong_to_their_own_class(self):
        result=build_cost_ledger({'records':[lesson(['EFUND01MA','EFUND01MB'],disciplina_componente='ARTE | MATEM')]},blank()['classes'])
        a=next(c for c in result['classes'] if c['class_name']=='1º A')
        b=next(c for c in result['classes'] if c['class_name']=='1º B')
        self.assertEqual(a['disciplines'],['ARTE']);self.assertEqual(b['disciplines'],['MATEM'])
        self.assertEqual(a['teacher_costs'][0]['weekly_cost'],8.1)
        self.assertEqual(b['teacher_costs'][0]['weekly_cost'],8.1)

    def test_repeated_components_do_not_multiply_professor_class_cost(self):
        result=build_cost_ledger({'records':[lesson(['EFUND01MA','EFUND01MA'],disciplina_componente='ARTE | MATEM')]},blank()['classes'])
        t,=result['professors'];g,=t['class_costs']
        self.assertEqual(g['weekly_cost'],16.2)
        self.assertEqual(g['weekly_lesson_equivalents'],1)
        self.assertEqual(g['disciplines'],['ARTE','MATEM'])

    def test_professor_status_distinguishes_conciliation_and_review(self):
        r=build_cost_ledger({'records':[lesson(['EFUND01MA'])]},blank()['classes'])
        self.assertEqual(r['professors'][0]['weekly_status'],'CONCILIADO')
        r=build_cost_ledger({'records':[lesson(['EFUND05TD'])]},blank()['classes'])
        self.assertEqual(r['professors'][0]['weekly_status'],'REQUER REVISÃO')
        self.assertIsNone(r['professors'][0]['monthly_salary'])

    def test_real_pending_parcels_reconcile_after_user_shared_rule(self):
        root=Path(__file__).resolve().parents[1]
        preview=json.loads((root/'output/auditoria-carga-horaria/extracao.json').read_text(encoding='utf-8'))
        result=build_cost_ledger(preview,blank()['classes'])
        self.assertEqual(len(result['pending_allocations']),0)
        self.assertEqual(sum(Decimal(str(p['weekly_cost'])) for p in result['pending_allocations']),Decimal('0.00'))
        self.assertTrue(all(p['pending_reasons'] for p in result['pending_allocations']))
        for t in result['professors']:
            self.assertEqual(sum((Decimal(str(g['weekly_cost'])) for g in t['class_costs']),Decimal(0)),Decimal(str(t['allocated_weekly_cost'])))
        for c in result['classes']:
            self.assertEqual(sum((Decimal(str(g['weekly_cost'])) for g in c['teacher_costs']),Decimal(0)),Decimal(str(c['weekly_cost'])))

    def test_real_allocated_records_exclude_all_overlap_endpoints(self):
        root=Path(__file__).resolve().parents[1]
        preview=json.loads((root/'output/auditoria-carga-horaria/extracao.json').read_text(encoding='utf-8'))
        result=build_cost_ledger(preview,blank()['classes'])
        conflicts={i for pair in result['overlap_pairs'] for i in pair}
        allocated={r['source_index'] for r in result['occurrences'] if any(p['status']=='ALOCADO_REFERENCIA' for p in r['allocations'])}
        self.assertFalse(conflicts&allocated)
        self.assertEqual(len(conflicts),0)


if __name__=='__main__':unittest.main()
