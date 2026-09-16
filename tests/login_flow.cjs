const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
test('accepted login loads shared state and renders dashboard without losing authentication',async()=>{
  const elements=new Map();
  function element(selector){if(!elements.has(selector))elements.set(selector,{value:'',innerHTML:'',textContent:'',classList:{add(){},remove(){},toggle(){},contains(){return false}},setAttribute(){},querySelectorAll(){return []},querySelector(){return null},addEventListener(){},insertAdjacentHTML(){},focus(){}});return elements.get(selector);}
  const calls=[];
  const c=vm.createContext({console,Date,Math,Number,String,Array,JSON,Object,Set,Blob,URL,setTimeout(){},
    document:{querySelector:s=>s==='#page table'?null:element(s),addEventListener(){},activeElement:null},
    window:{addEventListener(){}},location:{protocol:'https:'},localStorage:{getItem(){return null},setItem(){throw Error('Unexpected local write');}},
    EventSource:class{addEventListener(){}close(){}},
    fetch:async(url,options)=>{calls.push(url);assert.equal(options.credentials,'same-origin');return {ok:true,json:async()=>url==='/api/login'?{user:{id:'fixture',isAdmin:true,active:true,name:'Fixture'},csrf:'fixture'}:{state:vm.runInContext('SchoolModel.migrate({})',c),version:1,user:{id:'fixture',isAdmin:true,active:true,name:'Fixture'}}};}});
  for(const file of ['app.js','domain.js','enhancements.js','professional.js']){
    let source=fs.readFileSync(path.join(__dirname,'..',file),'utf8');
    if(file==='professional.js')source=source.replace(/bootstrapShared\(\);\s*$/,'');
    vm.runInContext(source,c,{filename:file});
  }
  element('#f_email').value='fixture@example.invalid';element('#f_password').value='fixture-only';
  vm.runInContext("page='login';showLogin();",c);
  await vm.runInContext('login()',c);
  assert.deepEqual(calls,['/api/login','/api/state']);
  assert.equal(vm.runInContext('page',c),'dashboard');
  assert.equal(vm.runInContext('App.user.isAdmin',c),true);
  assert.match(element('#page').innerHTML,/Painel|Dashboard|Visão|Executivo/i);
  assert.equal(element('.profile small').textContent,'Sessão autenticada');
});
