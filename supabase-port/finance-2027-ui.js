/* Extensão somente de consulta: não altera state, autenticação ou persistência. */
(function(){
  'use strict';
  const money=n=>n==null?'Não determinado':(n/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
  const number=n=>n==null?'Não determinado':String(n);
  let requestVersion=0;
  function render(data){
    const rows=data.rows.map(r=>`<tr><td>${esc(r.name)}</td><td>${r.students}</td><td>${r.capacity}</td><td>${r.vacancies}</td><td>${r.occupancy==null?'—':r.occupancy.toFixed(1)+'%'}</td><td>${money(r.weeklyCents)}</td><td>${money(r.revenueCents)}</td><td>${money(r.otherDirectCents)}</td><td>${money(r.indirectCents)}</td><td>${money(r.totalCostCents)}</td><td>${money(r.resultCents)}</td><td>${number(r.pe)}</td><td>${number(r.studentsNeeded)}</td><td>${number(r.margin)}</td><td>${esc(r.pending.join('; ')||'Base documentada')}</td></tr>`).join('');
    document.getElementById('finance2027Result').innerHTML=
      `<div class="grid kpis">${kpi('Docente semanal',money(data.weeklyCents))}${kpi('Despesas mensais existentes',money(data.totalExpensesCents))}${kpi('Receita mensal recorrente',money(data.recurringRevenueCents))}${kpi('PE geral em alunos',number(data.pe))}</div>`+
      `<div class="grid kpis" style="margin-top:16px">${kpi('Matrícula separada',money(data.enrollmentRevenueCents))}${kpi('Resultado mensal',money(data.resultCents))}${kpi('Margem em alunos',number(data.margin))}${kpi('Acima / no / abaixo do PE',`${data.above} / ${data.at} / ${data.below}`,`${data.undetermined} turmas com PE não determinado`)}</div>`+
      `<p class="notice">Custeio semanal fechado. Mensalização docente não determinada. Nenhuma parcela docente é acrescentada às despesas existentes. São 11 mensalidades em 2027; matrícula permanece separada. ${data.pe==null?'Dados insuficientes para o PE geral. ':''}${data.evidenceUnavailable?'Evidências financeiras ausentes ou incompatíveis com a versão do fechamento; valores ausentes não são zero.':''}</p>`+
      `<div class="card tablewrap"><table class="table"><thead><tr>${['Turma','Alunos','Capacidade','Vagas','Ocupação','Docente semanal','Receita mensal','Outros diretos','Indiretos','Custo total mensal','Resultado','PE alunos','Alunos necessários','Margem alunos','Situação'].map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>`+
      `<p>Conciliação semanal: ${money(data.weeklyDifferenceCents)}. Acréscimo às despesas: ${money(data.additionalExpenseCents)}.</p>`;
  }
  window.openFinance2027=async function(){
    if(!session?.uid||session.role!=='Master'){toast('Entre com um perfil Master do Supabase');return;}
    go('finance2027');
    const result=document.getElementById('finance2027Result');result.textContent='Consultando dados autorizados…';
    const userId=session.uid;
    const version=++requestVersion;
    try{
      const data=await Seven7Finance.load(window.seven7Supabase);
      if(version!==requestVersion||session?.uid!==userId||session.role!=='Master')return;
      render(data);
    }catch(error){if(version===requestVersion)result.textContent=error.message;}
  };
  const section=document.createElement('section');section.id='finance2027';section.className='section';
  section.innerHTML='<h2>Custeio docente / PE 2027</h2><p>Consulta ao Supabase. Nenhum lançamento é realizado.</p><div id="finance2027Result"></div>';
  document.querySelector('.content').appendChild(section);
  const originalRenderNav=renderNav;
  renderNav=function(){
    originalRenderNav();
    if(session?.uid&&session.role==='Master'){
      const button=document.createElement('button');button.textContent='Custeio / PE 2027';button.onclick=window.openFinance2027;
      document.getElementById('nav').appendChild(button);
    }
  };
  // Remove rendered financial data on logout; preserve the existing logout flow.
  const originalLogout=logout;
  logout=async function(){requestVersion++;document.getElementById('finance2027Result').textContent='';return originalLogout();};
})();
