import json
import unittest
from copy import deepcopy
from decimal import Decimal
from pe_real import AUDIT, calculate, money, ceil_ratio, build_layers
from enrollment_2027 import project_current
from scripts.sanitize_pe_real import sanitize_records, financial_ledger, normalized_label
from scripts.reconcile_pe_real_costs import apply_costs, reconcile


class SanitationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=json.loads((AUDIT/'registros-locais.json').read_text(encoding='utf-8'))
        cls.research=json.loads((AUDIT/'pesquisa-saneamento.json').read_text(encoding='utf-8'))
        cls.records,cls.resolutions=sanitize_records(cls.original,cls.research)
        cls.report=json.loads((AUDIT/'resultado.json').read_text(encoding='utf-8'))

    def test_all_41_memories_reproduce(self):
        d=calculate(self.records,allow_partial_mix=True);d['sanitation']={"enabled":True}
        d=project_current(apply_costs(d,reconcile()))
        from benefits_2027 import apply_benefit_view, import_benefits
        from enrollment_2027 import apply_snapshot_to_state
        from server import blank
        d=apply_benefit_view(d,import_benefits(apply_snapshot_to_state(blank()),self.records))
        for a,b in zip(d['rows'],self.report['rows']):
            for key in ('pe','ticketCents','consideredCostCents','netRevenueCents','discountCents','distanceToPE','projectedRevenueCents','projectedResultCents'):
                self.assertEqual(a[key],b[key],(a['name'],key))

    def test_controls_and_negative_vacancies(self):
        e=self.report['enrollmentSummary']
        self.assertEqual([e[k] for k in ('capacity','enrolled','new','re','vacancies')],[1103,775,37,738,328])
        self.assertEqual(len(self.report['rows']),41)
        self.assertEqual(sorted(r['vacancies'] for r in self.report['rows'] if r['vacancies']<0),[-18,-7,-6,-2,-2])

    def test_marcando_vidas_45_once(self):
        for n in (275,276):
            r=next(r for r in self.records if r['sourceRow']==n)
            self.assertEqual(r['rate'],'0.45')
            self.assertEqual(r['discountCents'],money(Decimal(r['grossCents'])*Decimal('.45')))
            self.assertEqual(r['postDiscountCents'],53057)

    def test_philanthropic_50_once(self):
        r=next(r for r in self.records if r['sourceRow']==697)
        self.assertEqual(r['rate'],'0.5');self.assertEqual(r['discountCents'],61991)
        self.assertTrue(r['benefitValid']);self.assertIsNone(r['classId'])

    def test_combination_is_individual_not_general_addition(self):
        r=next(r for r in self.records if r['sourceRow']==482)
        self.assertEqual(r['rate'],'0.95');self.assertEqual(r['discountCents'],91644)
        self.assertEqual(r['postDiscountCents'],4823)
        x=next(x for x in self.resolutions if x['row']==482)
        self.assertEqual(x['historicalChargedCents'],4425)
        self.assertEqual(money(Decimal(x['historicalTuitionCents'])*Decimal('.05')),4425)

    def test_no_second_progression_or_transfer(self):
        for a,b in zip(self.original,self.records):
            self.assertEqual(a['sourceClass'],b['sourceClass']);self.assertEqual(a['classId'],b['classId'])
        self.assertEqual(sum(r['classId'] is None for r in self.records),114)
        self.assertEqual(normalized_label('EFUND04TD'),'4º D')
        self.assertEqual(normalized_label('EMERE01MB'),'1º EM B')

    def test_no_change_to_source_records(self):
        before=deepcopy(self.original)
        sanitize_records(self.original,self.research)
        self.assertEqual(before,self.original)

    def test_four_resolved_and_no_duplicate_students(self):
        self.assertEqual(len(self.resolutions),4)
        self.assertEqual(len({r['studentKey'] for r in self.records}),1016)
        self.assertTrue(all(r['benefitValid'] for r in self.records))

    def test_partial_mix_does_not_block_whole_class(self):
        records=deepcopy(self.records)
        x=next(r for r in records if r['sourceRow']==275)
        x['valid']=False;x['issues']=['CONFLITO FIXTURE']
        r=next(r for r in calculate(records,allow_partial_mix=True)['rows'] if r['name']=='3º A')
        self.assertIsNotNone(r['pe']);self.assertFalse(r['completeMix']);self.assertTrue(r['partialMixAuthorized'])

    def test_financial_classification_closes_to_cent(self):
        x=financial_ledger(reconcile())
        self.assertEqual(sum(e['cents'] for e in x['entries']),62320836)
        self.assertEqual(x['totals'],dict(A=0,B=0,C=17790108,D=42948023,E=1582705))

    def test_pcld_and_discount_no_second_incidence(self):
        self.assertEqual(self.report['summary']['pcldExpenseCents'],0)
        self.assertEqual(self.report['summary']['structuralDiscountPercent'],0)
        for r in self.report['rows']:
            if r.get('costBridge'):
                b=r['costBridge'];self.assertEqual(r['consideredCostCents'],b['payrollCents']+b['supportCents']+b['generalCents']-b['pcldRemovedCents']-b['discountReclassifiedCents'])
            if r['acceptedStudentCount']:
                self.assertEqual(r['netRevenueCents'],money(Decimal(r['postDiscountCents'])*Decimal('.955')))

    def test_individual_discount_totals(self):
        self.assertEqual(sum(r['discountCents'] for r in self.records),41836995)
        self.assertEqual(sum(r['discountCents'] for r in self.records if r['valid']),34487669)

    def test_pe_independent_of_enrollment(self):
        from enrollment_2027 import snapshot
        snap=snapshot();snap['rows'][2]['students']=0
        d=project_current(self.report,data=snap)
        self.assertEqual([r['pe'] for r in d['rows']],[r['pe'] for r in self.report['rows']])
        self.assertEqual([r['consideredCostCents'] for r in d['rows']],[r['consideredCostCents'] for r in self.report['rows']])

    def test_g2_reproducible_without_fabricated_mix(self):
        for r in self.report['rows'][:2]:
            self.assertEqual(r['consideredCostCents'],1075530);self.assertEqual(r['pe'],14)
            self.assertEqual(r['historicalDocumentaryPE'],15)
            self.assertEqual(ceil_ratio(1075530*1000,93069*955),13)

    def test_personnel_total_and_single_replacement(self):
        self.assertEqual(sum(g['cents'] for g in self.report['sanitation']['personnelGroups'].values()),38759193)
        people=self.report['costReconciliation']['historicalPayroll']
        self.assertEqual(sum('Jailane' in p['person'] for p in people),1)
        self.assertEqual(sum('Romilton' in p['person'] for p in people),0)
        self.assertEqual(sum(a['payrollCents']+a['supportCents'] for a in self.report['costReconciliation']['allocations']),38759193)

    def test_teachers_and_historical_layers_unchanged(self):
        layers=build_layers()
        self.assertEqual(sum(c['cents'] for r in layers['rows'] for c in r['managerial']['costs'] if c['kind']=='docentes'),12267300)

    def test_status_vocabulary_and_no_final_claim(self):
        self.assertEqual(set(r['status'] for r in self.report['rows']),{'PARCIALMENTE COMPROVADO','EM AUDITORIA'})
        self.assertEqual(self.report['summary']['partial'],36)
        self.assertFalse(self.report['definitivelyClosed'])


if __name__=='__main__':unittest.main()
