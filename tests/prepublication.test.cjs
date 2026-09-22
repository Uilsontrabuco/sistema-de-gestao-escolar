const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('Filters support PE table without legacy table-wrap',()=>{
 const source=fs.readFileSync('professional.js','utf8');const fn=source.slice(source.indexOf('function installFilters()'),source.indexOf('\nrender=function',source.indexOf('function installFilters()')));
 let inserted=false,filtered=false;
 const table={closest:()=>null,before:()=>inserted=true};
 const context={page:'financial',$:selector=>selector==='#page table'?table:null,document:{createElement:()=>({})},applyTableFilters:()=>filtered=true};
 vm.runInNewContext(fn+';installFilters()',context);assert.ok(inserted);assert.ok(filtered);
});

test('PE table retains selector used by financial filters',()=>{assert.match(fs.readFileSync('pe_real.js','utf8'),/id="pe-turmas" class="table-wrap"/);});
