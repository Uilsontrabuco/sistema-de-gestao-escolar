/* Fechamento aprovado: apresenta valores armazenados, sem executar o motor de PE. */
(function(){
  'use strict';
  const checkpoint='PE-2027-FECHAMENTO-TECNICO-APROVADO-2026-09-22';
  const digest='a86183ae79d77b1b5ec1125b196e3c0b94ae2d7229e80fcd7c0a34928b0a198e';
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const cash=x=>(Number(x)/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
  function validate(s){
    if(s.checkpointId!==checkpoint||s.snapshotSha256!==digest||s.readOnly!==true||s.rows?.length!==41||new Set(s.rows.map(r=>r.id)).size!==41||s.costTotalCents!==60564103||s.reserveCents!==1582705||s.reserveIncludedInClassCost!==false)throw Error('Fechamento aprovado ausente ou divergente.');
    for(const [key,total] of [['capacidade',1103],['matriculados',775],['novos',37],['rematriculas',738],['vagas',328],['custoTotalCentavos',60564103]])if(s.rows.reduce((sum,r)=>sum+r[key],0)!==total)throw Error('Totais do fechamento divergentes.');
    if(s.rows.some(r=>!Number.isInteger(r.peAlunos)||r.peAlunos<=0))throw Error('PE aprovado inválido.');
    return s;
  }
  function renderApproved(s){
    validate(s);
    const fields=[['Turma','turma'],['Capacidade','capacidade'],['Matriculados','matriculados'],['Novos','novos'],['Rematrículas','rematriculas'],['Vagas','vagas'],['Custo mensal','custoTotalCentavos'],['Ticket líquido','ticketLiquidoCentavosExato'],['PE aprovado','peAlunos'],['PE % da capacidade','pePercentualCapacidade'],['Margem física','margemFisica'],['Situação','situacao']];
    return `<div class="head"><div><h1>PE 2027 — fechamento aprovado</h1><p>Valores oficiais preservados do fechamento.</p></div><button class="btn alt" onclick="hideBreakEven()">Voltar</button></div><section class="card"><p><b>41 turmas · capacidade 1.103 · 775 matriculados · 37 novos · 738 rematrículas · 328 vagas líquidas.</b></p><p>Custo reconciliado: ${cash(s.costTotalCents)}. Diferença financeira: R$ 0,00. Reserva fora do PE: ${cash(s.reserveCents)}.</p><p>11 turmas com PE superior à capacidade. Vagas e margens negativas permanecem sinalizadas. Estes valores pertencem ao fechamento aprovado; matrículas futuras não recalculam seus PEs.</p><details><summary>Identificação do fechamento</summary><p>${esc(s.checkpointId)}</p><p>SHA-256: ${esc(s.snapshotSha256)}</p></details><button class="btn alt" onclick="window.print()">Imprimir fechamento</button></section><section class="card" style="margin-top:16px"><div class="table-wrap" style="overflow:auto" role="region" tabindex="0" aria-label="41 turmas do fechamento aprovado"><table><thead><tr>${fields.map(([title])=>`<th>${title}</th>`).join('')}</tr></thead><tbody>${s.rows.map(r=>`<tr data-approved-class="${esc(r.id)}"${r.margemFisica<0?' class="pe-over-capacity"':''}>${fields.map(([,key])=>`<td>${key==='custoTotalCentavos'||key==='ticketLiquidoCentavosExato'?cash(r[key]):key==='pePercentualCapacidade'?esc(Number(r[key]).toLocaleString('pt-BR',{maximumFractionDigits:2}))+'%':esc(r[key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`;
  }
  if(typeof module!=='undefined'&&module.exports){module.exports={validate,renderApproved};return;}
  const previousShow=showBreakEven,previousView=breakEvenView,previousIntegrated=openIntegratedTeachingFinance;
  let data=null,error='',loading=false,sequence=0;
  showBreakEven=async function(){
    if(Number(breakEvenYear)!==2027)return previousShow();
    const request=++sequence;page='financial';breakEvenOpen=true;data=null;error='';loading=true;render();
    try{const received=validate(await api('break-even/approved?year=2027'));if(request===sequence)data=received;}
    catch(e){if(request===sequence)error=e.message||'Fechamento indisponível.';}
    finally{if(request===sequence){loading=false;if(breakEvenOpen)render();}}
  };
  breakEvenView=function(){
    if(Number(breakEvenYear)!==2027)return previousView();
    return data?renderApproved(data):`<section class="card"><h1>PE 2027 — fechamento aprovado</h1><p role="status">${loading?'Carregando fechamento aprovado…':esc(error||'Fechamento ainda não carregado.')}</p><button class="btn" onclick="showBreakEven()">Atualizar</button><button class="btn alt" onclick="hideBreakEven()">Voltar</button></section>`;
  };
  openIntegratedTeachingFinance=async function(){return Number(breakEvenYear)===2027?showBreakEven():previousIntegrated();};
})();
