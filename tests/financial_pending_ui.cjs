const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../professional.js'),'utf8');
const summarySource=source.slice(source.indexOf('function financialSummary()'),source.indexOf('function financialTable()'));

function render(unclassifiedFinancial,known=[]){
  let rows;
  const ctx={financeRows:()=>known,S:{classes:[{id:'c1'}],benefits:[]},financeYear:2027,
    M:{financialTotals:()=>({potential:1000,classified:known.reduce((n,x)=>n+x.classified,0),discounts:0,net:0,ticket:0,averageDiscount:0,fullExempt:0,partial:0,unclassifiedFinancial})},
    money:value=>'R$ '+Number(value).toFixed(2),formatPct:value=>value+'%',metrics:value=>{rows=value;return ''}};
  vm.createContext(ctx);vm.runInContext(summarySource,ctx);vm.runInContext('financialSummary()',ctx);return rows;
}

test('indicadores financeiros ausentes exibem pendência sem transformar alunos em desconto zero',()=>{
  const rows=render(752),pending='Pendente — classificação financeira dos alunos';
  assert.equal(rows[1][1],pending);assert.equal(rows[2][1],pending);assert.equal(rows[3][1],pending);
});

test('classificação parcial exibe valores conhecidos sem assumir desconto dos pendentes',()=>{
 const rows=render(8,[{id:'c1',classified:2,tuition:100,knownGross:200,discounts:50,net:150}]);
 assert.equal(rows[1][1],'R$ 50.00');assert.equal(rows[2][1],'R$ 150.00');assert.equal(rows[3][1],'R$ 75.00');
});

test('classificados sem mensalidade continuam sem receita inventada',()=>{
 const rows=render(0,[{id:'c1',classified:2,tuition:null,knownGross:0,discounts:0,net:0}]);
 assert.match(rows[2][1],/Pendente/);
});

test('zero legítimo continua visível quando a classificação financeira está completa',()=>{
  const rows=render(0);
  assert.equal(rows[1][1],'R$ 0.00');assert.equal(rows[2][1],'R$ 0.00');assert.equal(rows[3][1],'R$ 0.00');
});
