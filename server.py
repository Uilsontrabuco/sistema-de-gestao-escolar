"""Servidor CAJ: SQLite, sessões revogáveis, ACL, auditoria e eventos SSE.
Inicialização: python server.py --create-admin; python server.py
Não cria usuários ou dados de demonstração. Para publicar, usar proxy HTTPS.
"""
import argparse, base64, copy, getpass, hashlib, hmac, json, os, secrets, sqlite3, threading, time, unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT=Path(__file__).resolve().parent
BACKEND_REVISION='finance-state-patch-20260911.2'
MODULES=['dashboard','enrollments','classes','benefits','requests','budget','delinquency','guardians','users','reports','tasks','team','financial']
MUTABLE={'meta','classes','enrollments','benefits','requests','budget','delinquency','guardians','tasks','imports','classificationRules','reviewQueue','academicYears','activeAcademicYear','academicDataYear','breakEven','revenuePlanning','teachingLoad'}
FINANCIAL_SEGMENTS=[('early','Educação Infantil'),('fundamental1','Fundamental I'),('fundamental2','Fundamental II'),('secondary12','1º e 2º ano do Ensino Médio'),('secondary3','3º ano do Ensino Médio')]
FINANCIAL_CATEGORIES=[('noDiscount','Sem desconto',0),('philanthropic100','Bolsa filantrópica',100),('philanthropic50','Bolsa filantrópica',50),('staffChild100','Filho de funcionário',100),('staffChild80','Filho de funcionário',80),('workerChild100','Filho de obreiro',100),('markingLives45','Projeto Marcando Vidas',45)]
from teaching_cost import load_documentary_costs
from financial_integration import integration_snapshot
INITIAL_TUITION={'early':930.69,'fundamental1':964.67,'fundamental2':1239.81,'secondary12':1425.59,'secondary3':1461.05}
PERSONNEL_COST_AUDIT_2027={
    'source':'Orçamento 2027',
    'status':'source_verified',
    'includedInOfficialTotalExpenses':True,
    'allocationStatus':'not_allocated_to_teachers_or_classes',
    'totalMonthly':387591.93,
    'payrollMonthly':348494.61,
    'personalChargesAndBenefitsMonthly':10185.22,
    'nonEmployeeServicesMonthly':28912.10,
    'notes':'Composição auditável do custo total de pessoal; já incluída nas despesas oficiais e sem rateio por professor ou turma.'
}
LEGACY_CORE_CLASSES=['G2','G3','G4','G5','1º Ano','2º Ano','3º Ano','4º Ano','5º Ano','6º Ano','7º Ano','8º Ano','9º Ano','1º Ano do Ensino Médio','2º Ano do Ensino Médio','3º Ano do Ensino Médio']
REPORT_2027_ROWS=[
('Educação Infantil','G2 A',18,9,9),('Educação Infantil','G2 B',18,0,0),('Educação Infantil','G3 A',24,17,2),('Educação Infantil','G3 B',24,16,4),('Educação Infantil','G4 A',25,30,3),('Educação Infantil','G4 B',26,16,0),('Educação Infantil','G5 A',21,22,1),('Educação Infantil','G5 B',18,0,0),('Educação Infantil','G5 C',22,14,2),
('Fundamental Anos Iniciais','1º A',25,18,0),('Fundamental Anos Iniciais','1º B',19,17,3),('Fundamental Anos Iniciais','1º C',25,12,0),('Fundamental Anos Iniciais','1º D',19,8,1),('Fundamental Anos Iniciais','2º A',24,18,0),('Fundamental Anos Iniciais','2º B',19,11,0),('Fundamental Anos Iniciais','2º C',19,10,0),('Fundamental Anos Iniciais','2º D',24,5,1),('Fundamental Anos Iniciais','3º A',25,17,0),('Fundamental Anos Iniciais','3º B',25,16,0),('Fundamental Anos Iniciais','3º C',25,9,0),('Fundamental Anos Iniciais','3º D',25,11,0),('Fundamental Anos Iniciais','4º A',35,17,0),('Fundamental Anos Iniciais','4º B',15,18,1),('Fundamental Anos Iniciais','4º C',35,20,0),('Fundamental Anos Iniciais','5º A',30,26,0),('Fundamental Anos Iniciais','5º B',27,13,0),('Fundamental Anos Iniciais','5º C',30,12,0),
('Fundamental Anos Finais','6º A',35,12,0),('Fundamental Anos Finais','6º B',26,16,0),('Fundamental Anos Finais','6º C',35,16,0),('Fundamental Anos Finais','7º A',30,43,0),('Fundamental Anos Finais','7º B',30,6,0),('Fundamental Anos Finais','8º A',35,19,0),('Fundamental Anos Finais','8º B',28,0,0),('Fundamental Anos Finais','8º C',28,9,0),('Fundamental Anos Finais','9º A',30,12,0),('Fundamental Anos Finais','9º B',28,9,0),('Fundamental Anos Finais','9º C',30,8,0),
('Ensino Médio','1º EM',48,40,0),('Ensino Médio','2º EM',43,25,0),('Ensino Médio','3º EM',35,27,0)]
def now():return datetime.now(timezone.utc).isoformat()
def fold(value):return ''.join(c for c in unicodedata.normalize('NFD',str(value)) if unicodedata.category(c)!='Mn').lower().strip()
def class_id(name):return 'caj-2027-caj-'+'-'.join(part for part in ''.join(c if ('a'<=c<='z' or '0'<=c<='9') else '-' for c in fold(name)).split('-') if part)
def report_classes():return [dict(id=class_id(name),name=name,stage=stage,capacity=capacity,opening={'new':fresh,'re':students-fresh},unclassified=0,students=students,template=False,source='Matrículas 2027 CAJ') for stage,name,capacity,students,fresh in REPORT_2027_ROWS]
def default_financial_year(year,seed=False):return {'id':str(year),'year':year,'parameters':[{'id':uid,'label':label,'tuition':INITIAL_TUITION[uid] if seed else None} for uid,label in FINANCIAL_SEGMENTS],'classifications':{}}
def ensure_financial_years(s):
    years=s.setdefault('academicYears',[])
    if not any(x.get('year')==2027 for x in years):years.append(default_financial_year(2027,True))
    for y in years:
        y['id']=str(y.get('id',y.get('year')));y['year']=int(y['year']);y.setdefault('parameters',default_financial_year(y['year'])['parameters']);y.setdefault('classifications',{})
        for p in y['parameters']:
            p['label']=dict(FINANCIAL_SEGMENTS).get(p['id'],p.get('label',''));p['tuition']=None if p.get('tuition') in ('',None) else float(p['tuition'])
    s.setdefault('academicDataYear',2027);s.setdefault('activeAcademicYear',2027);s['schemaVersion']=4
