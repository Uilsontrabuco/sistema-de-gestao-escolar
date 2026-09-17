const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const professional=fs.readFileSync(path.join(__dirname,'../professional.js'),'utf8');
const breakEven=fs.readFileSync(path.join(__dirname,'../break_even.js'),'utf8');

test('Master recebe acesso direto ao PE 2027 pelo menu financeiro existente',()=>{
  assert.match(professional,/Ponto de Equilíbrio 2027/);
  assert.match(professional,/x\[1\]==='financial'/);
  assert.match(professional,/onclick="showBreakEven\(\)"/);
});

test('atalho abre a tela existente sem criar outro módulo ou cálculo',()=>{
  assert.doesNotMatch(breakEven,/openBreakEvenFromMenu/);
  assert.match(breakEven,/function breakEvenView\(\)/);
  assert.match(breakEven,/api\(`financial\/teaching-integration\?year=/);
});

test('Parâmetros financeiros encerra o estado visual do PE antes de navegar',()=>{
  assert.match(professional,/target==='financial'.*breakEvenOpen=false;page=target/);
});
