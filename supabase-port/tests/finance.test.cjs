const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const base=path.join(__dirname,'..');
const finance=require('../finance-2027.js');
const ledger=JSON.parse(fs.readFileSync(path.join(base,'private/teaching-cost-2027.json'),'utf8'));
const copy=x=>JSON.parse(JSON.stringify(x));
const rooms=()=>ledger.classes.map((r,i)=>{const m=r.class_name.match(/^(.*) ([A-Z]+)$/);return {id:`id-${i}`,serie:m?m[1]:r.class_name,turma:m?m[2]:'',capacidade:30,matriculados:10};});
const verified=amountCents=>({status:'verified',source:'fixture-document',period:'monthly',amountCents});
const evidence=()=>({year:2027,status:'verified',source:'fixture-plan',totalExpenses:verified(4100000),enrollmentRevenue:{...verified(80000),period:'year'},classes:rooms().map(r=>({classId:r.id,population:{status:'verified',source:'fixture-enrollment',year:2027,studentCount:10},recurringRevenue:{...verified(200000),studentCount:10},totalCost:{...verified(100000),economicSourceId:r.id}}))});
test('fechamento 50 professores, 41 turmas e R$ 25.677,35',()=>{
  finance.validateLedger(ledger);assert.equal(ledger.summary.reconciled_professors,50);
  const s=finance.snapshot(ledger,rooms(),null);assert.equal(s.weeklyCents,2567735);assert.equal(s.rows.length,41);assert.equal(s.weeklyDifferenceCents,0);
});
test('snapshot não modifica turmas, alunos, ledger ou evidências',()=>{
  const r=rooms(),e=evidence(),before=JSON.stringify([ledger,r,e]);finance.snapshot(ledger,r,e);assert.equal(JSON.stringify([ledger,r,e]),before);
});
test('preserva fontes documentais 40/45/50 e tarifas FII/EM',()=>{
  assert.deepEqual([...new Set(ledger.occurrences.map(x=>x.duration_minutes))].sort(),[40,45,50]);
  const rates=ledger.occurrences.flatMap(x=>x.allocations.map(a=>a.hour_aula_rate_2027));assert(rates.includes(26.11));assert(rates.includes(38.5));
  assert.equal(ledger.summary.documentary_time_observations,42);
});
test('rateios financeiros 100% e parcelas únicas',()=>{assert.equal(ledger.summary.financial_duplicates,0);finance.validateLedger(ledger);});
test('rateio adulterado é rejeitado',()=>{const l=copy(ledger);l.occurrences.find(o=>o.allocations.length).allocations[0].financial_fraction_numerator=0;assert.throws(()=>finance.validateLedger(l),/100%/);});
test('parcela duplicada é rejeitada',()=>{const l=copy(ledger);l.operational_allocations.push(l.operational_allocations[0]);assert.throws(()=>finance.validateLedger(l),/duplicada/);});
test('custo divergente é rejeitado',()=>{const l=copy(ledger);l.classes[0].weekly_cost+=1;assert.throws(()=>finance.validateLedger(l),/Soma/);});
test('5º ano mantém destinos manhã A/B e tarde B/C',()=>{
  const ids=Object.fromEntries(ledger.classes.map(r=>[r.class_name,r.class_id]));
  const groups=ledger.occurrences.filter(o=>o.allocations.some(a=>a.link_basis==='REGRA_USUARIO_5_ANO_RATEIO_50_50'));
  assert(groups.length>0);
  for(const o of groups){
    const pair=o.allocations.filter(a=>a.link_basis==='REGRA_USUARIO_5_ANO_RATEIO_50_50');
    assert.equal(pair.length,2);assert(pair.some(a=>a.class_id===ids['5º B']));
    assert.equal(pair[0].financial_fraction_numerator/pair[0].financial_fraction_denominator,pair[1].financial_fraction_numerator/pair[1].financial_fraction_denominator);
  }
});
test('G5 A/B/C preservados sem criar turmas',()=>{for(const name of ['G5 A','G5 B','G5 C'])assert(ledger.classes.some(r=>r.class_name===name));assert.equal(finance.snapshot(ledger,rooms(),null).rows.length,41);});
test('cadastro ambíguo ou incompleto não vincula custos',()=>{
  const r=rooms();assert.throws(()=>finance.snapshot(ledger,r.slice(1),null),/41/);r[1].serie=r[0].serie;r[1].turma=r[0].turma;assert.throws(()=>finance.snapshot(ledger,r,null),/ambíguos/);
});
test('capacidade e alunos reais usados sem valores padrão',()=>{
  const r=rooms();r[0].capacidade=8;r[0].matriculados=12;const row=finance.snapshot(ledger,r,null).rows[0];assert.equal(row.vacancies,0);assert.equal(row.occupancy,150);assert.equal(row.students,12);
  r[0].matriculados=null;assert.throws(()=>finance.snapshot(ledger,r,null),/inválidos/);
});
test('sem evidência PE e receita são nulos, sem mensalização',()=>{
  const s=finance.snapshot(ledger,rooms(),null);assert.equal(s.pe,null);assert.equal(s.recurringRevenueCents,null);assert.equal(s.monthlyTeachingCents,null);assert.equal(s.undetermined,41);
});
test('11 mensalidades e matrícula separada do PE',()=>{
  const s=finance.snapshot(ledger,rooms(),evidence());assert.equal(s.tuitionInstallments,11);assert.equal(s.enrollmentRevenueCents,80000);assert.equal(s.recurringRevenueCents,8200000);assert.equal(s.pe,205);
});
test('despesa existente nunca recebe docência novamente',()=>{
  const s=finance.snapshot(ledger,rooms(),evidence());assert.equal(s.totalExpensesCents,4100000);assert.equal(s.additionalExpenseCents,0);assert.equal(s.resultCents,4100000);assert.equal(s.above,41);
});
test('PE por turma, déficit, margem e arredondamento para cima',()=>{
  const e=evidence();e.classes[0].totalCost.amountCents=201000;const s=finance.snapshot(ledger,rooms(),e);assert.equal(s.rows[0].pe,11);assert.equal(s.rows[0].margin,-1);assert.equal(s.rows[0].resultCents,-1000);assert.equal(s.below,1);
  assert.equal(finance.ceilPE(182000,100000,10),19);
});
test('fonte econômica repetida bloqueia custo das turmas afetadas',()=>{
  const e=evidence();e.classes[1].totalCost.economicSourceId=e.classes[0].totalCost.economicSourceId;const s=finance.snapshot(ledger,rooms(),e);assert.equal(s.rows[0].pe,null);assert.equal(s.rows[1].pe,null);
});
test('ano e população não comprovados bloqueiam PE',()=>{
  const e=evidence();e.year=2026;assert.equal(finance.snapshot(ledger,rooms(),e).pe,null);e.year=2027;e.classes[0].population.studentCount=9;assert.equal(finance.snapshot(ledger,rooms(),e).pe,null);
});
test('receita individualizada prevalece e mantém bolsas e descontos',()=>{
  const r={...verified(999999),studentCount:3,students:[{id:'a',tuitionCents:10000,discountBasisPoints:0},{id:'b',tuitionCents:10000,discountBasisPoints:5000},{id:'c',tuitionCents:10000,discountBasisPoints:10000}]};assert.equal(finance.revenueEvidence(r,3),15000);
  r.students[1].id='a';assert.equal(finance.revenueEvidence(r,3),null);
});
test('ausência de desconto não vira desconto zero',()=>{assert.equal(finance.revenueEvidence({...verified(10000),students:[{id:'a',tuitionCents:10000}]},1),null);});
test('receita zero é comprovável mas não gera PE fictício',()=>{const e=evidence();for(const d of e.classes)d.recurringRevenue.amountCents=0;const s=finance.snapshot(ledger,rooms(),e);assert.equal(s.recurringRevenueCents,0);assert.equal(s.pe,null);});
test('custo anual não é tratado como custo mensal',()=>{const e=evidence();e.totalExpenses.period='year';e.classes[0].totalCost.period='year';const s=finance.snapshot(ledger,rooms(),e);assert.equal(s.pe,null);assert.equal(s.rows[0].pe,null);});
function client({role='master',active=true,user=true,errorTable=null}={}){
  const calls=[];const c={calls,auth:{getUser:async()=>({data:{user:user?{id:'test-user'}:null}})},from(table){calls.push(table);const q={select(){return q;},eq(){return q;},order(){return q;},limit(){return q;},range:async()=>({data:rooms()}),single:async()=>({data:{role,ativo:active}}),maybeSingle:async()=>table===errorTable?{error:{code:'denied'}}:{data:{version:1,snapshot_version:1,payload:table==='teaching_cost_snapshots'?ledger:evidence()}}};return q;}};return c;
}
test('leitura Supabase paginada com Master ativo',async()=>{const c=client();const s=await finance.load(c);assert.equal(s.pe,205);assert.deepEqual(c.calls,['profiles','turmas','teaching_cost_snapshots','financial_evidence']);});
test('sem autenticação não consulta tabelas',async()=>{const c=client({user:false});await assert.rejects(finance.load(c),/Entre/);assert.deepEqual(c.calls,[]);});
for(const opts of [{role:'promotora'},{role:'comum'},{active:false}])test('nega financeiro '+JSON.stringify(opts),async()=>{const c=client(opts);await assert.rejects(finance.load(c),/Master/);assert.deepEqual(c.calls,['profiles']);});
test('RLS nega snapshot: nenhum fallback para dados locais',async()=>{await assert.rejects(finance.load(client({errorTable:'teaching_cost_snapshots'})),/não disponibilizado/);});
test('evidências indisponíveis preservam apenas o custeio confirmado',async()=>{const s=await finance.load(client({errorTable:'financial_evidence'}));assert.equal(s.pe,null);assert.equal(s.weeklyCents,2567735);assert.equal(s.evidenceUnavailable,true);});
test('módulo novo não contém operação de escrita',()=>{
  for(const file of ['finance-2027.js','finance-2027-ui.js'])assert(!/\.(insert|update|upsert|delete|rpc|setItem)\s*\(/.test(fs.readFileSync(path.join(base,file),'utf8')));
});
const html=fs.readFileSync(path.join(base,'index.html'),'utf8');
const upstream=fs.readFileSync(path.join(base,'private/upstream-index.html'),'utf8');
const inline=s=>[...s.replace(/\r\n/g,'\n').matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
test('todos scripts inline válidos e scripts novos válidos',()=>{inline(html).forEach(s=>new vm.Script(s));for(const f of ['finance-2027.js','finance-2027-ui.js'])new vm.Script(fs.readFileSync(path.join(base,f),'utf8'));});
test('módulos legados preservados; somente bypass de login removido',()=>{
  const old=inline(upstream).filter(s=>s.trim()),now=inline(html).filter(s=>s.trim());assert.equal(old.length,now.length);
  assert(now[0].includes("supabaseUrl:''")&&now[0].includes("supabaseAnonKey:''"),'Nenhuma configuração de acesso embutida');
  const withoutLogin=s=>s.replace(/async function doLogin\(\)[^\n]*/,'');
  assert(withoutLogin(now[1])===withoutLogin(old[1]),'Módulos operacionais originais preservados');
  const before=old.find(s=>s.includes('async function doLogin()')).match(/async function doLogin\(\)[^\n]*/)[0];
  const after=now.find(s=>s.includes('async function doLogin()')).match(/async function doLogin\(\)[^\n]*/)[0];
  assert(after.startsWith(before.slice(0,before.indexOf('if((u.toLowerCase()'))),'Fluxo real Supabase preservado');
  assert(!after.includes('state.users[')&&!after.includes('p==='),'Sem credenciais ou login de demonstração');
});
test('schema original não alterado',()=>{
  const crypto=require('node:crypto');const manifest=JSON.parse(fs.readFileSync(path.join(base,'private/upstream.json')));assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(base,'supabase_schema.sql'))).digest('hex'),manifest.hashes['supabase_schema.sql']);
});
test('dados privados, SQL e testes excluídos da publicação',()=>{
  const ignore=fs.readFileSync(path.join(base,'.vercelignore'),'utf8');for(const p of ['private/','tests/','review/','*.sql'])assert(ignore.includes(p));
  const config=JSON.parse(fs.readFileSync(path.join(base,'vercel.json')));assert(config.routes.some(r=>r.status===404&&r.src.includes('private')));
});
function runtime(profile={role:'master',ativo:true},loginError=null){
  const nodes=new Map(),events={},calls=[];const node=id=>{if(!nodes.has(id))nodes.set(id,{value:'',classList:{add(){},remove(){}},textContent:'',innerHTML:''});return nodes.get(id);};
  const sb={auth:{signInWithPassword:async()=>{calls.push('signInWithPassword');return {data:{user:{id:'test-user'}},error:loginError};},signOut:async()=>{calls.push('signOut');},getSession:async()=>({data:{session:null}})},from:()=>({select:()=>({eq:()=>({single:async()=>({data:{id:'test-user',nome:'Test',email:'test@example.invalid',...profile}})})})})};
  const c={URL,atob:s=>Buffer.from(s,'base64').toString('binary'),console:{error(){},warn(){}},setTimeout(){},localStorage:{getItem(){return null;},setItem(){throw Error('Unexpected write');}},document:{getElementById:node},window:{supabase:{createClient:()=>sb},addEventListener:(n,f)=>events[n]=f}};
  vm.createContext(c);for(const s of inline(html))vm.runInContext(s,c);
  c.window.seven7Supabase=sb;vm.runInContext('renderApp=function(){};toast=function(){}',c);node('loginUser').value='test@example.invalid';node('loginPass').value='isolated-test-password';
  return {c,calls,nodes};
}
test('login Supabase existente autentica e mantém perfil',async()=>{const {c,calls}=runtime();await vm.runInContext('doLogin()',c);assert.equal(vm.runInContext('session.role',c),'Master');assert.deepEqual(calls,['signInWithPassword']);});
test('login recusado não cria sessão',async()=>{const {c}=runtime(undefined,new Error('denied'));await vm.runInContext('doLogin()',c);assert.equal(vm.runInContext('session',c),null);});
test('perfil bloqueado não cria sessão',async()=>{const {c}=runtime({role:'master',ativo:false});await vm.runInContext('doLogin()',c);assert.equal(vm.runInContext('session',c),null);});
test('promotora mantém perfil sem acesso administrativo no menu',async()=>{const {c}=runtime({role:'promotora',ativo:true});await vm.runInContext('doLogin()',c);assert(!vm.runInContext('navItems().some(x=>x[0]==="orcamento")',c));});
test('logout mantém chamada Supabase',async()=>{const {c,calls}=runtime();await vm.runInContext('doLogin()',c);await vm.runInContext('logout()',c);assert(calls.includes('signOut'));assert.equal(vm.runInContext('session',c),null);});
test('sem cliente Supabase nenhum login local concede Master',async()=>{
  const {c,calls,nodes}=runtime();c.window.seven7Supabase=null;
  // Test formerly accepted inputs without printing or storing their values.
  const original=inline(upstream).join('\n');
  const pairs=[...original.matchAll(/u\.toLowerCase\(\)==='([^']+)'&&p==='([^']+)'/g)];
  assert(pairs.length>0);
  for(const pair of pairs){nodes.get('loginUser').value=pair[1];nodes.get('loginPass').value=pair[2];await vm.runInContext('doLogin()',c);assert(vm.runInContext('session===null',c),'Sessão deve permanecer ausente');}
  assert.equal(calls.length,0);
});
test('nenhuma credencial de demonstração permanece no login preparado',()=>{
  const login=inline(html).join('\n').match(/async function doLogin\(\)[^\n]*/)[0];
  assert(!/p\s*===\s*['"]/.test(login));assert(!login.includes('state.users'));
});
test('persistência e estado localStorage legado permanecem intactos',()=>{
  const source=inline(upstream).join('\n'),current=inline(html).join('\n');
  for(const expression of [/let state=[^\n]*/,/function save\(\)[^\n]*/])assert(source.match(expression)[0]===current.match(expression)[0],'Persistência legada preservada');
});
test('consulta solicita apenas versões aprovadas mais recentes',async()=>{
  const c=client();const from=c.from,operations=[];
  c.from=table=>{const q=from(table);if(table!=='profiles'&&table!=='turmas'){
    q.eq=(key,value)=>{operations.push([table,'eq',key,value]);return q;};q.order=(key,opt)=>{operations.push([table,'order',key,opt.ascending]);return q;};q.limit=n=>{operations.push([table,'limit',n]);return q;};
  }return q;};await finance.load(c);
  for(const table of ['teaching_cost_snapshots','financial_evidence']){
    assert(operations.some(o=>o[0]===table&&o[1]==='eq'&&o[2]==='status'&&o[3]==='approved'));
    assert(operations.some(o=>o[0]===table&&o[1]==='order'&&o[2]==='version'&&o[3]===false));
    assert(operations.some(o=>o[0]===table&&o[1]==='limit'&&o[2]===1));
  }
});
test('evidência de outra versão bloqueia PE sem bloquear fechamento',async()=>{
  const c=client(),from=c.from;c.from=table=>{const q=from(table);if(table==='financial_evidence')q.maybeSingle=async()=>({data:{version:2,snapshot_version:2,payload:evidence()}});return q;};
  const s=await finance.load(c);assert.equal(s.pe,null);assert.equal(s.weeklyCents,2567735);assert(s.evidenceUnavailable);
});
test('SQL proposto restringe leitura, preserva RLS e impede mutações',()=>{
  const sql=fs.readFileSync(path.join(base,'review/additive-schema.sql'),'utf8');
  assert.equal((sql.match(/enable row level security/gi)||[]).length,2);
  assert(!/disable row level security|grant\s+(all|insert|update|delete)\b/i.test(sql));
  assert.equal((sql.match(/primary key \(year,version\)/g)||[]).length,2);
  assert(sql.includes('foreign key (year,snapshot_version)'));
  assert(sql.includes('public.is_master()'));
  assert(!/\b(drop|truncate|delete)\b/i.test(sql));
  assert(!/create (or replace )?function|alter function|public\.profiles\b|profiles_master/i.test(sql));
  assert.equal((sql.match(/create table if not exists/g)||[]).length,2);
  assert(sql.includes('create index if not exists'));
  assert(sql.includes('if found then')&&sql.includes('Política incompatível'));
});
test('proposta anterior de alteração de perfis cancelada',()=>{
  const sql=fs.readFileSync(path.join(base,'review/profiles-rls-prerequisite.sql'),'utf8');
  assert.equal(sql.split('\n').filter(line=>line.trim()&&!line.trim().startsWith('--')).length,0);
});
function uiRuntime(sessionValue,load){
  const result={textContent:'',innerHTML:''};const c={session:sessionValue,window:{seven7Supabase:{}},Seven7Finance:{load},esc:s=>s,kpi:()=>'',go(){},toast(){},renderNav(){},logout:async()=>{},document:{createElement:()=>({}),querySelector:()=>({appendChild(){}}),getElementById:id=>id==='finance2027Result'?result:{appendChild(){}}}};
  vm.createContext(c);vm.runInContext(fs.readFileSync(path.join(base,'finance-2027-ui.js'),'utf8'),c);return {c,result};
}
test('interface nega consulta sem sessão Supabase Master',async()=>{
  let reads=0;for(const s of [null,{role:'Master'},{uid:'user',role:'Comum'}]){const {c}=uiRuntime(s,async()=>{reads++;});await c.window.openFinance2027();}assert.equal(reads,0);
});
test('resposta em andamento não reaparece após logout',async()=>{
  let resolve;const pending=new Promise(r=>resolve=r);const {c,result}=uiRuntime({uid:'user',role:'Master'},()=>pending);
  const request=c.window.openFinance2027();await vm.runInContext('logout()',c);resolve(finance.snapshot(ledger,rooms(),null));await request;assert.equal(result.innerHTML,'');assert.equal(result.textContent,'');
});
test('configuração aceita apenas chave pública e endpoint HTTPS',()=>{
  const {c}=runtime();c.url='https://example.invalid';c.key='sb_publishable_fixture';
  assert(vm.runInContext('validSupabaseConfig(url,key)',c));
  for(const value of ['sb_secret_fixture','invalid']){c.key=value;assert(!vm.runInContext('validSupabaseConfig(url,key)',c));}
  const token=role=>['e30',Buffer.from(JSON.stringify({role})).toString('base64url'),'test'].join('.');
  c.key=token('service_role');assert(!vm.runInContext('validSupabaseConfig(url,key)',c));
  c.key=token('anon');assert(vm.runInContext('validSupabaseConfig(url,key)',c));
  c.url='http://example.invalid';assert(!vm.runInContext('validSupabaseConfig(url,key)',c));
});
test('validação de configuração precede gravação e não contém chaves embutidas',()=>{
  const setup=html.slice(html.indexOf('function saveSupabaseSetup()'));
  assert(setup.indexOf('if(!window.initSeven7Supabase')<setup.indexOf("localStorage.setItem('seven7_supabase_url'"));
  assert(!/sb_(publishable|secret)_[A-Za-z0-9_-]{10,}/.test(html));
  assert(!/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/.test(html));
});
test('correção administrativa exige owner e corpo exatos sem ampliar ACL',()=>{
  const sql=fs.readFileSync(path.join(base,'review/correct-authorization.sql'),'utf8');
  assert(sql.includes("f.rolname <> 'postgres'"));assert(sql.includes('c.relforcerowsecurity'));assert(sql.includes('normalized_body <>'));
  assert(!/\bgrant\b|alter.*owner|create.*function/i.test(sql));
  assert(sql.includes('alter function public.is_master() security definer'));
  assert(sql.includes("alter function public.is_master() set search_path = ''"));
});
test('introspecção preparada somente lê catálogos e gera metadados de rollback',()=>{
  const sql=fs.readFileSync(path.join(base,'review/inspect-authorization.sql'),'utf8');
  assert(sql.includes('pg_catalog.pg_depend'));assert(sql.includes('rollback_search_path'));
  assert(!/from\s+public\.(profiles|alunos)/i.test(sql));
});