def ensure_break_even(s):
    layer=s.setdefault('breakEven',{'plans':[]})
    if not isinstance(layer,dict):raise ValueError('Camada de ponto de equilíbrio inválida.')
    if not isinstance(layer.get('plans',[]),list):raise ValueError('Planos de ponto de equilíbrio inválidos.')
    layer.setdefault('plans',[])
    # Cada item é uma versão imutável de orçamento; mantém compatibilidade com o plano 2027 já existente.
    for plan in layer['plans']:
        plan.setdefault('version',1);plan.setdefault('status','analysis');plan.setdefault('plannedClasses',[]);plan.setdefault('costCenters',[]);plan.setdefault('extractions',[]);plan.setdefault('scenarios',[])
        plan.setdefault('tuitionParameters',[]);plan.setdefault('delinquency',{'officialPercent':plan.get('officialTotals',{}).get('delinquencyPercent'), 'scenarioPercent':None});plan.setdefault('installments',11)
        plan.setdefault('enrollmentRule',{'status':'pending_validation','discountPercent':None});plan.setdefault('approvedAt',None);plan.setdefault('effectiveAt',None)
        plan.setdefault('officialBudget',{'status':'pending_import','classRows':[],'totals':{}})
        plan.setdefault('managerialPlanning',{'status':'draft','installments':plan['installments'],'scenarios':[]})
        source_name=fold(plan.get('source',{}).get('sourceName',''))
        if plan.get('year')==2027 and 'orcamento' in source_name:
            plan.setdefault('personnelCostAudit',copy.deepcopy(PERSONNEL_COST_AUDIT_2027))
def ensure_revenue_planning(s):
    layer=s.setdefault('revenuePlanning',{'years':{}})
    if not isinstance(layer,dict) or not isinstance(layer.get('years',{}),dict):raise ValueError('Camada de receitas inválida.')
    for key,year in layer['years'].items():
        if not isinstance(year,dict):raise ValueError('Ano de receita inválido.')
        year.setdefault('year',int(key));year.setdefault('calendar',{'enrollmentMonth':1,'tuitionMonths':list(range(2,13))})
        year.setdefault('campaigns',[]);year.setdefault('imports',[]);year.setdefault('records',[])
def ensure_teaching_load(s):
    layer=s.setdefault('teachingLoad',{'versions':[]})
    if not isinstance(layer,dict) or not isinstance(layer.get('versions',[]),list):raise ValueError('Camada de carga horária inválida.')
    for item in layer['versions']:
        item.setdefault('status','PREVIA');item.setdefault('records',[]);item.setdefault('mappings',[]);item.setdefault('notes','')
def empty_generic(c):return c.get('template') is True and c.get('capacity',0)==0 and c.get('students',0)==0 and c.get('opening',{}).get('new',0)==0 and c.get('opening',{}).get('re',0)==0 and c.get('unclassified',0)==0
def can_replace_generic_classes(s):
    rooms=s.get('classes',[]);enrollments=s.get('enrollments',{});unallocated=enrollments.get('unallocated',{})
    return len(rooms)==len(LEGACY_CORE_CLASSES) and sorted(fold(x.get('name')) for x in rooms)==sorted(fold(x) for x in LEGACY_CORE_CLASSES) and all(empty_generic(x) for x in rooms) and not enrollments.get('history',[]) and not enrollments.get('new',0) and not enrollments.get('re',0) and not unallocated.get('new',0) and not unallocated.get('re',0)
def upgrade_enrollment_classes(s):
    if can_replace_generic_classes(s):
        s['classes']=report_classes();recalculate(s);return True
    return False
def blank():
    state=dict(schemaVersion=4,meta=1065,classes=report_classes(),benefits=[],requests=[],budget=[],guardians=[],imports=[],tasks=[],audit=[],notifications=[],classificationRules=[],reviewQueue=[],academicYears=[default_financial_year(2027,True)],activeAcademicYear=2027,academicDataYear=2027,breakEven={'plans':[]},revenuePlanning={'years':{}},teachingLoad={'versions':[]},enrollments={'new':0,'re':0,'history':[],'unallocated':{'new':0,'re':0}},delinquency={'financialPercent':None,'accountingPercent':None,'debt':0,'guardians':0,'students':0,'monthly':[]})
    recalculate(state);return state
def allowed(user,module,action='view'):return bool(user and user.get('active') and not user.get('deleted') and (user.get('isAdmin') or action in user.get('access',{}).get(module,[])))
def require(user,module,action='view'):
    if not allowed(user,module,action):raise PermissionError('Permissão insuficiente para esta ação.')
