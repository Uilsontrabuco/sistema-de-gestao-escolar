/* Benefícios previstos não são matrículas; o servidor controla a ativação. */
(function(){
  'use strict';
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const cash=x=>x==null?'Pendente':(x/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
  const managed=b=>b.sourceKind==='planned-2027';
  function summary(state){
    const list=state.benefits.filter(managed);
    return {total:list.length,active:list.filter(b=>b.state==='ATIVO').length,waiting:list.filter(b=>b.linkStatus==='AGUARDANDO_MATRICULA').length,pending:list.filter(b=>!['VINCULADO','AGUARDANDO_MATRICULA'].includes(b.linkStatus)).length};
  }
  function renderPlanned(state){
    const list=state.benefits.filter(managed),s=summary(state);
    if(!s.total)return '';
    const rows=list.map(b=>`<tr><td>${esc(b.studentName)}<br><small>${esc(b.studentId||b.identityKey)}</small></td><td>${esc(state.classes.find(c=>c.id===b.classId)?.name||b.sourceClass)}</td><td>${esc(b.name)}</td><td>${esc((Number(b.rate)*100).toFixed(4).replace(/0+$/,'').replace(/\.$/,''))}%</td><td>${esc(b.state)}</td><td>${esc(b.linkStatus)}</td><td>${cash(b.discountCents)}</td><td>${esc(b.source)} · linha ${b.sourceRow}</td></tr>`).join('');
    return `<section class="card"><h2>Benefícios previstos 2027</h2><p><b>Total de benefícios 2027: ${s.total}</b> · Ativos: ${s.active} · Aguardando matrícula: ${s.waiting} · Pendentes de vínculo: ${s.pending}</p><p>Base antecipada confirmada: benefícios previstos não criam matrícula nem ocupação. A matrícula nominal ativa o mesmo benefício automaticamente, por ID ou nome exato e único, com a mesma turma. Quantidades agregadas não identificam alunos.</p><p>Marcando Vidas: 45% uma vez. Bolsa filantrópica: 50% uma vez. 95% individual documentado: redução única. Os 114 códigos ausentes da estrutura ficam preservados, sem transferência automática.</p><div style="overflow:auto"><table><thead><tr>${['Aluno / ID','Turma 2027','Benefício','Percentual único','Estado','Vínculo','Desconto previsto','Origem'].map(x=>'<th>'+x+'</th>').join('')}</tr></thead><tbody>${rows}</tbody></table></div></section>`;
  }
  if(typeof module!=='undefined'&&module.exports){module.exports={summary,renderPlanned};return;}
  const previous=benefits;
  benefits=function(){
    const original=S,planned=renderPlanned(original);
    // Renderização legada continua disponível para os benefícios gerais manuais.
    try{S={...original,benefits:original.benefits.filter(b=>!managed(b))};return planned+previous();}
    finally{S=original;}
  };
})();
