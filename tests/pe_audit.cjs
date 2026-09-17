const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');

function runtime(){
  const classes=Array.from({length:41},(_,index)=>({id:'c'+index,name:'Turma '+(index+1),capacity:index===40?303:20}));
  const totals=classes.map((room,index)=>index===40?32:18);
  const ctx={financial:()=>'',App:{version:1,mode:'local'},S:{classes,breakEven:{plans:[]}},
    M:{financialStats:(_state,room)=>{const total=totals[Number(room.id.slice(1))];return {id:room.id,name:room.name,capacity:room.capacity,total,classified:0,unclassifiedFinancial:total,tuition:100,potential:total*100,knownGross:0,discounts:0,net:0,groups:[],segmentLabel:'Segmento'}},fold:value=>String(value).toLowerCase()},
    money:value=>'R$ '+Number(value).toFixed(2),e:value=>String(value),api:async()=>{},render:()=>{},toast:()=>{},
    metrics:()=>'',table:()=>'',card:()=>'',head:()=>'',btn:()=>'',financialAllowed:()=>false,currentUser:()=>({isAdmin:true})};
  vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../break_even.js'),'utf8'),ctx);return ctx;
}

test('fonte oficial 2027 é vinculada somente para consulta quando não há versão persistida',()=>{
  const ctx=runtime(),before=JSON.stringify(ctx.S);
  const plan=vm.runInContext('bePlan()',ctx);
  assert.equal(plan.readOnlyLink,true);assert.equal(plan.officialBudget.totals.totalExpensesMonthly,841486.96);
  assert.equal(JSON.stringify(ctx.S),before);
});

test('41 turmas sem custo mensal ficam estruturalmente pendentes e não classificados não viram desconto zero',()=>{
  const ctx=runtime();ctx.plan=vm.runInContext('bePlan()',ctx);
  const audit=vm.runInContext('beAuditOverview(plan)',ctx);
  assert.equal(audit.rows.length,41);assert.equal(audit.students,752);assert.equal(audit.definitive,0);assert.equal(audit.pending.length,41);
  assert.equal(audit.discounts,null);assert.equal(audit.net,null);assert.equal(audit.effective,null);assert.equal(audit.result,null);
  assert(audit.rows.every(row=>row.calculationStatus.includes('integração estrutural ainda não carregada')));
});

test('resumo geral é soma das turmas quando a classificação e os custos ficam completos',()=>{
  const ctx=runtime();ctx.M.financialStats=(_state,room)=>({id:room.id,name:room.name,capacity:room.capacity,total:1,classified:1,unclassifiedFinancial:0,tuition:100,potential:100,knownGross:100,discounts:10,net:90,groups:[{quantity:1,percent:10}],segmentLabel:'Segmento'});
  ctx.plan=vm.runInContext('bePlan()',ctx);ctx.plan.mappings=ctx.S.classes.map(room=>({operationalClassId:room.id,status:'mapped',costMonthly:50,costEvidence:{status:'verified'}}));
  ctx.integrated=ctx.S.classes.map(room=>({class_id:room.id,totalCostMonthly:50,teachingCostWeekly:10,teachingCostMonthly:null,structuralTicketMonthly:90,structuralDiscountPercent:10,structuralDiscountOrigin:'fixture',breakEvenStudents:1,breakEvenPercentCapacity:100/room.capacity,physicalMarginStudents:room.capacity-1,structuralPendingReasons:[]}));
  vm.runInContext('breakEvenIntegrated={classes:integrated}',ctx);
  const audit=vm.runInContext('beAuditOverview(plan)',ctx);
  assert.equal(audit.net,3690);assert.equal(audit.totalCost,2050);assert(Math.abs(audit.result-1473.95)<0.000001);
  assert.equal(audit.definitive,41);assert.equal(audit.pending.length,0);
});

test('contrato do frontend usa fator 4,5 e estados assíncronos determinísticos',()=>{
  const code=fs.readFileSync(path.join(__dirname,'../break_even.js'),'utf8');
  assert(code.includes('Promise.allSettled'));
  assert(code.includes("status:'loading'"));
  assert(code.includes("status:Object.keys(errors).length"));
  assert(code.includes('semanal × 4,5'));
  assert(!code.includes('semanal × 4,0'));
  for(const field of ['teachingCostWeekly','teachingCostMonthly','otherDirectCostsMonthly','indirectExpensesMonthly','totalCostMonthly','structuralTicketMonthly','breakEvenStudents','breakEvenPercentCapacity','physicalMarginStudents'])assert(code.includes(field),field);
});

test('navegação autenticada do menu dispara a API estrutural do PE',()=>{
  const code=fs.readFileSync(path.join(__dirname,'../professional.js'),'utf8');
  assert(code.includes('button[aria-label="Ponto de Equilíbrio 2027"]'));
  assert(code.includes('refreshShared().then(showBreakEven)'));
  const pe=fs.readFileSync(path.join(__dirname,'../break_even.js'),'utf8');
  assert(pe.includes("api('teaching-load/costs')"));
  assert(pe.includes("api(`break-even/integrated?year=${encodeURIComponent(breakEvenYear)}`)"));
});
