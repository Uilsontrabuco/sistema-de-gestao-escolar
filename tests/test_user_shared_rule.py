import copy
import json
from pathlib import Path
import unittest
from fractions import Fraction
from test_teaching_cost import lesson
from server import blank
from teaching_cost import build_cost_ledger, _build_cost_ledger


class UserSharedRuleTests(unittest.TestCase):
    def test_single_cost_and_duration_for_each_real_duration(self):
        for duration in (40,45,50):
            data=build_cost_ledger({'records':[lesson(['EFUND01MA'],duration=duration),lesson(['EFUND01MB'],duration=duration)]},blank()['classes'])
            self.assertEqual(data['validated_cost'],16.2)
            self.assertEqual(data['validated_minutes'],duration)
            self.assertEqual(data['conflicted_cost'],0)
            self.assertEqual(len(data['source_records']),2)
            self.assertTrue(all(p['status']=='COMPARTILHADO_RATEADO' for p in data['operational_allocations']))
    def test_union_of_participants_not_repeated_codes(self):
        rows=[lesson(['EFUND01MA','EFUND01MB'],disciplina_componente='ART | ART'),lesson(['EFUND01MB','EFUND01TC'],disciplina_componente='ART | ART')]
        data=build_cost_ledger({'records':rows},blank()['classes'])
        parts=data['operational_allocations']
        self.assertEqual(len(parts),3)
        self.assertEqual([p['validated_cost_cents'] for p in parts],[540]*3)
        self.assertEqual(sum(Fraction(p['fraction_numerator'],p['fraction_denominator']) for p in parts),1)
    def test_mixed_rates_do_not_choose_salary(self):
        data=build_cost_ledger({'records':[lesson(['EFUND09MA']),lesson(['EMERE01MA'])]},blank()['classes'])
        self.assertEqual(data['validated_cost'],64.61)
        self.assertEqual(data['conflicted_cost'],0)
    def test_different_duration_not_invented(self):
        data=build_cost_ledger({'records':[lesson(['EFUND01MA'],duration=40),lesson(['EFUND01MB'],duration=45)]},blank()['classes'])
        self.assertEqual(data['conflicted_cost'],32.4)
    def test_real_delta_and_exclusively_unassigned_preserved(self):
        source=json.loads((Path(__file__).resolve().parents[1]/'output/auditoria-carga-horaria/extracao.json').read_text(encoding='utf-8'))
        before=copy.deepcopy(source)
        old=_build_cost_ledger(source,blank()['classes']);new=build_cost_ledger(source,blank()['classes'])
        self.assertEqual(source,before)
        self.assertEqual(new['conflicted_cost_cents'],0)
        self.assertEqual(new['validated_cost_cents'],2567735)
        self.assertEqual(new['summary']['reference_reduction'],291.6)
        mapped={i:r for r in new['occurrences'] for i in r['original_source_indices']}
        for row in old['occurrences']:
            if row['status']=='SEM_DESTINO' and 'EFUND05TD' not in row['source_codes']:
                after=mapped[row['source_index']]
                self.assertEqual(after['original_source_indices'],[row['source_index']])
                self.assertEqual([(p['source_code'],p['weekly_cost'],p['operational_status']) for p in row['allocations']],[(p['source_code'],p['weekly_cost'],p['operational_status']) for p in after['allocations']])
        self.assertEqual(len(new['classes']),41)
        self.assertEqual(new['validated_cost_cents']+new['conflicted_cost_cents']+new['unassigned_cost_cents'],new['reference_cost_cents'])
