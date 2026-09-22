import json,unittest
from copy import deepcopy
from pathlib import Path
from scripts.unblock_pe_forensic import investigate

ROOT=Path(__file__).resolve().parents[1]

class ForensicUnblockTests(unittest.TestCase):
    def setUp(self):
        paths=['output/pe-administrativo-aprovado-20270922/resultado-administrativo.json',
               'pe_layers_2027_source.json','output/desbloqueio-pe-2027/docencia-reconstruida.json',
               'output/pe-real-2027/reconciliacao-custos.json']
        self.inputs=[json.loads((ROOT/p).read_text(encoding='utf-8')) for p in paths]

    def test_unverified_legacy_amount_is_not_integral_cost(self):
        result=investigate(*self.inputs)
        self.assertEqual([c['partialKnownCents'] for c in result['classes']],[311329,256880,341529,315279])
        for c in result['classes']:
            self.assertIsNone(c['integralCostCents']);self.assertIsNone(c['missingActualCostCents'])
            self.assertIsNone(c['pe']);self.assertFalse(c['canClose'])

    def test_non_teachers_are_exposed_as_historical_conflict(self):
        c=investigate(*self.inputs)['classes'][-1]
        excluded=[t['name'] for t in c['teachers'] if t['currentTeacherExcluded']]
        self.assertEqual(excluded,['Lohana Rodrigues Leite da Silva','Marcelo Rodrigues'])
        self.assertEqual(c['teacherRoleConflictCents'],27414)
        lohana=next(t for t in c['teachers'] if t['name']==excluded[0])
        marcelo=next(t for t in c['teachers'] if t['name']==excluded[1])
        self.assertEqual(lohana['administrativeConfirmation']['role'],'Auxiliar administrativo')
        self.assertTrue(marcelo['administrativeConfirmation']['payrollMembershipConfirmed'])
        self.assertIsNone(marcelo['administrativeConfirmation']['role'])

    def test_no_mutation_or_reserve_reallocation(self):
        before=deepcopy(self.inputs);r=investigate(*self.inputs)
        self.assertEqual(before,self.inputs)
        self.assertTrue(r['reserveIncludedInSchoolEnvelope'])
        self.assertFalse(r['reserveIncludedInClassAllocation'])
        self.assertEqual(r['reserve']['costCents'],1582705)

    def test_teacher_component_mismatch_blocks_report(self):
        next(r for r in self.inputs[2]['classes'] if r['class_name']=='1º D')['weekly_cost']+=1
        with self.assertRaises(AssertionError):investigate(*self.inputs)

if __name__=='__main__':unittest.main()