def integer(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and value>=0 and value<=9007199254740991 and int(value)==value
def validate(s,previous=None):
    ensure_financial_years(s)
    ensure_break_even(s)
    ensure_revenue_planning(s)
    ensure_teaching_load(s)
    for key in ['classes','benefits','requests','budget','guardians','tasks','imports','classificationRules','reviewQueue','academicYears']:
        if not isinstance(s.get(key),list):raise ValueError('Lista inválida: '+key)
        ids=[str(x.get('id')) for x in s[key]]
        if len(ids)!=len(set(ids)) or 'None' in ids:raise ValueError('Identificadores ausentes ou duplicados: '+key)
    if not integer(s.get('meta')) or s['meta']<=0:raise ValueError('Meta inválida.')
    for c in s['classes']:
        if not str(c.get('name','')).strip() or not integer(c.get('capacity')):raise ValueError('Turma inválida.')
        if any(not integer(c.get('opening',{}).get(k,0)) for k in ['new','re']) or not integer(c.get('unclassified',0)):raise ValueError('Saldo inicial inválido.')
    for h in s['enrollments']['history']:
        if h.get('type') not in ('new','re') or not integer(h.get('quantity')) or h['quantity']<1:raise ValueError('Quantidade ou tipo inválido.')
        datetime.strptime(h.get('date',''),'%Y-%m-%d')
    for b in s['benefits']:
        if not b.get('name','').strip() or not integer(b.get('quantity')):raise ValueError('Benefício inválido.')
    old_requests={str(r['id']):r for r in (previous or {}).get('requests',[])}
    for r in s['requests']:
        if not r.get('title','').strip() or r.get('status') not in ['requested','waiting','approved','rejected','doing','completed']:raise ValueError('Solicitação inválida.')
        old=old_requests.get(str(r['id']))
        if r.get('status')=='rejected' and not r.get('rejectionReason','').strip() and r!=old:raise ValueError('O motivo da reprovação é obrigatório.')
    for b in s['budget']:
        if not b.get('category','').strip() or any(not isinstance(b.get(k), (int,float)) or b[k]<0 for k in ['budget','actual']):raise ValueError('Orçamento inválido.')
    d=s['delinquency']
    for k in ['financialPercent','accountingPercent']:
        if d.get(k) is not None and (not isinstance(d[k],(int,float)) or not 0<=d[k]<=100):raise ValueError('Percentual inválido.')
    for k in ['guardians','students']:
        if not integer(d.get(k,0)):raise ValueError('Contagem inválida.')
    if not isinstance(d.get('debt',0),(int,float)) or d.get('debt',0)<0:raise ValueError('Dívida inválida.')
    if len({y['year'] for y in s['academicYears']})!=len(s['academicYears']) or any(not integer(y['year']) or not 2000<=y['year']<=2100 for y in s['academicYears']):raise ValueError('Ano letivo inválido.')
    if s['activeAcademicYear'] not in {y['year'] for y in s['academicYears']}:raise ValueError('Ano letivo ativo inválido.')
    ids={x['id'] for x in s['classes']}
    for y in s['academicYears']:
        if {p['id'] for p in y['parameters']}!={p[0] for p in FINANCIAL_SEGMENTS}:raise ValueError('Parâmetros financeiros incompletos.')
        if any(p['tuition'] is not None and p['tuition']<0 for p in y['parameters']):raise ValueError('Mensalidade inválida.')
        for cid,classification in y['classifications'].items():
            if cid not in ids:raise ValueError('Turma financeira inválida.')
            fixed=classification.get('fixed',{});variables=classification.get('variables',[]);total=sum(fixed.get(k,0) for k,_,_ in FINANCIAL_CATEGORIES)+sum(x.get('quantity',0) for x in variables)
            if any(not integer(fixed.get(k,0)) for k,_,_ in FINANCIAL_CATEGORIES) or any(not integer(x.get('quantity',0)) or not isinstance(x.get('percent'),(int,float)) or not 0<=x['percent']<=100 for x in variables):raise ValueError('Classificação financeira inválida.')
            if total>next(c['students'] for c in s['classes'] if c['id']==cid):raise ValueError('Classificação financeira excede os alunos matriculados.')
    plan_ids=[]
    for plan in s['breakEven']['plans']:
        if not isinstance(plan,dict) or not str(plan.get('id','')).strip() or not integer(plan.get('year')) or not integer(plan.get('version',1)):raise ValueError('Plano de ponto de equilíbrio inválido.')
        if plan.get('status') not in ['analysis','reviewed','approved','effective']:raise ValueError('Status de orçamento inválido.')
        plan_ids.append(str(plan['id']))
        totals=plan.get('officialTotals',{})
        if not isinstance(totals,dict) or any(not isinstance(value,(int,float)) or value<0 for value in totals.values()):raise ValueError('Totais oficiais do ponto de equilíbrio inválidos.')
        personnel=plan.get('personnelCostAudit')
        if personnel is not None:
            if not isinstance(personnel,dict) or personnel.get('source')!='Orçamento 2027' or personnel.get('status')!='source_verified' or personnel.get('includedInOfficialTotalExpenses') is not True or personnel.get('allocationStatus')!='not_allocated_to_teachers_or_classes':raise ValueError('Composição de pessoal inválida.')
            fields=['totalMonthly','payrollMonthly','personalChargesAndBenefitsMonthly','nonEmployeeServicesMonthly']
            if any(not isinstance(personnel.get(field),(int,float)) or personnel[field]<0 for field in fields):raise ValueError('Valores da composição de pessoal inválidos.')
            if abs(personnel['totalMonthly']-(personnel['payrollMonthly']+personnel['personalChargesAndBenefitsMonthly']+personnel['nonEmployeeServicesMonthly']))>.005:raise ValueError('Composição de pessoal não confere.')
            if 'totalExpensesMonthly' in totals and personnel['totalMonthly']>totals['totalExpensesMonthly']+.005:raise ValueError('Composição de pessoal excede as despesas oficiais.')
        for key in ['costLines','mappings','rateioRules','plannedClasses','costCenters','extractions','scenarios','tuitionParameters']:
            if not isinstance(plan.get(key,[]),list):raise ValueError('Estrutura de conciliação inválida: '+key)
        source=plan.get('officialBudget',{})
        if not isinstance(source,dict) or not isinstance(source.get('classRows',[]),list) or not isinstance(source.get('totals',{}),dict):raise ValueError('Fonte oficial do orçamento inválida.')
        if not isinstance(plan.get('managerialPlanning',{}),dict):raise ValueError('Planejamento gerencial inválido.')
        old_plan=next((item for item in (previous or {}).get('breakEven',{}).get('plans',[]) if item.get('id')==plan.get('id')),None)
        if old_plan and old_plan.get('officialBudget',{}).get('status')=='source_imported' and source!=old_plan.get('officialBudget'):
            raise ValueError('A fonte oficial é imutável. Crie uma nova versão para corrigir ou substituir o orçamento.')
        if not isinstance(plan.get('installments'),int) or not 1<=plan['installments']<=24:raise ValueError('Quantidade de parcelas inválida.')
        for room in plan['plannedClasses']:
            if not isinstance(room,dict) or not str(room.get('id','')).strip() or not str(room.get('name','')).strip() or not integer(room.get('capacity',0)) or room.get('status','active') not in ['active','inactive']:raise ValueError('Turma planejada inválida.')
        for center in plan['costCenters']:
            if not isinstance(center,dict) or not str(center.get('id','')).strip() or not str(center.get('name','')).strip() or center.get('revenueGenerating') not in [True,False]:raise ValueError('Centro de custo inválido.')
        line_ids=[]
        for line in plan.get('costLines',[]):
            if not isinstance(line,dict) or not str(line.get('id','')).strip() or not str(line.get('label','')).strip() or not isinstance(line.get('amount'),(int,float)) or line['amount']<0:raise ValueError('Linha de custo do ponto de equilíbrio inválida.')
            if line.get('classification') not in ['direct_class','direct_segment','administrative','shared','financial','depreciation','pcld','fund','contribution','pending']:raise ValueError('Classificação de custo inválida.')
            if line.get('reconciliation') not in ['pending','mapped','excluded']:raise ValueError('Situação de conciliação inválida.')
            line_ids.append(str(line['id']))
        if len(line_ids)!=len(set(line_ids)):raise ValueError('Linhas de custo duplicadas no ponto de equilíbrio.')
        for rule in plan.get('rateioRules',[]):
            if not isinstance(rule,dict) or not rule.get('id') or not str(rule.get('name','')).strip():raise ValueError('Regra de rateio sem identificação.')
            if rule.get('driver') not in ['students','revenue','teachingHours','custom']:raise ValueError('Critério de rateio inválido.')
            allocations=rule.get('allocations',[])
            if not isinstance(allocations,list):raise ValueError('Alocações de rateio inválidas.')
            if rule.get('status')=='active':
                total=sum(number(item.get('weight',0),f"peso da regra {rule.get('id')}") for item in allocations if isinstance(item,dict))
                if not allocations or abs(total-100)>0.005:raise ValueError('Regra de rateio ativa deve totalizar 100%.')
    if len(plan_ids)!=len(set(plan_ids)):raise ValueError('Planos de ponto de equilíbrio duplicados.')
    versions=[(p['year'],p.get('version',1)) for p in s['breakEven']['plans']]
    if len(versions)!=len(set(versions)):raise ValueError('Versão de orçamento duplicada para o ano letivo.')
    for year_key,year in s['revenuePlanning']['years'].items():
        if str(year.get('year'))!=str(year_key) or not isinstance(year.get('calendar'),dict):raise ValueError('Ano de receita inconsistente.')
        calendar=year['calendar']
        if calendar.get('enrollmentMonth')!=1 or calendar.get('tuitionMonths')!=list(range(2,13)):raise ValueError('Receita 2027 exige matrícula em janeiro e mensalidades de fevereiro a dezembro.')
        record_ids=set();external=set()
        for campaign in year.get('campaigns',[]):
            if not campaign.get('id') or not str(campaign.get('name','')).strip() or not isinstance(campaign.get('discountPercent'),(int,float)) or not 0<=campaign['discountPercent']<=100:raise ValueError('Campanha de matrícula inválida.')
            date_from=datetime.strptime(campaign.get('startDate',''),'%Y-%m-%d').date();date_to=datetime.strptime(campaign.get('endDate',''),'%Y-%m-%d').date()
            if date_to<date_from or not isinstance(campaign.get('appliesEnrollment'),bool) or not isinstance(campaign.get('exceptions',[]),list):raise ValueError('Período ou exceções da campanha inválidos.')
        for record in year.get('records',[]):
            if not record.get('id') or record['id'] in record_ids or not str(record.get('studentId','')).strip() or record.get('status') not in ['realized','receivable','projected'] or record.get('eventType') not in ['enrollment','tuition','transfer','cancellation','refund']:raise ValueError('Registro de receita inválido.')
            record_ids.add(record['id']);reference=str(record.get('externalId','')).strip()
            if not reference or reference in external:raise ValueError('Identificador financeiro duplicado ou ausente.')
            external.add(reference)
            if record['eventType'] in ['enrollment','tuition'] and (not record.get('classId') or not isinstance(record.get('gross'),(int,float)) or not isinstance(record.get('discount'),(int,float)) or not isinstance(record.get('net'),(int,float))):raise ValueError('Valor de receita inválido.')
            if record['eventType'] in ['enrollment','tuition']:
                if record['classId'] not in ids or record['gross']<0 or record['discount']<0 or record['discount']>record['gross'] or abs(record['net']-(record['gross']-record['discount']))>.01:raise ValueError('Turma ou composição de receita inválida.')
                month=datetime.strptime(record.get('date',''),'%Y-%m-%d').month
                if record['eventType']=='enrollment' and month!=1 or record['eventType']=='tuition' and month not in calendar['tuitionMonths']:raise ValueError('Competência de receita incompatível com calendário 2027.')
    # JSON não aceita NaN/infinito, inclusive em estruturas aninhadas.
    json.dumps(s,allow_nan=False)
def recalculate(s):
    fresh=0;renewed=0
    for c in s['classes']:
        hist=[h for h in s['enrollments']['history'] if str(h['classId'])==str(c['id']) and not h.get('supersededByClassUpdate')]
        new=c.get('opening',{}).get('new',0)+sum(h['quantity'] for h in hist if h['type']=='new')
        re=c.get('opening',{}).get('re',0)+sum(h['quantity'] for h in hist if h['type']=='re')
        c['students']=new+re+c.get('unclassified',0);fresh+=new;renewed+=re
    s['enrollments']['new']=fresh+s['enrollments'].get('unallocated',{}).get('new',0)
    s['enrollments']['re']=renewed+s['enrollments'].get('unallocated',{}).get('re',0)

class Store:
    def __init__(self,path):
        self.path=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, payload TEXT NOT NULL, password TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,csrf TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1),version INTEGER NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS failures(key TEXT PRIMARY KEY,count INTEGER NOT NULL,last REAL NOT NULL);
