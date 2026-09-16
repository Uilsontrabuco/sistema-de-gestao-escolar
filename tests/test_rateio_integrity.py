"""Contrato de auditoria: fixtures sintéticas, sem banco e sem alterar a implementação."""
import copy
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import blank
from services import build_teaching_weekly_cost_with_shared_rateio_audit as audit


def occurrence(codes, duration=45, **changes):
    return dict(professor='Docente fixture', professor_id='fixture',
                source_class_codes=codes, duracao_minutos=duration,
                status_temporal='CONFIRMADO', status_vinculo_turma='PENDENTE',
                aula_compartilhada=True, disciplina_componente='ARTE', **changes)


class RateioIntegrityTests(unittest.TestCase):
    def test_equal_fractions_and_exact_cent_conservation_2_3_4_7_participants(self):
        for count in (2, 3, 4, 7):
            for duration in (40, 45, 50):
                with self.subTest(count=count, duration=duration):
                    codes = [f'EFUND06M{chr(65+i)}' for i in range(count)]
                    result = audit({'records': [occurrence(codes, duration)]}, blank()['classes'])
                    shared = result['shared_lesson_rateio']
                    row, = shared['allocations']
                    parts = row['allocations']
                    self.assertEqual(len(parts), count)
                    self.assertTrue(all(p['fraction'] == 1/count for p in parts))
                    self.assertAlmostEqual(sum(p['fraction'] for p in parts), 1, places=12)
                    amounts = [Decimal(str(p['amount'])) for p in parts]
                    self.assertEqual(sum(amounts), Decimal('26.11'))
                    self.assertLessEqual(max(amounts)-min(amounts), Decimal('.01'))
                    self.assertTrue(all(a < Decimal('26.11') for a in amounts))
                    self.assertEqual(shared['closure_difference'], 0)
                    self.assertEqual(row['duration_minutes'], duration)
                    self.assertAlmostEqual(sum(p['allocated_minutes'] for p in parts), duration, delta=1e-9)
                    self.assertTrue(all(abs(p['allocated_minutes']-duration/count)<1e-9 for p in parts))
                    self.assertAlmostEqual(shared['allocated_minutes_to_operational_classes']+shared['allocated_minutes_pending_code'],duration,delta=1e-9)
                    self.assertEqual(result['professors'][0]['weekly_minutes'], duration)

    def test_global_occurrences_cost_and_all_41_classes_are_preserved(self):
        state = blank()
        before = copy.deepcopy(state)
        preview = {'records': [occurrence(['EFUND01MA', 'EFUND01MB'], d) for d in (40,45,50)]}
        original = copy.deepcopy(preview)
        result = audit(preview, state['classes'])
        self.assertEqual(state, before)
        self.assertEqual(preview, original)
        self.assertEqual(len(result['classes']), 41)
        self.assertEqual({r['class_id'] for r in result['classes']}, {r['id'] for r in state['classes']})
        self.assertEqual(result['summary']['real_occurrences'], 3)
        self.assertEqual(result['shared_lesson_rateio']['occurrences'], 3)
        self.assertEqual(sum(r['weekly_lessons'] for r in result['professors']), 3)
        self.assertEqual(sum(r['weekly_minutes'] for r in result['professors']), 135)
        self.assertEqual(sum(r['weekly_minutes'] for r in result['classes']), 135)
        self.assertEqual(result['summary']['shared_lessons_pending'], 0)
        self.assertEqual(result['shared_lesson_rateio']['pending_links'], 0)
        self.assertEqual(result['pending_occurrences'], [])
        self.assertEqual(sum(Decimal(str(r['reference_weekly_cost'])) for r in result['classes']), Decimal('48.60'))
        self.assertEqual(result['summary']['reference_weekly_cost'], 48.60)
        self.assertIsNone(result['summary']['monthly_cost'])

    def test_shared_minutes_reach_operational_classes_without_loss(self):
        result = audit({'records': [occurrence(['EFUND01MA','EFUND01MB'], 45)]}, blank()['classes'])
        self.assertEqual(sum(r['weekly_minutes'] for r in result['classes']), 45)

    def test_pending_em_sections_never_receive_operational_cost(self):
        for family in ('EMERE','EMICN','EMICH'):
            with self.subTest(family=family):
                result = audit({'records': [occurrence([family+'01MA',family+'02MB'])]}, blank()['classes'])
                shared = result['shared_lesson_rateio']
                self.assertEqual(shared['allocated_to_operational_classes'], 0)
                self.assertEqual(shared['allocated_pending_code'], 38.50)

    def test_unknown_code_remains_pending_without_exception(self):
        result = audit({'records': [occurrence(['DESCONHECIDO'])]}, blank()['classes'])
        self.assertEqual(result['shared_lesson_rateio']['occurrences'], 0)
        self.assertGreater(result['summary']['shared_lessons_pending'], 0)
        self.assertEqual(result['shared_lesson_rateio']['pending_links'], 1)

    def test_unconfirmed_time_is_not_allocated(self):
        row = occurrence(['EFUND01MA','EFUND01MB'])
        row['status_temporal'] = 'PENDENTE'
        result = audit({'records': [row]}, blank()['classes'])
        self.assertEqual(result['shared_lesson_rateio']['occurrences'], 0)

    def test_pending_participant_is_not_reported_as_zero_pending(self):
        result = audit({'records': [occurrence(['EFUND01MA','EFUND01MZ'])]}, blank()['classes'])
        self.assertEqual(result['summary']['shared_lessons_pending'], 1)

    def test_repeated_code_does_not_duplicate_single_occurrence(self):
        result = audit({'records': [occurrence(['EFUND01MA','EFUND01MA'])]}, blank()['classes'])
        shared = result['shared_lesson_rateio']
        self.assertEqual(shared['occurrences'], 1)
        self.assertEqual(len(shared['allocations'][0]['allocations']), 1)
        self.assertEqual(shared['original_cost_total'], 16.20)

    def test_einfa_keeps_minutes_and_cost_in_explicit_pending_parcels(self):
        result = audit({'records':[occurrence(['EINFA01MA','EINFA02MA'],50)]},blank()['classes'])
        shared = result['shared_lesson_rateio']
        self.assertEqual(shared['allocated_to_operational_classes'],0)
        self.assertEqual(shared['allocated_pending_code'],16.20)
        self.assertEqual(shared['allocated_minutes_pending_code'],50)
        self.assertEqual(shared['pending_links'],2)
        self.assertEqual(result['summary']['shared_lessons_pending'],1)
        self.assertTrue(all('gramática' in p['reason'] for p in shared['pending_code_allocations']))

    def test_global_mixed_pending_and_valid_occurrences_are_not_lost(self):
        rows = [occurrence(['EFUND01MA','EFUND01MB'],40),
                occurrence(['EMERE01MA','EMERE02MB'],45),
                occurrence(['EINFA01MA','EINFA02MA'],50),
                occurrence(['DESCONHECIDO'],40)]
        result = audit({'records':rows},blank()['classes'])
        shared = result['shared_lesson_rateio']
        self.assertEqual(shared['occurrences']+len(shared['unallocated_occurrences']),4)
        self.assertEqual(result['summary']['shared_lessons_pending'],3)
        self.assertEqual(len(result['pending_occurrences']),3)
        self.assertEqual(result['professors'][0]['pending_occurrences'],3)
        self.assertEqual(shared['original_minutes_total'],135)
        self.assertEqual(shared['allocated_minutes_to_operational_classes']+shared['allocated_minutes_pending_code'],135)
        self.assertEqual(shared['original_minutes_total']+sum(r['duration_minutes'] for r in shared['unallocated_occurrences']),175)
        self.assertEqual(result['professors'][0]['weekly_minutes'],175)
        self.assertEqual(Decimal(str(shared['allocated_to_operational_classes']))+Decimal(str(shared['allocated_pending_code'])),Decimal('70.90'))
        self.assertEqual(result['summary']['reference_weekly_cost'],70.90)

    def test_empty_malformed_and_mixed_tariff_inputs_are_pending(self):
        for codes in ([],['EFUNDINVALIDO'],['EMERE99MA'],['EFUND01MA','DESCONHECIDO'],['EFUND01MA','EFUND06MA']):
            with self.subTest(codes=codes):
                result = audit({'records':[occurrence(codes)]},blank()['classes'])
                self.assertEqual(result['summary']['shared_lessons_pending'],1)
                self.assertEqual(result['shared_lesson_rateio']['occurrences'],0)
                self.assertEqual(sum(r['reference_weekly_cost'] for r in result['classes']),0)
                self.assertEqual(sum(r['weekly_minutes'] for r in result['classes']),0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
