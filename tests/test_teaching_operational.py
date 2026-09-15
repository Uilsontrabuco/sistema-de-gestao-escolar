import copy
import unittest
from test_teaching_cost import lesson
from server import blank
from teaching_cost import build_cost_ledger, load_documentary_costs

class OperationalTests(unittest.TestCase):
    def build(self, records, evidence=None):
        return build_cost_ledger({'records':records,'class_evidence':evidence or []},blank()['classes'])
    def structural(self):
        r=lesson(['EFUND05TD'],disciplina_componente='ART',ano_serie='5',turno='Tarde',source_cell_x=12,source_cell_y=30,pagina=1)
        e={**r,'source_code':'EFUND05TD','source_reference':'Documento de vínculo verificado, p. 1', 'status':'VERIFICADO','segment':'Fundamental I','target_code':'EFUND05TA','class_id':'caj-2027-caj-5-a'}
        return r,e
    def test_unique_d(self):
        r,e=self.structural(); data=self.build([r],[e])
        self.assertEqual(data['validated_cost'],16.2)
        self.assertEqual(data['audit_log'][0]['action'],'RESOLVIDO_POR_CORRESPONDENCIA_UNICA')
    def test_ambiguous_d(self):
        r,e=self.structural(); other={**e,'target_code':'EFUND05TB','class_id':'caj-2027-caj-5-b'}
        data=self.build([r],[e,other]); self.assertEqual(data['validated_cost'],0)
        self.assertEqual(data['operational_allocations'][0]['status'],'SEM_DESTINO')
    def test_incomplete_evidence_cannot_resolve(self):
        r,e=self.structural(); del e['turno']
        self.assertEqual(self.build([r],[e])['unassigned_cost'],16.2)
    def test_true_overlap(self):
        data=self.build([lesson(['EFUND01MA']),lesson(['EFUND01MB'],'07:40')])
        self.assertEqual(data['conflicted_cost'],32.4);self.assertEqual(data['validated_minutes'],0)
    def test_duplicate_physical_cell(self):
        r=lesson(['EFUND01MA'],disciplina_componente='ART',pagina=1,source_cell_x=1,source_cell_y=2)
        data=self.build([r,copy.deepcopy(r)])
        self.assertEqual(data['validated_cost'],16.2);self.assertEqual(data['validated_minutes'],45)
        self.assertEqual(data['operational_allocations'][1]['status'],'DUPLICATA_NAO_CONTABILIZADA')
        self.assertEqual(data['operational_allocations'][1]['duplicate_of'],'O0001')
    def test_shared_exact_cents(self):
        data=self.build([lesson(['EFUND06MA','EFUND06MB'],duration=50)])
        parts=data['operational_allocations']
        self.assertEqual([p['validated_cost_cents'] for p in parts],[1306,1305])
        self.assertTrue(all(p['status']=='COMPARTILHADO_RATEADO' for p in parts))
        self.assertEqual(data['validated_minutes'],50)
    def test_documentary_conflict_no_priority_guess(self):
        data=self.build([lesson(['EFUND01MA']),lesson(['EFUND01MB'],'07:40')])
        self.assertTrue(all(p['status']=='CONFLITO_DOCUMENTAL' for p in data['operational_allocations']))
    def test_teacher_mixed(self):
        data=self.build([lesson(['EFUND01MA']),lesson(['EFUND01MB'],'07:40'),lesson(['EFUND01MA'],'09:00')])
        t=data['professors'][0]
        self.assertEqual((t['validated_cost'],t['conflicted_cost'],t['reference_cost']),(16.2,32.4,48.6))
        self.assertEqual(t['status'],'PROCESSADO_COM_RESSALVAS')
    def test_unknown_not_zero(self):
        data=self.build([lesson([])])
        self.assertIsNone(data['reference_cost']);self.assertIsNone(data['conflicted_cost'])
        self.assertEqual(len(data['operational_allocations']),1)
    def test_real_integral_reconciliation(self):
        data=load_documentary_costs(blank()['classes'])
        self.assertEqual((data['validated_cost_cents'],data['conflicted_cost_cents'],data['unassigned_cost_cents'],data['reference_cost_cents']),(2567735,0,0,2567735))
        self.assertEqual(data['summary']['pending_allocations'],0)
        self.assertEqual(data['summary']['reconciled_professors'],50)
        self.assertEqual(data['summary']['classified_records'],1235)
        self.assertEqual(len(data['professors']),50)
    def test_no_double_count(self):
        data=self.build([lesson(['EFUND05TD']),lesson(['EFUND01MA'],'07:40')])
        self.assertEqual(data['conflicted_cost'],32.4);self.assertEqual(data['unassigned_cost'],0)
        self.assertEqual(sum(p['reference_cost_cents'] for p in data['operational_allocations']),3240)
    def test_preserve_41_and_pe_code(self):
        state=blank();before=copy.deepcopy(state);load_documentary_costs(state['classes'])
        self.assertEqual(state,before);self.assertEqual(len(state['classes']),41)
