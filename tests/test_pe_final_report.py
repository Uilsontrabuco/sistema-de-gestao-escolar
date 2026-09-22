import json,unittest,io
from copy import deepcopy
from pathlib import Path
from pe_final_2027 import final_view,executive,diagnostic
from benefits_2027 import apply_benefit_view,import_benefits
from enrollment_2027 import apply_snapshot_to_state,project_current
from server import blank
from pe_real import AUDIT

class FinalReportTests(unittest.TestCase):
 def setUp(self):
  self.base=json.loads((AUDIT/'resultado.json').read_text(encoding='utf-8'))
  self.state=import_benefits(apply_snapshot_to_state(blank()),json.loads((AUDIT/'registros-saneados-locais.json').read_text(encoding='utf-8')))
  self.final=final_view(self.base,self.state)
 def test_g5_planning_and_documentary_values_separated(self):
  r=next(x for x in self.final['rows'] if x['name']=='G5 C')
  self.assertEqual((r['planningTuitionCents'],r['documentaryTuitionCents']),(96467,93069));self.assertEqual(r['ticketCents'],81070.8668);self.assertEqual(r['pe'],17)
 def test_eighth_ticket_not_cost_transfer(self):
  r=next(x for x in self.final['rows'] if x['name']=='8º C')
  self.assertEqual(r['ticketCents'],104193.6324);self.assertIsNone(r['pe']);self.assertIsNone(r['consideredCostCents'])
 def test_g2_and_39th_rules_preserved(self):
  for a,b in zip(self.base['rows'],self.final['rows']):
   if a['name'] not in ('G5 C','8º C'):self.assertEqual(a,b)
 def test_no_state_mutation_or_new_benefit(self):
  before=deepcopy(self.state);final_view(self.base,self.state);self.assertEqual(before,self.state)
 def test_sufficient_real_mix_replaces_assumption(self):
  b=deepcopy(self.base);r=next(x for x in b['rows'] if x['name']=='G5 C')
  r.update(plannedBenefitCount=14,currentRevenueComplete=True,plannedTicketCents=60000,ticketCents=60000)
  f=next(x for x in final_view(b,self.state)['rows'] if x['name']=='G5 C')
  self.assertNotIn('planningAssumption',f);self.assertEqual(f['ticketCents'],60000);self.assertEqual(f['pe'],23)
 def test_incomplete_mix_keeps_identified_premise(self):
  b=deepcopy(self.base);r=next(x for x in b['rows'] if x['name']=='G5 C');r.update(plannedBenefitCount=1,currentRevenueComplete=False,plannedTicketCents=60000)
  f=next(x for x in final_view(b,self.state)['rows'] if x['name']=='G5 C');self.assertEqual(f['ticketCents'],81070.8668)
 def test_idempotence_and_finite_json(self):
  self.assertEqual(self.final,final_view(self.final,self.state));json.dumps(self.final,allow_nan=False)
 def test_partial_consolidation_same_population(self):
  e=executive(self.final);self.assertEqual(e['comparableClasses'],37);self.assertEqual(e['result'],e['comparableRevenue']-e['cost']);self.assertEqual(e['peMissing'],4)
 def test_diagnostics_41_unique_with_real_distance(self):
  texts=[diagnostic(r) for r in self.final['rows']];self.assertEqual(len(set(texts)),41);self.assertIn('mais 2 matrículas',texts[0]);self.assertIn('20 matriculados',texts[34])
 def test_structure_correction_not_silently_deleting_students(self):
  self.assertIn('20 matriculados',self.final['structureNotice']);self.assertEqual(executive(self.final)['enrolled'],775)
 def test_pdf_complete_and_repeatable_template(self):
  from pe_executive_pdf import executive_pdf
  from pypdf import PdfReader
  data=executive_pdf(self.final);self.assertTrue(data.startswith(b'%PDF'))
  reader=PdfReader(io.BytesIO(data));text='\n'.join(p.extract_text() for p in reader.pages)
  self.assertEqual(len(reader.pages),49)
  for r in self.final['rows']:self.assertIn(r['name']+' - Diagnóstico financeiro',text)
  self.assertIn('ESTRUTURA EM REVISÃO',text);self.assertIn('R$ 810,71',text)

 def test_pdf_http_requires_financial_permission_and_is_read_only(self):
  import tempfile,threading,urllib.request,urllib.error,http.cookiejar
  from server import serve
  with tempfile.TemporaryDirectory() as tmp:
   app=serve(Path(tmp)/'fixture.sqlite3',port=0);admin=app.store.create_user('PDF fixture','pdf@fixture.invalid','PDF-fixture-only-2027',is_admin=True)
   thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start();url='http://127.0.0.1:'+str(app.server_port)
   client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
   try:
    with self.assertRaises(urllib.error.HTTPError):client.open(url+'/api/break-even/report.pdf')
    client.open(urllib.request.Request(url+'/api/login',data=json.dumps(dict(email='pdf@fixture.invalid',password='PDF-fixture-only-2027')).encode(),headers={'Content-Type':'application/json'})).close()
    before=app.store.state()
    with client.open(url+'/api/break-even/report.pdf') as response:self.assertTrue(response.read().startswith(b'%PDF'))
    self.assertEqual(app.store.state(),before)
    app.store.create_user('Sem financeiro','pdf-no@fixture.invalid','PDF-fixture-only-2027',{'classes':['view']},actor=admin)
    client.open(urllib.request.Request(url+'/api/login',data=json.dumps(dict(email='pdf-no@fixture.invalid',password='PDF-fixture-only-2027')).encode(),headers={'Content-Type':'application/json'})).close()
    with self.assertRaises(urllib.error.HTTPError):client.open(url+'/api/break-even/report.pdf')
   finally:app.shutdown();app.server_close();thread.join()

 def test_future_registered_mix_updates_memory_and_pdf(self):
  s=deepcopy(self.state);c=next(c for c in s['classes'] if c['name']=='G5 C');c['benefitMix2027Confirmed']=True
  b=deepcopy(s['benefits'][0]);b.update(id='future-g5-fixture',classId=c['id'],grossCents=93069,discountCents=33069,rate=str(33069/93069));s['benefits'].append(b)
  d=final_view(apply_benefit_view(self.base,s),s);r=next(r for r in d['rows'] if r['name']=='G5 C')
  self.assertNotIn('planningAssumption',r);self.assertEqual(r['acceptedStudentCount'],1);self.assertEqual(r['ticketCents'],57300);self.assertEqual(r['averageFinancialDiscountCents'],33069)
  from pe_executive_pdf import executive_pdf
  self.assertTrue(executive_pdf(d).startswith(b'%PDF'))

if __name__=='__main__':unittest.main()