CREATE TABLE IF NOT EXISTS previews(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY,payload TEXT NOT NULL);''')
            db.execute('INSERT OR IGNORE INTO state VALUES(1,0,?)',(json.dumps(blank()),))
            row=db.execute('SELECT version,payload FROM state WHERE id=1').fetchone();state=json.loads(row['payload']);original=copy.deepcopy(state)
            ensure_financial_years(state);ensure_break_even(state);ensure_revenue_planning(state);ensure_teaching_load(state)
            if upgrade_enrollment_classes(state):
                db.execute('UPDATE state SET payload=?,version=? WHERE id=1',(json.dumps(state),row['version']+1))
            elif state!=original:db.execute('UPDATE state SET payload=?,version=? WHERE id=1',(json.dumps(state),row['version']+1))
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=20);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()
    def users(self,db=None):
        if db is None:
            with self.db() as conn:return self.users(conn)
        return [json.loads(r['payload']) for r in db.execute('SELECT payload FROM users')]
    def state(self,db=None):
        if db is None:
            with self.db() as conn:return self.state(conn)
        row=db.execute('SELECT * FROM state WHERE id=1').fetchone();return json.loads(row['payload']),row['version']
    def audit(self,db,user,module,action,field,before=None,after=None):
        db.execute('INSERT INTO audit(payload) VALUES(?)',(json.dumps({'userId':user['id'],'user':user['name'],'module':module,'action':action,'date':now(),'field':field,'before':before,'after':after},ensure_ascii=False),))
    def create_user(self,name,email,password,access=None,is_admin=False,actor=None,user_id=None):
        with self.lock,self.db() as db:
            if actor:require(actor,'users','create')
            elif self.users(db):raise PermissionError('Administrador inicial já configurado.')
            return self._user(db,{'name':name,'email':email,'password':password,'access':access or {},'isAdmin':is_admin,'active':True,'id':user_id},actor)
    def _user(self,db,payload,actor):
        uid=payload.get('id') or secrets.token_hex(12);row=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone();old=json.loads(row['payload']) if row else None
        if not payload.get('name','').strip() or '@' not in payload.get('email',''):raise ValueError('Nome e e-mail válidos são obrigatórios.')
        if any(u['id']!=uid and fold(u['email'])==fold(payload['email']) for u in self.users(db)):raise ValueError('E-mail já cadastrado.')
        password=payload.pop('password',None)
        if not old and not password:raise ValueError('Senha inicial obrigatória.')
        if password and len(password)<12:raise ValueError('A senha deve ter pelo menos 12 caracteres.')
        access=payload.get('access',{})
        if not isinstance(access,dict) or any(k not in MODULES or not isinstance(v,list) or any(a not in ['view','create','edit','delete','approve'] for a in v) for k,v in access.items()):raise ValueError('Permissões inválidas.')
        user={k:payload.get(k) for k in ['name','email','phone','active','isAdmin']};user.update(id=uid,access=access,deleted=False);user['active']=bool(user['active']);user['isAdmin']=bool(user['isAdmin'])
        if old and old.get('isAdmin') and (not user['active'] or not user['isAdmin']) and not any(u['id']!=uid and u.get('isAdmin') and u.get('active') and not u.get('deleted') for u in self.users(db)):raise ValueError('Mantenha pelo menos um administrador ativo.')
        if password:
            salt=secrets.token_hex(16);digest=salt+':'+hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
        else:digest=row['password']
        db.execute('INSERT OR REPLACE INTO users VALUES(?,?,?)',(uid,json.dumps(user),digest))
        if old:db.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
        self.audit(db,actor or user,'users','edit' if old else 'create',uid,old,user)
        db.execute('UPDATE state SET version=version+1 WHERE id=1');return user
    def user_action(self,actor,payload,action):
        require(actor,'users',action)
        with self.lock,self.db() as db:
            if action!='delete':return self._user(db,dict(payload),actor)
            row=db.execute('SELECT payload FROM users WHERE id=?',(payload['id'],)).fetchone()
            if not row:raise ValueError('Usuário não encontrado.')
            old=json.loads(row[0]);user=dict(old,active=False,deleted=True)
            if old.get('isAdmin') and not any(u['id']!=old['id'] and u.get('active') and u.get('isAdmin') and not u.get('deleted') for u in self.users(db)):raise ValueError('Não é possível excluir o último administrador.')
            db.execute('UPDATE users SET payload=?,password=? WHERE id=?',(json.dumps(user),'',user['id']));db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],));self.audit(db,actor,'users','delete',user['id'],old,user);db.execute('UPDATE state SET version=version+1 WHERE id=1');return user
    def login(self,email,password,remote):
        failkey=hashlib.sha256((remote+'|'+fold(email)).encode()).hexdigest()
        with self.lock,self.db() as db:
            f=db.execute('SELECT * FROM failures WHERE key=?',(failkey,)).fetchone()
            if f and f['count']>=8 and time.time()-f['last']<900:raise PermissionError('Muitas tentativas. Aguarde 15 minutos.')
            row=next((r for r in db.execute('SELECT * FROM users') if fold(json.loads(r['payload'])['email'])==fold(email)),None)
            valid=False;user=json.loads(row['payload']) if row else None
            if row and ':' in row['password']:
                salt,digest=row['password'].split(':');valid=hmac.compare_digest(hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex(),digest)
            if not valid or not user.get('active') or user.get('deleted'):
                count=(f['count']+1) if f and time.time()-f['last']<900 else 1
                db.execute('INSERT OR REPLACE INTO failures VALUES(?,?,?)',(failkey,count,time.time()));db.commit();raise PermissionError('Credenciais inválidas ou usuário inativo.')
            token=secrets.token_urlsafe(40);csrf=secrets.token_urlsafe(32);db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),));db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],csrf,time.time()+8*3600));db.execute('DELETE FROM failures WHERE key=?',(failkey,));self.audit(db,user,'users','login','session');return token,csrf,user
    def session(self,token):
        with self.db() as db:
            row=db.execute('SELECT s.*,u.payload FROM sessions s JOIN users u ON s.user_id=u.id WHERE token=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
            if not row:return None,None
            user=json.loads(row['payload']);return (user,row['csrf']) if user.get('active') and not user.get('deleted') else (None,None)
    def snapshot(self,user):
        with self.db() as db:
            s,version=self.state(db)
            if not user.get('isAdmin'):
                for key,module in {'classes':'enrollments','enrollments':'enrollments','benefits':'benefits','requests':'requests','budget':'budget','delinquency':'delinquency','guardians':'guardians','tasks':'tasks','imports':'budget','classificationRules':'budget','reviewQueue':'budget','breakEven':'financial','revenuePlanning':'financial','teachingLoad':'financial'}.items():
                    visible=allowed(user,module) or (key=='classes' and allowed(user,'classes')) or allowed(user,'dashboard') or allowed(user,'reports')
                    if not visible:s[key]=blank()[key]
                if not allowed(user,'financial'):s['academicYears']=[{'id':str(x['year']),'year':x['year'],'parameters':[],'classifications':{}} for x in s['academicYears']]
                s['requests']=[r for r in s['requests'] if r.get('creatorId')==user['id'] or r.get('recipientId')==user['id']]
            s['users']=self.users(db) if user.get('isAdmin') else [dict(id=u['id'],name=u['name'],phone=u.get('phone',''),active=u['active'],isAdmin=u.get('isAdmin',False)) for u in self.users(db) if not u.get('deleted')]
            s['audit']=[dict(json.loads(r['payload']),id=r['id']) for r in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 2000')] if user.get('isAdmin') else []
            s['notifications']=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM outbox') if user.get('isAdmin') or json.loads(r['payload']).get('userId')==user['id']]
            return {'state':s,'version':version,'user':user}
    def _check_list(self,user,module,old,new):
        before={str(x['id']):x for x in old};after={str(x['id']):x for x in new}
        for uid in before.keys()|after.keys():
            a,b=before.get(uid),after.get(uid)
            if a==b:continue
            action='create' if a is None else 'delete' if b is None else 'edit'
            if module=='requests' and a and b and a.get('status')!=b.get('status') and b.get('status') in ('approved','rejected'):
                changed={k for k in a.keys()|b.keys() if a.get(k)!=b.get(k)}
                if changed<={'status','rejectionReason','history'}:action='approve'
            require(user,module,action)
            if module=='requests':
                if a and not user.get('isAdmin') and user['id'] not in [a.get('creatorId'),a.get('recipientId')]:raise PermissionError('Solicitação de outro usuário.')
                if b and b.get('status') in ('approved','rejected') and (not a or a.get('status')!=b['status']):require(user,module,'approve')
                if b and a and any(b.get(k)!=a.get(k) for k in ['creatorId','creatorName','createdAt','requestedBy']):raise ValueError('Autoria original não pode ser alterada.')
                if b and not a and b.get('creatorId')!=user['id']:raise ValueError('Autoria inválida.')
                if b and a:
                    flow={'requested':['waiting'],'waiting':['approved','rejected'],'approved':['doing'],'rejected':['waiting'],'doing':['completed'],'completed':[]}
                    if b['status']!=a['status'] and b['status'] not in flow.get(a['status'],[]):raise ValueError('Transição de status não permitida.')
                    if b.get('history',[])[:len(a.get('history',[]))]!=a.get('history',[]) or b.get('comments',[])[:len(a.get('comments',[]))]!=a.get('comments',[]):raise ValueError('O histórico existente deve ser preservado.')
    def patch(self,user,changes,version,module,action='edit',confirmation=None):
        if not isinstance(changes,dict):raise ValueError(f'Alteração inválida: changes deve ser objeto; recebido {type(changes).__name__}.')
        if not changes:raise ValueError('Alteração inválida: nenhum campo foi enviado pela interface.')
        unexpected=sorted(set(changes)-MUTABLE)
        if unexpected:raise ValueError('Alteração inválida: campo(s) não permitido(s): '+', '.join(unexpected)+'.')
        with self.lock,self.db() as db:
            old,current=self.state(db)
            if current!=version:raise RuntimeError('Os dados foram atualizados por outra sessão. Revise a alteração antes de salvar novamente.')
            new=copy.deepcopy(old)
            for key,value in changes.items():
                if key=='requests' and not user.get('isAdmin'):
                    hidden=[r for r in old[key] if user['id'] not in [r.get('creatorId'),r.get('recipientId')]]
                    if any(str(r['id']) in {str(x['id']) for x in hidden} for r in value):raise PermissionError('Solicitação de outro usuário.')
                    value=hidden+value
                if key=='meta':
                    if not user.get('isAdmin'):raise PermissionError('Somente administradores podem alterar a meta de matrículas.')
                elif key=='enrollments':self._check_list(user,'enrollments',old[key]['history'],value['history']);require(user,'enrollments','edit' if old[key].get('unallocated')!=value.get('unallocated') else 'view')
                elif key=='classes':
                    # Lançamentos modificam apenas o total derivado; reconciliação modifica saldos de matrícula.
                    a={str(c['id']):c for c in old[key]};b={str(c['id']):c for c in value}
                    for uid in a.keys()|b.keys():
                        left,right=a.get(uid),b.get(uid)
                        if left==right:continue
                        fields={k for k in (left or {}).keys()|(right or {}).keys() if (left or {}).get(k)!=(right or {}).get(k)}
                        if left and right and fields & {'capacity','opening','unclassified'}:
                            # Quem edita Matrículas pode reconciliar somente os quantitativos
                            # de abertura. Capacidade e estrutura da turma continuam administrativas.
                            if not user.get('isAdmin'):
                                if fields <= {'opening','unclassified','students'}:require(user,'enrollments','edit')
                                else:raise PermissionError('Somente administradores podem alterar capacidade ou a estrutura da turma.')
                        elif left and right and fields<={'students'} and 'enrollments' in changes:pass
                        elif left and right and fields<= {'students'}:
                            if not user.get('isAdmin'):raise PermissionError('Somente administradores podem alterar quantitativos da turma.')
                        else:require(user,'classes','create' if left is None else 'delete' if right is None else 'edit')
                elif key in ['academicYears','activeAcademicYear','academicDataYear']:require(user,'financial','edit')
                elif key=='breakEven':
                    require(user,'financial','edit')
                    if not user.get('isAdmin'):
                        old_maps={str(plan.get('id')):plan.get('mappings',[]) for plan in old.get('breakEven',{}).get('plans',[])}
                        new_maps={str(plan.get('id')):plan.get('mappings',[]) for plan in value.get('plans',[])}
                        if old_maps!=new_maps:raise PermissionError('Somente administradores podem conciliar custos ou alterar vínculos de orçamento.')
                elif key=='revenuePlanning':
                    require(user,'financial','edit')
                    if not user.get('isAdmin'):raise PermissionError('Somente administradores podem alterar campanhas e receitas consolidadas.')
                elif key=='teachingLoad':
                    require(user,'financial','edit')
                    if not user.get('isAdmin'):raise PermissionError('Somente administradores podem importar ou conciliar carga horária.')
                elif key in ['imports','classificationRules','reviewQueue']:require(user,'delinquency' if module=='delinquency' else 'budget','edit')
                elif isinstance(value,list):self._check_list(user,key,old[key],value)
                else:require(user,key,'edit')
                new[key]=value
            if 'benefits' in changes:
                for benefit in new['benefits']:
                    prior=next((x for x in old['benefits'] if x['id']==benefit['id']),None)
                    events=copy.deepcopy(prior.get('history',[])) if prior else []
                    for field in ['name','type','quantity','active']:
                        if (prior or {}).get(field)!=benefit.get(field):events.append({'id':secrets.token_hex(12),'userId':user['id'],'user':user['name'],'date':now(),'field':field,'before':(prior or {}).get(field),'after':benefit.get(field)})
                    benefit['history']=events
            if 'requests' in changes:
                removed=len(old['requests'])-len(new['requests'])
                if removed>1 and (not user.get('isAdmin') or confirmation!='APAGAR TODAS AS SOLICITAÇÕES'):raise PermissionError('Exclusão em lote exige administrador e confirmação forte.')
                for r in new['requests']:
                    prior=next((x for x in old['requests'] if x['id']==r['id']),None)
                    if r!=prior:
                        target=next((u for u in self.users(db) if u['id']==r.get('recipientId') and u.get('active') and not u.get('deleted')),None)
                        if not target:raise ValueError('Destinatário inativo ou não encontrado.')
                        if not user.get('isAdmin') and (not prior or prior.get('recipientId')!=r.get('recipientId')) and not target.get('isAdmin'):raise PermissionError('Solicitações deste perfil devem ser enviadas ao administrador.')
                        r['recipientName']=target['name'];r['owner']=target['name']
                        history=copy.deepcopy(prior.get('history',[])) if prior else []
                        if not prior or prior.get('status')!=r['status']:history.append({'date':now(),'user':user['name'],'userId':user['id'],'status':r['status'],'reason':r.get('rejectionReason','')})
                        r['history']=history
                        oldcomments=prior.get('comments',[]) if prior else []
                        r['comments']=oldcomments+[dict(x,user=user['name'],userId=user['id'],date=now()) for x in r.get('comments',[])[len(oldcomments):]]
                        if not prior:r['creatorName']=user['name'];r['createdAt']=now()
                        if not prior or prior.get('status')!=r['status']:self.queue_notification(db,r,r['status'])
            validate(new,old);recalculate(new)
            for key,value in changes.items():
                if isinstance(value,list):
                    a={str(x['id']):x for x in old[key]};b={str(x['id']):x for x in new[key]}
                    for uid in a.keys()|b.keys():
                        left,right=a.get(uid),b.get(uid)
                        if left!=right:
                            for field in (left or {}).keys()|(right or {}).keys():
                                if (left or {}).get(field)!=(right or {}).get(field):self.audit(db,user,key,'create' if left is None else 'delete' if right is None else 'edit',uid+'.'+field,(left or {}).get(field),(right or {}).get(field))
                            if key=='classes' and left and right:
                                class_name=right.get('name',left.get('name','Turma'))
                                for field,label in [('new','Alunos novos'),('re','Rematrículas')]:
                                    before=(left.get('opening') or {}).get(field,0);after=(right.get('opening') or {}).get(field,0)
                                    if before!=after:self.audit(db,user,'classes','edit',class_name+' · '+label,before,after)
                                before=left.get('unclassified',0);after=right.get('unclassified',0)
                                if before!=after:self.audit(db,user,'classes','edit',class_name+' · Matriculados ainda não classificados',before,after)
                    if key=='academicYears':
                        names={str(c['id']):c['name'] for c in new['classes']}
                        for year_id in a.keys()|b.keys():
                            left,right=a.get(year_id) or {},b.get(year_id) or {}
                            for class_id in set((left.get('classifications') or {}))|set((right.get('classifications') or {})):
                                before=(left.get('classifications') or {}).get(class_id,{}) ;after=(right.get('classifications') or {}).get(class_id,{})
                                for category,label,percent in FINANCIAL_CATEGORIES:
                                    old_count=(before.get('fixed') or {}).get(category,0);new_count=(after.get('fixed') or {}).get(category,0)
                                    if old_count!=new_count:self.audit(db,user,'financial','edit',f"Ano {right.get('year',left.get('year'))} · {names.get(class_id,class_id)} · {label} · {percent}%",old_count,new_count)
                                old_vars={str(x.get('id')):x for x in before.get('variables',[])};new_vars={str(x.get('id')):x for x in after.get('variables',[])}
                                for variable_id in old_vars.keys()|new_vars.keys():
                                    old_var,new_var=old_vars.get(variable_id,{}),new_vars.get(variable_id,{})
                                    if old_var.get('quantity',0)!=new_var.get('quantity',0) or old_var.get('percent')!=new_var.get('percent'):self.audit(db,user,'financial','edit',f"Ano {right.get('year',left.get('year'))} · {names.get(class_id,class_id)} · Outros descontos variáveis · {new_var.get('percent',old_var.get('percent',0))}%",old_var.get('quantity',0),new_var.get('quantity',0))
                else:self.audit(db,user,module,action,key,old[key],new[key])
            db.execute('UPDATE state SET version=?,payload=? WHERE id=1',(current+1,json.dumps(new,ensure_ascii=False,allow_nan=False)));return current+1
    def queue_notification(self,db,request,event):
        nid=hashlib.sha256((str(request['id'])+'|'+event+'|'+str(len(request.get('history',[])))).encode()).hexdigest()
        payload={'id':nid,'requestId':request['id'],'userId':request.get('creatorId'),'phone':request.get('requesterPhone',''),'event':event,'createdAt':now(),'attemptedAt':None,'status':'awaiting_configuration','detail':'API oficial de WhatsApp não configurada. Nenhum envio realizado.'}
        return db.execute('INSERT OR IGNORE INTO outbox VALUES(?,?)',(nid,json.dumps(payload))).rowcount
    def overdue(self):
        with self.lock,self.db() as db:
            s,_=self.state(db);today=datetime.now().date().isoformat()
            added=0
            for r in s['requests']:
                if r.get('due') and r['due']<today and r['status'] not in ('completed','rejected'):added+=self.queue_notification(db,r,'overdue')
            if added:db.execute('UPDATE state SET version=version+1 WHERE id=1')

class Handler(BaseHTTPRequestHandler):
    server_version='CAJ'
    def log_message(self,*args):pass
    @property
    def store(self):return self.server.store
    def token(self):
        cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''));return cookie['caj_session'].value if 'caj_session' in cookie else ''
    def respond(self,status,data,headers=None):
        content=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
    def body(self):
        size=int(self.headers.get('Content-Length',0))
        if size>16*1024*1024:raise ValueError('Arquivo excede o limite de 16 MB.')
        return json.loads(self.rfile.read(size) or b'{}',parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Número inválido.')))
    def current(self,mutation=False):
        user,csrf=self.store.session(self.token())
        if not user:raise PermissionError('Sessão encerrada. Entre novamente.')
        if mutation and not hmac.compare_digest(csrf,self.headers.get('X-CSRF-Token','')):raise PermissionError('Token de sessão inválido.')
        return user
    def do_GET(self):
        path=urlparse(self.path).path
        try:
            if path=='/api/health':return self.respond(200,{'available':True,'configured':bool(self.store.users()),'whatsappConfigured':False,'backendRevision':BACKEND_REVISION})
            if path=='/api/me':
                user,csrf=self.store.session(self.token())
                if not user:return self.respond(401,{'error':'Entre para acessar a base compartilhada.'})
                return self.respond(200,{'user':user,'csrf':csrf})
            if path=='/api/state':return self.respond(200,self.store.snapshot(self.current()))
            if path in ('/api/financial/teaching-integration','/api/break-even/integrated'):
                require(self.current(),'financial','view')
                state,version=self.store.state()
                year=int(parse_qs(urlparse(self.path).query).get('year',[state.get('activeAcademicYear',2027)])[0])
                result=integration_snapshot(state,load_documentary_costs(state['classes']),year)
                result['state_version']=version
                return self.respond(200,result)
            if path=='/api/teaching-load/costs':
                require(self.current(),'financial','view')
                state,version=self.store.state()
                result=load_documentary_costs(state['classes'])
                result['state_version']=version
                return self.respond(200,result)
            if path=='/api/events':
                self.current();self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-store');self.send_header('X-Accel-Buffering','no');self.end_headers();last=-1
                for _ in range(240):
                    user,_csrf=self.store.session(self.token())
                    if not user:self.wfile.write(b'event: revoked\ndata: {}\n\n');self.wfile.flush();return
                    self.store.overdue();_,version=self.store.state()
                    if version!=last:self.wfile.write(('event: changed\ndata: '+json.dumps({'version':version})+'\n\n').encode());last=version
                    else:self.wfile.write(b': heartbeat\n\n')
                    self.wfile.flush();time.sleep(1)
                return
            if path=='/api/logo':
                self.current();logo=Path(self.store.path).parent/'logo.png'
                if not logo.exists():return self.respond(404,{'error':'Logo institucional ainda não fornecida.'})
                return self.binary(logo.read_bytes(),'image/png')
            if path.startswith('/api/'):return self.respond(404,{'error':'Rota não encontrada.'})
            permitted={'/':'index.html','/index.html':'index.html','/app.css':'app.css','/app.js':'app.js','/enhancements.js':'enhancements.js','/domain.js':'domain.js','/professional.js':'professional.js','/professional.css':'professional.css','/break_even.js':'break_even.js','/recovered_ui.js':'recovered_ui.js'}
            if path not in permitted:return self.respond(404,{'error':'Arquivo não público.'})
            target=ROOT/permitted[path];typ='text/html' if target.suffix=='.html' else 'text/css' if target.suffix=='.css' else 'text/javascript';return self.binary(target.read_bytes(),typ+'; charset=utf-8')
        except (ConnectionError,TimeoutError):pass
        except PermissionError as ex:self.respond(401,{'error':str(ex)})
        except Exception as ex:self.respond(400,{'error':str(ex)})
    def binary(self,content,mime,name=None):
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','same-origin')
        if name:self.send_header('Content-Disposition','attachment; filename="'+name+'"')
        self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            origin=self.headers.get('Origin')
            if origin and urlparse(origin).netloc!=self.headers.get('Host'):raise PermissionError('Origem não autorizada.')
            p=self.body()
            if path=='/api/login':
                token,csrf,user=self.store.login(p.get('email',''),p.get('password',''),self.client_address[0]);secure='; Secure' if os.environ.get('CAJ_SECURE_COOKIE')=='1' else '';return self.respond(200,{'user':user,'csrf':csrf},{'Set-Cookie':'caj_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'+secure})
            user=self.current(True)
            if path=='/api/logout':
                with self.store.db() as db:db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(self.token().encode()).hexdigest(),))
                return self.respond(200,{'ok':True},{'Set-Cookie':'caj_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
            if path=='/api/state':self.store.patch(user,p['changes'],p['version'],p['module'],p.get('action','edit'),p.get('confirmation'));return self.respond(200,self.store.snapshot(user))
            if path=='/api/users':self.store.user_action(user,p['user'],p['action']);return self.respond(200,{'ok':True})
            if path=='/api/migrate':
                require(user,'users','create')
                with self.store.lock,self.store.db() as db:
                    old,version=self.store.state(db)
                    has_real_classes=any(not item.get('template') for item in old['classes'])
                    if has_real_classes or any(old[k] for k in ['benefits','requests','budget','guardians','tasks']):raise ValueError('A migração inicial só pode ocorrer em uma base compartilhada vazia.')
                    if p.get('confirm')!='MIGRAR DADOS LOCAIS':raise ValueError('Confirmação obrigatória.')
                    state={**blank(),**{k:v for k,v in p['state'].items() if k not in ['users','audit','notifications']}}
                    validate(state,state);recalculate(state);self.store.audit(db,user,'users','migration','state',None,state);db.execute('UPDATE state SET payload=?,version=? WHERE id=1',(json.dumps(state),version+1))
                return self.respond(200,self.store.snapshot(user))
            if path=='/api/logo':
                require(user,'users','edit');from PIL import Image
                import io
                content=base64.b64decode(p['content'],validate=True)
                if len(content)>2*1024*1024:raise ValueError('Logo excede 2 MB.')
                img=Image.open(io.BytesIO(content));img.verify();img=Image.open(io.BytesIO(content));img.thumbnail((1600,1600));img.save(Path(self.store.path).parent/'logo.png','PNG');return self.respond(200,{'ok':True})
            if path in ['/api/import/preview','/api/import/confirm','/api/export','/api/budget-version/preview','/api/financial-classifications/template','/api/financial-classifications/preview','/api/financial-classifications/confirm','/api/revenue-2027/preview','/api/revenue-2027/confirm','/api/teaching-load/preview','/api/classes-update/preview','/api/classes-update/confirm']:
                from services import api_service
                return api_service(self,user,path,p)
            return self.respond(404,{'error':'Rota não encontrada.'})
        except PermissionError as ex:self.respond(403,{'error':str(ex)})
        except RuntimeError as ex:self.respond(409,{'error':str(ex)})
        except (ValueError,KeyError,TypeError,ImportError) as ex:self.respond(400,{'error':str(ex)})
        except Exception:self.respond(500,{'error':'Falha interna. Nenhuma alteração parcial foi confirmada.'})

def serve(path,host='127.0.0.1',port=8765):
    server=ThreadingHTTPServer((host,port),Handler);server.daemon_threads=True;server.store=Store(path);return server
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--create-admin',action='store_true');parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8765);parser.add_argument('--database',default=str(ROOT/'data'/'caj.sqlite3'));args=parser.parse_args()
    if args.create_admin:
        name=input('Nome do administrador: ').strip();email=input('E-mail: ').strip();password=getpass.getpass('Senha (mínimo 12 caracteres): ');confirmation=getpass.getpass('Repita a senha: ')
        if password!=confirmation:raise SystemExit('Senhas diferentes.')
        Store(args.database).create_user(name,email,password,is_admin=True);print('Administrador cadastrado. Nenhum dado escolar foi criado.')
    else:
        server=serve(args.database,args.host,args.port);print(f'CAJ disponível em http://{args.host}:{args.port}. Configure o administrador com --create-admin.');server.serve_forever()
