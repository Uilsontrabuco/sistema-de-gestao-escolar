import json
import unittest
from decimal import Decimal
from scripts.audit_documentary_41_pe import build, OUT, report, parse_financial, revenue_bridge


class Documentary41AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit=build()
        cls.rows=cls.audit['rows']
        cls.source=json.loads((OUT/'fontes.json').read_text(encoding='utf-8'))

    def test_exact_current_universe_is_preserved(self):
        self.assertEqual(len(self.rows),41)
        self.assertEqual(len({r['name'] for r in self.rows}),41)
        self.assertEqual(sum(r['currentCapacity'] for r in self.rows),1103)
        self.assertEqual(sum(r['currentPE'] for r in self.rows),831)

    def test_all_48_original_rows_and_printed_pe_are_reproduced(self):
        source=self.audit['sourceRows']
        self.assertEqual(len(source),48)
        for row in source:
            self.assertEqual(row['reconstructedDisplayedPE'],row['pe'],row['sourceName'])

    def test_capacity_column_is_unknown_not_forecast_students(self):
        for r in self.rows:
            self.assertIsNone(r['documentCapacity'])
            if r['document']:
                self.assertIsNone(r['document']['capacity'])
        for word in self.source['capacityColumnEvidence']:
            if word['text'].isdigit():
                self.assertEqual(word['text'],'0')
                self.assertTrue('Subtotal' in word['line'] or 'TOTAL' in word['line'])

    def test_historical_formula_evidence_is_marked_2024(self):
        self.assertEqual(self.source['historicalWorkbookYear'],2024)
        self.assertFalse(self.source['original2027WorkbookAvailable'])
        self.assertEqual(len(self.source['historicalPEFormulas']),48)
        for i,c in enumerate(self.source['historicalPEFormulas'],7):
            self.assertEqual(c['formula'],f'=IFERROR(B{i}/H{i}*M{i},0)')
            self.assertEqual(c['numberFormat'],'0')

    def test_missing_d_classes_are_not_zero_or_allocated_from_c(self):
        missing=[r for r in self.rows if r['document'] is None]
        self.assertEqual([r['name'] for r in missing],['1º D','2º D','3º D'])
        for r in missing:
            self.assertIsNone(r['documentaryPE'])
            self.assertIsNone(r['costDifference'])
            self.assertIsNone(r['revenueBridge'])
            self.assertIsNone(r['peDifference'])

    def test_inactive_8c_has_printed_zero_but_no_definitive_conclusion(self):
        r=next(r for r in self.rows if r['name']=='8º C')
        self.assertEqual(r['documentaryPE'],0)
        self.assertEqual(r['document']['students'],0)
        self.assertIsNone(r['document']['ratio'])
        self.assertEqual(r['currentPE'],17)
        self.assertEqual(r['status'],'E')
        self.assertIsNone(r['newDefinitivePE'])

    def test_g2_conclusion_and_cost_bridge_are_unchanged(self):
        for r in self.rows[:2]:
            self.assertEqual(r['g2ConclusionPreserved'],dict(documentary=15,provisional=22,certifiedNewPE=None))
            self.assertEqual(r['costDifference'],Decimal('5178.48'))
            self.assertEqual(r['document']['totalCost'],Decimal('13543.09'))

    def test_every_revenue_bridge_closes_with_distinct_capacity_effect(self):
        for r in self.rows:
            if not r['document']: continue
            b=r['revenueBridge']; p=r['document']; c=r['current']
            self.assertEqual(b['start']+sum(b['parts'].values()),b['end'])
            self.assertEqual(b['currentAtDocumentaryStudents']+b['parts']['forecastToCapacity'],b['end'])
            self.assertEqual(b['parts']['removeDocumentaryFreeTuition'],p['freeTuition'])
            self.assertEqual(b['parts']['removeInstitutionalRevenue'],-p['otherRevenue'])

    def test_every_cost_bridge_closes_without_double_adding_institutional(self):
        for r in self.rows:
            self.assertEqual(sum(r['currentComponents'].values()),Decimal(str(r['current']['totalCostMonthly'])))
            if not r['document']: continue
            b=r['costBridge']
            self.assertEqual(b['start']+sum(b['parts'].values()),b['end'])
            self.assertNotIn('institutionalIncludedInPersonnel',b['parts'])
            self.assertGreater(b['institutionalIncludedInPersonnel'],0)

    def test_printed_benefit_breakdown_matches_summary_with_cent_precision(self):
        for p in self.audit['sourceRows']:
            detail=p['studentFinancials']
            benefits=sum(detail[k] for k in ('freePartial','freeFull','collectivePartial','collectiveFull'))
            self.assertLessEqual(abs(benefits-p['freeTuition']),Decimal('.02'),p['sourceName'])
            self.assertLessEqual(abs(detail['netRevenue']+p['otherRevenue']-p['netRevenue']),Decimal('.02'),p['sourceName'])

    def test_sums_use_same_38_class_universe(self):
        s=self.audit['summary']
        self.assertEqual((s['mappedClasses'],s['mappedDocumentaryPESum'],s['mappedCurrentPESum'],s['mappedDifference']),(38,967,777,-190))
        self.assertIsNone(s['all41DocumentaryPESum'])
        self.assertIsNone(s['all41ComparableDifference'])
        excluded=next(p for p in self.audit['excludedSourceRows'] if p['sourceName']=='7º Ano C')
        self.assertEqual(excluded['pe'],34)
        self.assertEqual(s['sourceDisplayedPESum']-excluded['pe'],s['mappedDocumentaryPESum'])

    def test_rounding_of_sum_is_not_sum_of_displayed_pe(self):
        s=self.audit['summary']
        self.assertEqual(s['sourceDisplayedPESum'],1001)
        self.assertEqual(s['sourceQuotientSum'].quantize(Decimal('1')),Decimal(1000))
        self.assertEqual(s['sourceSumDisplayedCosts']-s['sourcePrintedTotalCost'],Decimal('.04'))
        self.assertEqual(s['sourceDisplayedBelowCoveringInteger'],17)

    def test_equal_integer_does_not_claim_integral_reproduction(self):
        matched=[r for r in self.rows if r['peDifference']==0]
        self.assertEqual([r['name'] for r in matched],['1º C'])
        self.assertNotEqual(matched[0]['costDifference'],0)
        self.assertEqual(matched[0]['status'],'E')
        for r in self.rows:
            self.assertIsNone(r['newDefinitivePE'])
            self.assertFalse(r['provenDuplicate'])

    def test_full_table_has_41_rows_and_all_required_columns(self):
        text=report(self.audit)
        table=text.split('| TURMA |',1)[1].split('## Resultado',1)[0]
        body=[line for line in table.splitlines() if line.startswith('| ') and not line.startswith('|---')]
        self.assertEqual(len(body),41)
        self.assertIn('RECEITA DOCUMENTAL',text)
        self.assertIn('CAUSA DA DIFERENÇA',text)
        self.assertIn('D comprovada: zero',text)

    def test_negative_unmapped_benefits_are_preserved_not_absorbed(self):
        p=next(p for p in self.audit['excludedSourceRows'] if p['sourceName']=='3º E. Médio B')
        self.assertEqual(p['students'],0)
        self.assertEqual(p['netRevenue'],Decimal('-9474.89'))
        self.assertEqual(p['studentFinancials']['delinquency'],Decimal('-294.88'))
        em=next(r for r in self.rows if r['name']=='3º EM')
        self.assertEqual(em['mappedSource'],'3º E. Médio A')


if __name__=='__main__': unittest.main()
