const test=require('node:test');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {renderLayers}=require('../pe_layers.js');
const data=JSON.parse(execFileSync('python',['-c','import json; from pe_layers import build_layers; print(json.dumps(build_layers()))'],{cwd:require('node:path').join(__dirname,'..'),encoding:'utf8'}));
test('Three layers render all 41 unique rows',()=>{const html=renderLayers(data);assert.equal((html.match(/data-pe-class=/g)||[]).length,41);assert.match(html,/PE Orçamentário/);assert.match(html,/PE Gerencial/);assert.match(html,/PE Provisório/);assert.match(html,/Projeção real 2027/);});
test('Pending data and partial cost coverage visible',()=>{const html=renderLayers(data);assert.match(html,/Cobertura de custos incompleta/);assert.match(html,/valor ainda desconhecido/);assert.match(html,/Não alimentada/);assert.match(html,/Sem correspondência/);});
test('Provisional above capacity never claims definite infeasibility',()=>{const html=renderLayers(data);assert.match(html,/Provisório · acima da capacidade/);assert.doesNotMatch(html,/>INVIÁVEL FISICAMENTE</);});
test('Renderer escapes evidence text and names',()=>{const edited=structuredClone(data);edited.rows[0].name='<img src=x onerror=alert(1)>';assert.doesNotMatch(renderLayers(edited),/<img src=x/);assert.match(renderLayers(edited),/&lt;img/);});
test('Renderer does not mutate layer data',()=>{const before=JSON.stringify(data);renderLayers(data);assert.equal(JSON.stringify(data),before);});
function browserFixture(){const vm=require('node:vm'),fs=require('node:fs');const c={breakEvenYear:2027,page:'dashboard',breakEvenOpen:false,showBreakEven(){},breakEvenView(){return 'legacy';},openIntegratedTeachingFinance(){},render(){},api:async()=>structuredClone(data)};vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../pe_layers.js'),'utf8'),c);return c;}
test('PE navigation from Dashboard opens financial layer view',async()=>{const c=browserFixture();await c.showBreakEven();assert.equal(c.page,'financial');assert.equal(c.breakEvenOpen,true);assert.match(c.breakEvenView(),/G2 A/);});
test('Failed refresh never leaves stale confirmed values visible',async()=>{const c=browserFixture();await c.showBreakEven();c.api=async()=>{throw new Error('fixture failure');};await c.showBreakEven();const html=c.breakEvenView();assert.match(html,/fixture failure/);assert.doesNotMatch(html,/data-pe-class=/);});
