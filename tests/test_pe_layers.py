import copy
import json
import unittest
from pe_layers import build_layers, SOURCE, metrics, project_real, validate_recognition, ticket_cents


class PELayersTests(unittest.TestCase):
    def setUp(self):
        self.source=json.loads(SOURCE.read_text(encoding='utf-8'));self.data=build_layers(self.source)

    def test_manifest_and_capacity(self):
        self.assertEqual((len(self.data['rows']),self.data['summary']['capacity']),(41,1103))

    def test_g2_three_distinct_values(self):
        for r in self.data['rows'][:2]:
            self.assertEqual((r['documentary']['pe'],r['documentary']['printedPE'],r['managerial']['pe'],r['provisional']['pe']),(15,15,7,22))

    def test_pending_excluded_and_amounts_reconcile(self):
        for r in self.data['rows']:
            self.assertEqual(r['managerial']['costCents']+r['pendingCosts']['knownCents'],r['provisional']['costCents'])
            self.assertFalse(any(p['verified'] for p in r['pendingCosts']['items']))
        self.assertEqual(self.data['summary']['verifiedMonthlyCents'],17616080)
        self.assertEqual(self.data['summary']['pendingKnownMonthlyCents'],62320836)

    def test_pending_increase_never_changes_verified_pe(self):
        self.source['rows'][0]['components'][-1]['cents']+=1000000
        changed=build_layers(self.source)['rows'][0]
        self.assertEqual(changed['managerial'],self.data['rows'][0]['managerial'])
        self.assertGreater(changed['provisional']['pe'],22)

    def test_duplicate_cost_rejected(self):
        self.source['rows'][0]['components'].append(copy.deepcopy(self.source['rows'][0]['components'][0]))
        with self.assertRaises(ValueError):build_layers(self.source)

    def test_duplicate_rateio_cannot_hide_under_new_id(self):
        part=copy.deepcopy(self.source['rows'][0]['components'][-2]);part['id']+='-duplicate'
        self.source['rows'][0]['components'].append(part)
        with self.assertRaises(ValueError):build_layers(self.source)

    def test_residual_cannot_be_promoted_without_evidence(self):
        self.source['rows'][0]['components'][-1]['verified']=True
        with self.assertRaises(ValueError):build_layers(self.source)

    def test_capacity_does_not_change_cost_or_pe(self):
        capacities={r['id']:r['capacity']+10 for r in self.source['rows']}
        changed=build_layers(self.source,capacities)
        for old,new in zip(self.data['rows'],changed['rows']):
            self.assertEqual(old['managerial']['pe'],new['managerial']['pe'])
            self.assertEqual(old['managerial']['costCents'],new['managerial']['costCents'])
            self.assertEqual(new['managerial']['physicalMargin']-old['managerial']['physicalMargin'],10)

    def test_enrollments_never_enter_structural_formula(self):
        for r in self.source['rows']:r['students']=99999
        self.assertEqual(build_layers(self.source),self.data)

    def test_only_proven_pe_can_signal_infeasibility(self):
        r=self.data['rows'][0]
        self.assertTrue(r['provisional']['aboveCapacityWarning'])
        self.assertIsNone(r['provisional']['physicalStatus'])
        self.assertIsNone(r['managerial']['physicalStatus'])
        self.assertEqual(metrics(20000,1000,10)['physicalStatus'],'INVIÁVEL FISICAMENTE')

    def test_unknown_is_not_zero(self):
        r=next(r for r in self.data['rows'] if r['name']=='G3 B')
        self.assertIsNone(r['pendingCosts']['unknownItems'][0]['cents'])
        self.assertFalse(r['pendingCosts']['completeAmount'])
        self.assertIsNone(metrics(None,1000,10)['pe'])

    def test_missing_document_never_copies_other_class(self):
        for name in ('1º D','2º D','3º D','8º C'):
            d=next(r['documentary'] for r in self.data['rows'] if r['name']==name)
            self.assertIsNone(d['pe']);self.assertEqual(d['status'],'SEM CORRESPONDÊNCIA')

    def test_printed_values_preserved_alongside_requested_ceiling(self):
        rows=[r for r in self.data['rows'] if r['documentary'].get('roundingDifference')]
        self.assertEqual(len(rows),17)
        self.assertTrue(all(r['documentary']['status']=='PENDENTE DOCUMENTAL' for r in rows))
        self.assertEqual(self.data['summary']['printedDocumentaryConfirmed'],37)

    def test_pcld_not_in_management(self):
        self.assertEqual(self.data['pcld']['managementIncludedCents'],0)
        self.assertEqual(sum(r['historicalPCLDNeutralizedCents'] for r in self.source['rows']),4211780)
        self.source['pcld']['managementIncludedCents']=4211780
        with self.assertRaises(ValueError):build_layers(self.source)

    def test_pcld_expense_rejected_with_delinquency(self):
        with self.assertRaises(ValueError):validate_recognition([dict(economicEventId='loss',kind='pcld',side='expense')])

    def test_same_benefit_cannot_hit_three_places(self):
        with self.assertRaises(ValueError):validate_recognition([dict(economicEventId='benefit-1',kind='discount',side=side) for side in ('expense','ticket','student')])

    def test_institutional_income_requires_management_evidence(self):
        self.assertTrue(all(r['managerial']['institutionalRevenueIncludedCents']==0 for r in self.data['rows']))
        self.source['institutionalRevenue']['availableForManagement']=True
        with self.assertRaises(ValueError):build_layers(self.source)

    def test_shared_verified_allocations_close_exactly(self):
        for kind in ('auxiliares-segmento','coordenacao-segmento'):
            a=sum(p['cents'] for r in self.source['rows'] for p in r['components'] if p['kind']==kind)
            b=sum(p['cents'] for r in self.data['rows'] for p in r['managerial']['costs'] if p['kind']==kind)
            self.assertEqual(a,b)

    def test_real_projection_not_loaded(self):
        for row in project_real(self.data):
            self.assertIsNone(row['studentCount']);self.assertIsNone(row['revenueCents'])

    def test_real_import_contract_blocks_unreconciled_coverage(self):
        with self.assertRaises(ValueError):project_real(self.data,[],complete=True)

    def test_real_discount_replaces_structural_discount(self):
        before=copy.deepcopy(self.data);r=self.data['rows'][0]
        student=dict(studentId='fixture',classId=r['id'],benefits=[dict(economicEventId='fixture-discount',discountCents=10000)])
        result=project_real(self.data,[student],complete=True,coverage=dict(status='RECONCILIADA',source='FICTÍCIO — TESTE'))
        self.assertEqual(result[0]['revenueCents'],79331)
        self.assertEqual(result[0]['discountImpactCents'],10000)
        self.assertEqual(self.data,before)
        self.assertEqual(result[0]['structuralPE'],7)

    def test_real_same_benefit_as_expense_blocked(self):
        r=self.data['rows'][0];s=dict(studentId='fixture',classId=r['id'],benefits=[dict(economicEventId='x',discountCents=100)])
        with self.assertRaises(ValueError):project_real(self.data,[s],complete=True,coverage=dict(status='RECONCILIADA',source='fixture'),recognitions=[dict(economicEventId='x',side='expense',kind='discount')])

    def test_official_tuitions(self):
        self.assertEqual({r['tuitionCents'] for r in self.data['rows']},{93069,96467,123981,142559,146105})
        self.assertEqual(ticket_cents(93069),86214)

    def test_no_closure_claim_with_pending_costs(self):
        self.assertFalse(self.data['definitivelyClosed'])
        self.assertEqual(self.data['summary']['managerialCompletelyClosed'],0)

    def test_teacher_identity_and_total_remain_homologated(self):
        from scripts.generate_approved_pe_2027_preview import teacher_projection_2027
        people=teacher_projection_2027()
        self.assertEqual(len(people),50)
        self.assertEqual(len({p['name'] for p in people}),50)
        self.assertFalse(any(p['name'].startswith(('Lohana ','Marcelo ')) for p in people))
        self.assertTrue(any(p['name'].startswith('Telma ') for p in people))
        self.assertTrue(any(p['name'].startswith('Julianne ') for p in people))
        self.assertEqual(sum(p['cents'] for r in self.data['rows'] for p in r['managerial']['costs'] if p['kind']=='docentes'),12267300)


if __name__=='__main__':unittest.main()
