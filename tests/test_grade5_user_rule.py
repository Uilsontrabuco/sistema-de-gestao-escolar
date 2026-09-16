import copy
import json
from pathlib import Path
import unittest
from server import blank
from teaching_cost import build_cost_ledger,load_documentary_costs
from test_teaching_cost import lesson


class Grade5RuleTests(unittest.TestCase):
    def row(self,companion=None,shift='Tarde',start='13:10'):
        codes=([companion] if companion else [])+['EFUND05TD']
        return lesson(codes,start,turno=shift,disciplina_componente=' | '.join(['MATEM']*len(codes)),
            source_cell_x=1,source_cell_y=2,evidencia_original='Célula documental',pagina=1)
    def test_afternoon_complement_b_and_c(self):
        for code,name in [('EFUND05TC','5º B'),('EFUND05MB','5º C')]:
            data=build_cost_ledger({'records':[self.row(code)]},blank()['classes'])
            p=next(p for p in data['operational_allocations'] if p['source_code']=='EFUND05TD')
            self.assertEqual(next(c['class_name'] for c in data['classes'] if c['class_id']==p['class_id']),name)
            self.assertEqual(p['link_basis'],'RESOLVIDO_POR_CORRESPONDENCIA_UNICA')
            self.assertEqual(data['validated_cost'],16.2)
    def test_morning_uses_grade_shift_not_code_t(self):
        data=build_cost_ledger({'records':[self.row('EFUND05MB','Manhã','07:20')]},blank()['classes'])
        p=next(p for p in data['operational_allocations'] if p['source_code']=='EFUND05TD')
        self.assertEqual(p['class_id'],'caj-2027-caj-5-a')
    def test_alone_does_not_infer_from_other_times(self):
        data=build_cost_ledger({'records':[self.row(),self.row('EFUND05TC',start='15:45')]},blank()['classes'])
        self.assertEqual([p['operational_status'] for p in data['occurrences'][0]['allocations']],['COMPARTILHADO_RATEADO']*2)
    def test_time_shift_disagreement_stays_unassigned(self):
        data=build_cost_ledger({'records':[self.row('EFUND05TC',start='07:20')]},blank()['classes'])
        self.assertEqual(data['unassigned_cost'],8.1)
    def test_real_only_grade5_destinations_change(self):
        old=json.loads((Path(__file__).resolve().parents[1]/'output/regra-5-ano-usuario-2027/resultado.json').read_text(encoding='utf-8'))
        state=blank();before=copy.deepcopy(state);new=load_documentary_costs(state['classes'])
        self.assertEqual(state,before)
        changes=[]
        mapped={tuple(r['original_source_indices']):r for r in new['occurrences']}
        for a in old['occurrences']:
            if 'EFUND05TD' not in a['source_codes']: continue
            b=mapped[tuple(a['original_source_indices'])]
            if b.get('pool_id'): continue
            for field in ('source_codes','professor_id','disciplines','start','duration_minutes','original_source_references','reference_weekly_cost'):
                self.assertEqual(a[field],b[field])
            original=[p for p in a['allocations'] if p['source_code']=='EFUND05TD' and p['operational_status']=='SEM_DESTINO']
            if original:
                resolved=[p for p in b['allocations'] if p['link_basis']=='REGRA_USUARIO_5_ANO_RATEIO_50_50']
                self.assertEqual(len(resolved),2)
                self.assertTrue(all(p['operational_status']=='COMPARTILHADO_RATEADO' for p in resolved))
                self.assertEqual(resolved[0]['weekly_cost'],resolved[1]['weekly_cost'])
                self.assertAlmostEqual(sum(p['weekly_cost'] for p in resolved),original[0]['weekly_cost'])
                changes.append(original[0])
            else:
                self.assertEqual([(p['source_code'],p['class_id'],p['weekly_cost'],p['operational_status']) for p in a['allocations']],[(p['source_code'],p['class_id'],p['weekly_cost'],p['operational_status']) for p in b['allocations']])
        self.assertEqual(len(changes),32)
        self.assertEqual(round(sum(p['weekly_cost'] for p in changes)*100),36450)
        self.assertEqual(new['reference_cost_cents'],old['reference_cost_cents'])
        self.assertEqual(new['conflicted_cost_cents'],0)
        self.assertEqual(len(new['classes']),41)

    def test_both_shifts_and_all_durations(self):
        for shift,start,names in [('Manhã','07:20',{'5º A','5º B'}),('Tarde','13:10',{'5º C','5º B'})]:
            for duration in (40,45,50):
                row=self.row(shift=shift,start=start)
                row['duracao_minutos']=duration
                row.pop('hora_fim',None)
                data=build_cost_ledger({'records':[row]},blank()['classes'])
                self.assertEqual(data['validated_minutes'],duration)
                self.assertEqual(data['validated_cost'],16.2)
                self.assertEqual(len(data['occurrences']),1)
                self.assertEqual({c['class_name'] for c in data['classes'] if c['weekly_cost']},names)
                self.assertEqual([p['fraction'] for p in data['operational_allocations']],[0.5,0.5])
