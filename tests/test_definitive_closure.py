import copy
import json
from pathlib import Path
from fractions import Fraction
import unittest
from server import blank
from teaching_cost import build_cost_ledger, load_documentary_costs
from test_teaching_cost import lesson


class DefinitiveClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=load_documentary_costs(blank()['classes'])
        cls.old=json.loads((Path(__file__).resolve().parents[1]/'output/decisoes-finais-2027/resultado.json').read_text(encoding='utf-8'))

    def test_g5_three_exact_shares_single_cost_and_original_duration(self):
        for duration in (40,45,50):
            source=lesson(['EINFA05TD'],duration=duration,disciplina_componente='IGLMI')
            d=build_cost_ledger({'records':[source]},blank()['classes'])
            self.assertEqual(d['validated_cost_cents'],1620)
            self.assertEqual(d['validated_minutes'],duration)
            self.assertEqual(len(d['occurrences']),1)
            self.assertEqual([p['validated_cost_cents'] for p in d['operational_allocations']],[540]*3)
            self.assertEqual({p['class_id'] for p in d['operational_allocations']},{'caj-2027-caj-g5-a','caj-2027-caj-g5-b','caj-2027-caj-g5-c'})
            self.assertEqual(d['source_records'],[source])
            self.assertIn('RATEIO_G5_ABC_CONFIRMADO_PELO_USUARIO',[a['action'] for a in d['audit_log']])

    def test_indivisible_pool_cents_are_deterministic_and_conserved(self):
        from teaching_pools import apply_financial_pools
        # Isolar o resíduo em centavos sem inventar tarifa no modelo produtivo.
        from teaching_cost import _build_cost_ledger
        original=_build_cost_ledger({'records':[lesson(['EINFA05TD'],disciplina_componente='IGLMI')]},blank()['classes'])
        original['occurrences'][0]['allocations']=original['occurrences'][0]['documentary_allocations']
        original['occurrences'][0]['allocations'][0]['weekly_cost']=16.21
        original['occurrences'][0]['reference_weekly_cost']=16.21
        first=apply_financial_pools(copy.deepcopy(original))
        second=apply_financial_pools(copy.deepcopy(original))
        parts=first['occurrences'][0]['allocations']
        self.assertEqual([p['weekly_cost'] for p in parts],[5.41,5.4,5.4])
        self.assertEqual(parts,second['occurrences'][0]['allocations'])

    def test_jose_each_connected_block_has_one_pool_with_original_balance(self):
        pools=self.data['financial_pools']
        self.assertEqual(len(pools),11)
        self.assertEqual(sum(p['cost_cents'] for p in pools),68040)
        self.assertEqual(len({p['pool_id'] for p in pools}),11)
        covered=[oid for p in pools for oid in p['occurrence_ids']]
        self.assertEqual(len(covered),len(set(covered)))
        self.assertEqual(len(covered),42)
        old={r['occurrence_id']:r for r in self.old['occurrences']}
        for pool in pools:
            self.assertEqual(pool['cost_cents'],sum(old[oid]['conflicted_cost_cents'] for oid in pool['occurrence_ids']))

    def test_original_times_40_45_50_preserved_without_invented_pool_duration(self):
        old={r['occurrence_id']:r for r in self.old['occurrences']}
        durations=set()
        for pool in self.data['financial_pools']:
            self.assertIsNone(pool['duration_minutes'])
            for source in pool['source_times']:
                for field in ('start','duration_minutes','page','evidence'):
                    self.assertEqual(source[field],old[source['occurrence_id']][field])
                durations.add(source['duration_minutes'])
        self.assertEqual(durations,{40,45,50})

    def test_pools_equal_unique_participants_and_no_second_financial_representation(self):
        for pool in self.data['financial_pools']:
            parts=[p for p in self.data['operational_allocations'] if p.get('pool_id')==pool['pool_id']]
            self.assertEqual(len(parts),len(pool['participant_class_ids']))
            self.assertEqual({p['class_id'] for p in parts},set(pool['participant_class_ids']))
            self.assertEqual(sum(p['validated_cost_cents'] for p in parts),pool['cost_cents'])
            self.assertEqual(sum(Fraction(p['fraction_numerator'],p['fraction_denominator']) for p in parts),1)
            self.assertLessEqual(max(p['validated_cost_cents'] for p in parts)-min(p['validated_cost_cents'] for p in parts),1)
            self.assertEqual(len({p['source_reference']['occurrence_id'] for p in parts}),1)

    def test_documentary_observations_do_not_block_finance(self):
        d=self.data
        self.assertEqual(d['summary']['documentary_time_observations'],42)
        self.assertEqual(d['conflicted_cost_cents'],0)
        self.assertEqual(d['unassigned_cost_cents'],0)
        self.assertEqual(d['pending_allocations'],[])
        self.assertEqual(d['summary']['reconciled_professors'],50)
        self.assertEqual(sum(t['weekly_lesson_equivalents'] for t in d['professors']),d['summary']['financial_units'])
        self.assertTrue(all(r['status']=='COMPARTILHADO_RATEADO' for r in d['occurrences'] if r.get('documentary_status')=='SOURCE_TIME_REVIEW'))

    def test_no_source_lost_and_previous_confirmed_finance_unchanged(self):
        d=self.data;old=self.old
        self.assertEqual(d['source_records'],old['source_records'])
        mapped={r['occurrence_id']:r for r in d['occurrences']}
        keys=('source_code','class_id','weekly_cost','fraction','allocated_minutes')
        for row in old['occurrences']:
            before=[tuple(p[k] for k in keys) for p in row['allocations'] if p['operational_status'] in ('COMPARTILHADO_RATEADO','VALIDADO_E_ATRIBUIDO')]
            if before:
                after=[tuple(p[k] for k in keys) for p in mapped[row['occurrence_id']]['allocations']]
                self.assertTrue(all(p in after for p in before))
        self.assertEqual(sorted(i for r in d['occurrences'] for i in r['original_source_indices']),list(range(1256)))
        self.assertEqual(d['validated_cost_cents']-old['validated_cost_cents'],275780)
        self.assertEqual(d['validated_cost_cents'],d['reference_cost_cents'])
        self.assertEqual(d['summary']['unexplained_cost_cents'],0)
        self.assertEqual(d['summary']['financial_duplicates'],0)
