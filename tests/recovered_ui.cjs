const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function context(state){
  const c=vm.createContext({S:state,benefits:()=>'<section>current</section>',requests:()=>'',budget:()=>'',delinquency:()=>'',
    e:value=>String(value??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x])),
    money:value=>String(value),table:(_headers,rows)=>rows});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../recovered_ui.js'),'utf8'),c);
  return c;
}
test('registros recuperados escapam conteúdo sem alterar fonte',()=>{
  const state={budget:[],recoveredLegacy:{benefits:[{student:'<img src=x onerror=alert(1)>',value:0}],requests:[{title:'<script>alert(1)</script>'}]}};
  const before=JSON.stringify(state), c=context(state);
  assert.match(c.benefits(),/&lt;img/);
  assert.doesNotMatch(c.benefits(),/<img/);
  assert.match(c.requests(),/&lt;script/);
  assert.equal(JSON.stringify(state),before);
});
test('orçamento recuperado mantém aviso de ausência de certificação',()=>{
  const c=context({budget:[{sourceStatus:'recovered_unverified'}],recoveredLegacy:{}});
  assert.match(c.budget(),/Não constituem orçamento certificado/);
});
