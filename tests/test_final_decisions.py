import copy
import json
from fractions import Fraction
from pathlib import Path
import unittest
from server import blank
from teaching_cost import build_cost_ledger, load_documentary_costs, structural_destination
from test_teaching_cost import lesson


class FinalDecisionsTests(unittest.TestCase):
    def test_g5_does_not_invent_class_or_shift(self):
        classes=blank()['classes']; before=copy.deepcopy(classes)
        result=structural_destination('EINFA05TD',{'turno':'Tarde'},classes,[])
        self.assertEqual(result['status'],'PENDENTE')
        self.assertEqual(classes,before)

    def test_g5_only_unique_explicit_registered_afternoon_target(self):
        classes=blank()['classes']+[{'id':'existing','name':'G5 E','turno':'Tarde'}]
        result=structural_destination('EINFA05TD',{},classes,[])
        self.assertEqual(result['operational_class_id'],'existing')
        self.assertEqual(result['basis'],'REGRA_FINAL_G5_CADASTRO_REAL')
        classes.append({'id':'other','name':'G5 F','turno':'Tarde'})
        self.assertEqual(structural_destination('EINFA05TD',{},classes,[])['status'],'PENDENTE')

    def test_mixed_segments_keep_each_tariff_and_one_physical_lesson(self):
        rows=[lesson(['EFUND09MA','EFUND09MB'],disciplina_componente='CUTG2 | CUTG2'),
              lesson(['EMERE01MA','EMERE02MA','EMERE03MA'],disciplina_componente='CULTG | CULTG | CULTG')]
        before=copy.deepcopy(rows)
        d=build_cost_ledger({'records':rows},blank()['classes'])
        self.assertEqual(rows,before)
        self.assertEqual(len(d['occurrences']),1)
        self.assertEqual(d['validated_minutes'],45)
        self.assertEqual(d['validated_cost_cents'],6461)
        parts=d['operational_allocations']
        self.assertEqual(sum(p['reference_cost_cents'] for p in parts if p['source_code'].startswith('EFUND')),2611)
        self.assertEqual(sum(p['reference_cost_cents'] for p in parts if p['source_code'].startswith('EMERE')),3850)
        self.assertEqual({p['hour_aula_rate_2027'] for p in parts},{26.11,38.5})
        self.assertEqual(sum(Fraction(p['financial_fraction_numerator'],p['financial_fraction_denominator']) for p in parts),1)
        self.assertTrue(all(p['status']=='COMPARTILHADO_RATEADO' for p in parts))

    def test_transition_keeps_both_lessons_without_extra_cost(self):
        for teacher in ('579','868'):
            rows=[dict(lesson(['EFUND04MB'],'10:45',40),professor_id=teacher),dict(lesson(['EFUND08MA'],'11:20',45),professor_id=teacher)]
            d=build_cost_ledger({'records':rows},blank()['classes'])
            self.assertEqual(d['validated_cost_cents'],4231)
            self.assertEqual(d['validated_minutes'],85)
            self.assertEqual(d['conflicted_cost_cents'],0)
            self.assertEqual(d['transitions'][0]['status'],'TRANSICAO_ENTRE_AULAS')
            self.assertEqual(d['transitions'][0]['additional_cost_cents'],0)
            rows[1]['hora_inicio']='11:19'
            self.assertEqual(build_cost_ledger({'records':rows},blank()['classes'])['conflicted_cost_cents'],4231)

    def test_morning_confirmation_preserves_source_clock(self):
        rows=[dict(lesson(['EMERE03MA'],'13:15',45,disciplina_componente='SOCIO'),professor_id='864'),
              dict(lesson(['EFUND01TC'],'13:55',45,disciplina_componente='IGLMI'),professor_id='864')]
        d=build_cost_ledger({'records':rows},blank()['classes'])
        self.assertEqual(d['conflicted_cost_cents'],0)
        self.assertEqual(d['occurrences'][0]['confirmed_shift'],'Manhã')
        self.assertEqual(d['occurrences'][0]['start'],'13:15')
        self.assertEqual(d['source_records'],rows)

    def test_jose_sharing_confirmed_but_duration_not_invented(self):
        rows=[dict(lesson(['EINFA04MA'],'07:40',40),professor_id='590'),dict(lesson(['EFUND02MA'],'07:20',45),professor_id='590')]
        d=build_cost_ledger({'records':rows},blank()['classes'])
        self.assertEqual(d['validated_cost_cents'],3240)
        self.assertTrue(all(r['shared_confirmed'] for r in d['occurrences']))
        self.assertEqual([r['duration_minutes'] for r in d['occurrences']],[40,45])

    def test_real_previous_confirmed_shares_unchanged_and_all_sources_tracked(self):
        old=json.loads((Path(__file__).resolve().parents[1]/'output/rateio-5-ano-confirmado/resultado.json').read_text(encoding='utf-8'))
        state=blank();before=copy.deepcopy(state);d=load_documentary_costs(state['classes'])
        self.assertEqual(state,before)
        self.assertEqual(d['source_records'],old['source_records'])
        mapped={tuple(r['original_source_indices']):r for r in d['occurrences']}
        fields=('source_code','class_id','weekly_cost','allocated_minutes','fraction','operational_status')
        for row in old['occurrences']:
            previous=[p for p in row['allocations'] if p['operational_status'] in ('VALIDADO_E_ATRIBUIDO','COMPARTILHADO_RATEADO')]
            if previous:
                current=mapped[tuple(row['original_source_indices'])]
                self.assertTrue(all(tuple(p[k] for k in fields) in [tuple(q[k] for k in fields) for q in current['allocations']] for p in previous))
        self.assertEqual(sorted(i for r in d['occurrences'] for i in r['original_source_indices']),list(range(len(d['source_records']))))
        self.assertEqual(d['validated_cost_cents']-old['validated_cost_cents'],160714)
        self.assertEqual(d['reference_cost_cents'],2567735)
        self.assertEqual(d['summary']['reconciled_professors'],50)
        self.assertEqual(len(d['classes']),41)
        self.assertEqual(d['summary']['financial_duplicates'],0)
