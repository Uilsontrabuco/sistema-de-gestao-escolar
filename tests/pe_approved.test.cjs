const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {validate,renderApproved}=require('../pe_approved.js');
const data=()=>({...JSON.parse(fs.readFileSync(require('node:path').join(__dirname,'../approved_pe_2027_snapshot.json'),'utf8')),snapshotSha256:'a86183ae79d77b1b5ec1125b196e3c0b94ae2d7229e80fcd7c0a34928b0a198e',readOnly:true});
test('renders stored PEs, all classes and negative margins without altering data',()=>{
 const s=data(),before=JSON.stringify(s),html=renderApproved(s);
 assert.equal((html.match(/data-approved-class=/g)||[]).length,41);
 assert.equal((html.match(/class="pe-over-capacity"/g)||[]).length,11);
 for(const row of s.rows)assert.ok(html.includes(`data-approved-class="${row.id}"`));
 assert.ok(html.includes('775 matriculados'));assert.ok(html.includes('15.827,05'));
 assert.equal(JSON.stringify(s),before);
});
test('rejects missing or divergent release metadata and totals',()=>{
 for(const mutate of [s=>s.rows.pop(),s=>s.reserveIncludedInClassCost=true,s=>s.snapshotSha256='bad',s=>s.rows[0].matriculados++,s=>s.rows[0].peAlunos=null]){const s=data();mutate(s);assert.throws(()=>validate(s));}
});
test('2027 browser path calls only approved endpoint, never historical motor',async()=>{
 const calls=[];const context={breakEvenYear:2027,page:'',breakEvenOpen:false,render(){},showBreakEven(){throw Error('Historical calculation');},breakEvenView(){throw Error('Historical view');},openIntegratedTeachingFinance(){throw Error('Historical integration');},api:async path=>{calls.push(path);return data();}};
 vm.createContext(context);vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../pe_approved.js'),'utf8'),context);
 await context.showBreakEven();assert.deepEqual(calls,['break-even/approved?year=2027']);assert.ok(context.breakEvenView().includes('41 turmas'));
});
