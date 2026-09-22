import unittest
import json
from copy import deepcopy
from decimal import Decimal
from pe_real import import_rows, calculate, benefit_rate, class_key, AUDIT
from pe_layers import build_layers


class RealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records=json.loads((AUDIT/'registros-locais.json').read_text(encoding='utf-8'))
        cls.result=calculate(cls.records)

    def fixture(self, code='EINFA02MA', rate=.2, label='_Sem Bolsa', grant=None):
        return import_rows([['CAJ','Educ Inf 2 anos',code,'Aluno teste',label,grant,rate]],'fixture')

    def test_41_1103(self):
        self.assertEqual(len(self.result['rows']),41)
        self.assertEqual(self.result['summary']['capacity'],1103)

    def test_no_second_progression(self):
        self.assertEqual(class_key('EINFA03MA'),'caj-2027-caj-g3-a')
        self.assertEqual(self.records[0]['sourceClass'],'EINFA03MA')
        self.assertEqual(self.records[0]['classId'],'caj-2027-caj-g3-a')

    def test_no_class_letter_collapse(self):
        self.assertIsNone(class_key('EMERE01MB'))
        self.assertEqual(self.result['summary']['unmappedRecords'],114)

    def test_g2_without_mix_is_unknown(self):
        for r in self.result['rows'][:2]:
            self.assertIsNone(r['pe']);self.assertIsNone(r['ticketCents'])
            self.assertEqual(r['historicalDocumentaryPE'],15)
            self.assertEqual(r['historicalProvisionalPE'],22)

    def test_conflict_excludes_whole_class_pe(self):
        r=next(r for r in self.result['rows'] if r['name']=='3º A')
        self.assertIsNone(r['pe']);self.assertEqual(len(r['issues']),2)

    def test_duplicate_detection(self):
        rows=[['CAJ','Educ Inf 2 anos','EINFA02MA','Aluno','_Sem Bolsa',None,.2]]*2
        records=import_rows(rows,'fixture')
        self.assertTrue(all(not r['valid'] for r in records))

    def test_integral_gratuity(self):
        records=self.fixture(rate=1,label='CEBAS - Ebolsa',grant='100')
        self.assertTrue(records[0]['valid']);self.assertEqual(records[0]['postDiscountCents'],0)
        r=calculate(records)['rows'][0]
        self.assertEqual(r['netRevenueCents'],0);self.assertIsNone(r['pe'])

    def test_rates_not_rounded_to_categories(self):
        value=.1500046847184484
        r=self.fixture(rate=value)[0]
        self.assertEqual(r['rate'],str(value))

    def test_equal_grant_not_added_twice(self):
        r=self.fixture(rate=.5,label='CEBAS - Ebolsa',grant='50')[0]
        self.assertEqual(r['discountCents'],46535)
        self.assertEqual(r['postDiscountCents'],46534)

    def test_conflicting_grants_unknown(self):
        for grant,rate in [('50',.45),('45',1),('50 | 45',.95)]:
            self.assertIsNone(benefit_rate('Bolsa',grant,rate)[0])

    def test_invalid_or_missing_percent(self):
        for rate in [None, -1, 1.01, float('nan'),float('inf'),True]:
            self.assertIsNone(benefit_rate('_Sem Bolsa',None,rate)[0])

    def test_missing_benefit_not_zero(self):
        self.assertIsNone(benefit_rate(None,None,0)[0])

    def test_series_divergence(self):
        r=self.fixture(code='EINFA03MA')[0]
        self.assertFalse(r['valid'])

    def test_individual_rounding_then_delinquency_once(self):
        r=calculate(self.fixture())['rows'][0]
        self.assertEqual(r['postDiscountCents'],74455)
        self.assertEqual(r['netRevenueCents'],71105)
        self.assertEqual(r['delinquencyCents'],3350)

    def test_proportional_mix_not_enrollment_target(self):
        records=self.fixture(rate=0)
        a=calculate(records)['rows'][0]['pe']
        second=deepcopy(records[0]);second['studentKey']='OUTRO';second['economicEventId']='outro'
        self.assertEqual(a,calculate(records+[second])['rows'][0]['pe'])

    def test_capacity_does_not_change_pe(self):
        layers=build_layers();a=calculate(self.fixture(),layers)['rows'][0]
        layers['rows'][0]['capacity']=1
        b=calculate(self.fixture(),layers)['rows'][0]
        self.assertEqual(a['pe'],b['pe']);self.assertNotEqual(a['physicalMargin'],b['physicalMargin'])
        self.assertFalse(b['physicallyInfeasible'])

    def test_pending_not_in_pe(self):
        layers=build_layers();a=calculate(self.fixture(),layers)['rows'][0]
        layers['rows'][0]['pendingCosts']['knownCents']+=1000000
        b=calculate(self.fixture(),layers)['rows'][0]
        self.assertEqual(a['pe'],b['pe'])

    def test_cost_components_close(self):
        for r in self.result['rows']:
            self.assertEqual(sum(c['cents'] for c in r['costs']),r['verifiedCostCents'])
            self.assertEqual(sum(c['cents'] for c in r['pendingCosts']),r['pendingCostCents'])
        self.assertEqual(self.result['summary']['verifiedCostCents']+self.result['summary']['pendingCostCents'],79936916)

    def test_financial_events_cannot_duplicate(self):
        records=self.fixture();second=deepcopy(records[0]);second['studentKey']='OUTRO'
        with self.assertRaises(ValueError):calculate(records+[second])

    def test_no_pcld_or_structural_discount_added(self):
        self.assertEqual(self.result['summary']['pcldExpenseCents'],0)
        self.assertEqual(self.result['summary']['structuralDiscountPercent'],0)

    def test_repeatable_no_mutation(self):
        before=deepcopy(self.records)
        self.assertEqual(calculate(self.records),self.result)
        self.assertEqual(before,self.records)

    def test_documentary_and_teachers_preserved(self):
        layers=build_layers()
        self.assertEqual(sum(c['cents'] for r in layers['rows'] for c in r['managerial']['costs'] if c['kind']=='docentes'),12267300)
        self.assertEqual(layers['rows'][0]['documentary']['pe'],15)

    def test_missing_cost_and_confidence_not_zero(self):
        for r in self.result['rows']:
            self.assertIsNone(r['otherDirectCents']);self.assertIsNone(r['peConfidencePercent'])
        self.assertEqual(self.result['summary']['confirmed'],0)


if __name__=='__main__':unittest.main()
