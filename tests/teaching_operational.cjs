const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../break_even.js'),'utf8');
async function render(data){
 let html='';const ctx={financial:()=>'',App:{version:1},api:async()=>data,money:v=>String(v),e:v=>String(v).replaceAll('<','&lt;'),metrics:rows=>JSON.stringify(rows),table:(h,b)=>h.join('|')+b,btn:()=>'',modal:(title,body)=>{html=body},toast:msg=>{throw Error(msg)}};
 vm.createContext(ctx);vm.runInContext(code,ctx);await vm.runInContext('openTeachingCosts()',ctx);return html;
}
test('consulta exibe contas separadas e evidencia escapada',async()=>{
 const html=await render({summary:{professors:50},validated_cost:23244.01,conflicted_cost:1680.04,unassigned_cost:1044.90,reference_cost:25968.95,classes:[],professors:[{professor:'Teste',status:'PROCESSADO_COM_RESSALVAS',validated_minutes:45,validated_cost:16.2,conflicted_cost:16.2,unassigned_cost:0,reference_cost:32.4}],operational_allocations:[{bucket:'conflicted',allocation_id:'O1:P1',professor:'Teste',source_code:'EFUND05TD',status:'CONFLITO_DOCUMENTAL',conflict_reason:['SOBREPOSICAO_TEMPORAL'],reference_cost:16.2,source_reference:{page:1,evidence:'<script>'}}]});
 for(const s of ['Custo docente confirmado','Custo em conferência','Custo documental total','23244.01','25968.95','CONFLITO_DOCUMENTAL','&lt;script>'])assert.ok(html.includes(s),s);
 assert.ok(!html.includes('<script>'));
});
test('fonte ausente nao vira custo zero',async()=>{const html=await render({summary:{}});assert.ok(html.includes('Não comprovado'));});
test('todas funcoes de PE preservadas',()=>{
 const before=fs.readFileSync(path.join(__dirname,'../output/finalizacao-operacional-2027/break_even.before.txt'),'utf8');
 const outside=s=>s.slice(0,s.indexOf('async function openTeachingCosts()'))+s.slice(s.indexOf('function beSummary('),s.indexOf('const financialScreen='));
 assert.equal(outside(code).replaceAll('\r\n','\n'),outside(before).replaceAll('\r\n','\n'));
});
