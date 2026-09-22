/* Consulta local das três camadas; não grava estado nem importa descontos. */
(function(root){
  'use strict';
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number=value=>value==null?'Pendente':escape(value);
  const cash=value=>value==null?'Pendente':(Number(value)/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
  const percent=value=>value==null?'Pendente':Number(value).toFixed(1).replace('.',',')+'%';
  function renderLayers(data){
    const headers=['Turma','Capacidade','PE Orçamentário¹','PE Gerencial²','PE Provisório','Custo comprovado²','Custo pendente','Ticket','PE %²','Margem física²','Status'];
    const rows=data.rows.map(r=>{
      const d=r.documentary,m=r.managerial,p=r.provisional;
      const doc=d.pe==null?'Sem correspondência':`${number(d.pe)}<br><small>PDF: ${number(d.printedPE)} · ${escape(d.status)}</small>`;
      return `<tr data-pe-class="${escape(r.id)}"><th scope="row">${escape(r.name)}</th><td>${number(r.capacity)}</td><td>${doc}</td><td>${number(m.pe)}<br><small>base comprovada parcial</small></td><td>${r.pendingCosts.knownCents||r.pendingCosts.unknownItems.length?`${number(p.pe)}<br><small>Provisório${p.aboveCapacityWarning?' · acima da capacidade':''}</small>`:'—'}</td><td>${cash(m.costCents)}</td><td>${cash(r.pendingCosts.knownCents)}${r.pendingCosts.unknownItems.length?'<br><small>+ valor ainda desconhecido</small>':''}</td><td>${cash(m.ticketCents)}</td><td>${percent(m.percentCapacity)}</td><td>${number(m.physicalMargin)}</td><td>${escape(r.status)}<br><small>${m.completeCostCoverage?'Cobertura completa':'Cobertura de custos incompleta'}</small></td></tr>`;
    }).join('');
    const memories=data.rows.map(r=>{
      const d=r.documentary,s=d.sourceValues,m=r.managerial;
      const realMoney=v=>v==null?'Pendente':cash(Math.round(Number(v)*100));
      return `<details><summary>${escape(r.name)} — memória das três camadas</summary><h3>PE Orçamentário</h3><p>${escape(d.source)} · página ${number(d.page)}. ${escape(d.observation||'SEM CORRESPONDÊNCIA DOCUMENTAL DIRETA')}</p>${s?`<p>Alunos previstos: ${number(s.students)}. Mensalidades: ${realMoney(s.grossRevenue)}; outras receitas: ${realMoney(s.otherRevenue)}; gratuidades/convênios: ${realMoney(s.freeTuition)}; desconto comercial: ${realMoney(s.commercialDiscount)}; receita líquida: ${realMoney(s.netRevenue)}; custo: ${realMoney(s.totalCost)}.</p>`:''}<p>${escape(d.formula)}. Teto reconstruído: ${number(d.pe)}. Valor impresso: ${number(d.printedPE)}. ${escape(d.precision)}</p><h3>PE Gerencial</h3><p>${cash(m.costCents)} ÷ ${cash(m.ticketCents)}, arredondado para cima = ${number(m.pe)}. Receita na capacidade: ${cash(m.revenueAtCapacityCents)}. Resultado com custos comprovados parciais: ${cash(m.resultAtCapacityCents)}. Mensalidade: ${cash(r.tuitionCents)} — ${escape(r.tuitionSource)}.</p><ul>${m.costs.map(c=>`<li>${escape(c.kind)}: ${cash(c.cents)} — ${escape(c.evidence)}</li>`).join('')}</ul><h3>Custo pendente de comprovação</h3><ul>${r.pendingCosts.items.map(c=>`<li>${escape(c.kind)}: ${cash(c.cents)}</li>`).join('')}${r.pendingCosts.unknownItems.map(c=>`<li>${escape(c.person)}: valor desconhecido — ${escape(c.reason)}</li>`).join('')}</ul><h3>Projeção real 2027</h3><p>Não alimentada. Alunos, receita, ticket médio, descontos, margem e distância até o PE: pendentes. Projeção real não substitui o PE.</p></details>`;
    }).join('');
    return `<div class="head"><div><p class="eyebrow">7&7 · 2027</p><h1>Ponto de equilíbrio — três camadas</h1><p>Orçamento documental, estrutura econômica e projeção real separados.</p></div><button class="btn alt" onclick="hideBreakEven()">Voltar aos parâmetros</button></div><section class="card"><p><b>${data.summary.classes} turmas · ${data.summary.capacity} vagas.</b> Custos comprovados: ${cash(data.summary.verifiedMonthlyCents)}. Pendentes conhecidos: ${cash(data.summary.pendingKnownMonthlyCents)}. Nenhum PE gerencial documentalmente fechado.</p><p title="Reproduz o cenário do orçamento oficial 2027."><b>¹ PE Orçamentário:</b> teto reconstruído e valor impresso preservados separadamente. Divergências de arredondamento aguardam a fórmula/precisão da planilha 2027.</p><p title="Calculado com custos econômicos comprovados e ticket gerencial."><b>² PE Gerencial:</b> somente os custos comprovados da base homologada. Enquanto faltarem custos, não representa equilíbrio econômico completo. PE %, margem física e resultado usam essa base parcial.</p><p title="Inclui valores ainda pendentes de comprovação documental."><b>PE Provisório:</b> inclui custos pendentes; superar a capacidade não comprova inviabilidade definitiva.</p><p>G2 A/B: PE documental 15 preservado. ${escape(data.costBasis)}</p></section><section class="card" style="margin-top:16px"><h2>As 41 turmas</h2><div role="region" aria-label="Comparação dos três indicadores" tabindex="0" style="overflow:auto"><table><thead><tr>${headers.map(x=>`<th scope="col">${x}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div></section><section class="card" style="margin-top:16px"><h2>Projeção real 2027 — ainda não alimentada</h2><p>Importação de descontos desabilitada nesta camada. Matrículas não determinam o PE estrutural.</p><p>${escape(data.discountCoverage.status)}: ${cash(data.discountCoverage.monthlyCents)}. A base real substituirá o desconto estrutural, sem somá-lo novamente.</p><p>PCLD oficial: ${cash(data.pcld.officialCents)}. PCLD incluída no custo gerencial: ${cash(data.pcld.managementIncludedCents)}; inadimplência de 4,5% aplicada uma vez ao ticket.</p><p>Receitas institucionais: ${cash(data.institutionalRevenue.monthlyCents)} — preservadas no documental, pendentes de critério gerencial.</p></section><section class="card" style="margin-top:16px"><h2>Memórias por turma</h2>${memories}</section>`;
  }
  if(typeof module!=='undefined'&&module.exports){module.exports={renderLayers};return;}
  let snapshot=null,error='',loading=false,sequence=0;
  const legacyShow=showBreakEven,legacyView=breakEvenView,legacyIntegrated=openIntegratedTeachingFinance;
  showBreakEven=async function(){
    if(Number(breakEvenYear)!==2027)return legacyShow();
    const request=++sequence;page='financial';breakEvenOpen=true;snapshot=null;error='';loading=true;render();
    try{const value=await api('break-even/layers?year=2027');if(request!==sequence)return;
      if(value.contractVersion!=='pe-2027-three-layers-v1'||value.rows.length!==41)throw new Error('Contrato de PE incompatível');snapshot=value;
    }catch(ex){if(request===sequence)error=ex.message||'Não foi possível carregar as camadas.';}
    finally{if(request===sequence){loading=false;if(breakEvenOpen)render();}}
  };
  breakEvenView=function(){
    if(Number(breakEvenYear)!==2027)return legacyView();
    if(snapshot)return renderLayers(snapshot);
    return `<section class="card"><h1>Ponto de equilíbrio — três camadas</h1><p role="status">${loading?'Carregando evidências locais…':escape(error||'Evidências ainda não carregadas.')}</p><button class="btn" onclick="showBreakEven()">${loading?'Atualizar':'Tentar novamente'}</button><button class="btn alt" onclick="hideBreakEven()">Voltar</button></section>`;
  };
  openIntegratedTeachingFinance=async function(){
    if(Number(breakEvenYear)===2027){breakEvenOpen=true;await showBreakEven();return;}
    return legacyIntegrated();
  };
})(typeof window!=='undefined'?window:globalThis);
