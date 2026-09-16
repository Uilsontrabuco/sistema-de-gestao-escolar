/* Consulta financeira 2027. Sem gravações, mensalização presumida ou credenciais. */
(function(root){
  'use strict';
  const YEAR=2027, WEEKLY=2567735;
  const validInt=n=>Number.isSafeInteger(n)&&n>=0;
  const canonical=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase().replace(/[^A-Z0-9]/g,'');
  const fail=message=>{throw new Error(message);};
  const check=(condition,message)=>{if(!condition)fail(message);};
  function cents(n){
    check(typeof n==='number'&&Number.isFinite(n)&&n>=0,'Valor monetário inválido');
    const result=Math.round((n+Number.EPSILON)*100);
    check(Number.isSafeInteger(result),'Valor fora do limite');return result;
  }
  function ceilPE(cost,net,students){
    if(cost==null||net==null||!students||net<=0)return null;
    check(validInt(cost)&&validInt(net)&&validInt(students),'Base de PE inválida');
    return Number((BigInt(cost)*BigInt(students)+BigInt(net)-1n)/BigInt(net));
  }
  function validateLedger(ledger){
    check(ledger?.target_year===YEAR&&ledger.validated_cost_cents===WEEKLY,'Custeio fora do fechamento 2027');
    check(ledger.conflicted_cost_cents===0&&ledger.unassigned_cost_cents===0,'Custeio com pendência financeira');
    const s=ledger.summary;
    check(s?.reconciled_professors===50&&s.financial_duplicates===0&&s.unexplained_cost_cents===0,'Fechamento não conciliado');
    check(ledger.classes?.length===41,'O custeio deve conter 41 turmas');
    check(new Set(ledger.classes.map(r=>canonical(r.class_name))).size===41,'Turmas duplicadas');
    check(ledger.classes.reduce((sum,r)=>sum+cents(r.weekly_cost),0)===WEEKLY,'Soma semanal divergente');
    check(Array.isArray(ledger.occurrences)&&ledger.occurrences.length===1235,'Rastreabilidade documental incompleta');
    for(const occurrence of ledger.occurrences){
      check([40,45,50].includes(occurrence.duration_minutes),'Duração documental alterada');
      let numerator=0n,denominator=1n;
      for(const a of occurrence.allocations){
        const n=a.financial_fraction_numerator,d=a.financial_fraction_denominator;
        check(validInt(n)&&Number.isSafeInteger(d)&&d>0,'Fração inválida');
        numerator=numerator*BigInt(d)+BigInt(n)*denominator;denominator*=BigInt(d);
      }
      // Non-anchor documentary records in a shared pool have no financial allocation.
      if(occurrence.allocations.length)check(numerator===denominator,'Rateio diferente de 100%');
    }
    const allocations=ledger.operational_allocations;
    check(Array.isArray(allocations)&&new Set(allocations.map(a=>a.allocation_id)).size===allocations.length,'Parcela financeira duplicada');
    check(allocations.reduce((sum,a)=>sum+a.validated_cost_cents,0)===WEEKLY,'Parcelas financeiras não conciliam');
    return ledger;
  }
  function verified(r){return r?.status==='verified'&&typeof r.source==='string'&&r.source.trim().length>0;}
  function moneyEvidence(r,period='monthly'){return verified(r)&&r.period===period&&validInt(r.amountCents)?r.amountCents:null;}
  function revenueEvidence(r,students){
    if(!verified(r)||r.period!=='monthly')return null;
    // Individualized records take precedence over any aggregate; no default discounts.
    if(Array.isArray(r.students)){
      if(r.students.length!==students||new Set(r.students.map(x=>x.id)).size!==students)return null;
      let sum=0;
      for(const x of r.students){
        if(!x.id||!validInt(x.tuitionCents)||!validInt(x.discountBasisPoints)||x.discountBasisPoints>10000)return null;
        sum+=Number((BigInt(x.tuitionCents)*BigInt(10000-x.discountBasisPoints)+5000n)/10000n);
      }
      return sum;
    }
    // Only an explicitly documented aggregate for the same student population.
    return r.studentCount===students?moneyEvidence(r):null;
  }
  function snapshot(ledger,turmas,evidence){
    validateLedger(ledger);
    check(Array.isArray(turmas)&&turmas.length===41,'Cadastro Supabase deve conter exatamente 41 turmas');
    check(new Set(turmas.map(r=>r.id)).size===41&&turmas.every(r=>r.id),'IDs de turmas duplicados ou ausentes');
    const names=turmas.map(r=>canonical(`${r.serie} ${r.turma}`));
    check(new Set(names).size===41,'Nomes de turmas ambíguos; confirme o vínculo');
    const mapped=ledger.classes.map(r=>{
      const index=names.indexOf(canonical(r.class_name));
      check(index>=0,`Turma não vinculada: ${r.class_name}`);
      const room=turmas[index];
      check(validInt(room.capacidade)&&validInt(room.matriculados),'Capacidade ou alunos inválidos');
      return {room,closed:r};
    });
    const approved=evidence?.year===YEAR&&verified(evidence);
    const details=approved&&Array.isArray(evidence.classes)?evidence.classes:[];
    const sourceCounts=new Map();
    for(const d of details)if(verified(d.totalCost))sourceCounts.set(d.totalCost.economicSourceId,(sourceCounts.get(d.totalCost.economicSourceId)||0)+1);
    const rows=mapped.map(({room,closed})=>{
      const matches=details.filter(d=>d.classId===room.id);
      const d=matches.length===1?matches[0]:{};
      const population=verified(d.population)&&d.population.year===YEAR&&d.population.studentCount===room.matriculados;
      const net=population?revenueEvidence(d.recurringRevenue,room.matriculados):null;
      const uniqueSource=d.totalCost?.economicSourceId&&sourceCounts.get(d.totalCost.economicSourceId)===1;
      const cost=uniqueSource?moneyEvidence(d.totalCost):null;
      const pe=ceilPE(cost,net,room.matriculados);
      return {id:room.id,name:closed.class_name,students:room.matriculados,capacity:room.capacidade,
        vacancies:Math.max(0,room.capacidade-room.matriculados),occupancy:room.capacidade?room.matriculados/room.capacidade*100:null,
        weeklyCents:cents(closed.weekly_cost),weeklyMinutes:closed.weekly_minutes,monthlyTeachingCents:null,
        revenueCents:net,totalCostCents:cost,resultCents:net!=null&&cost!=null?net-cost:null,
        otherDirectCents:moneyEvidence(d.otherDirect),indirectCents:moneyEvidence(d.indirect),
        pe,margin:pe==null?null:room.matriculados-pe,studentsNeeded:pe==null?null:Math.max(0,pe-room.matriculados),
        pending:[!population&&'Matrículas do exercício não comprovadas',net==null&&'Receita líquida recorrente não comprovada',cost==null&&'Custo mensal exclusivo da turma não comprovado'].filter(Boolean)};
    });
    const expense=approved?moneyEvidence(evidence.totalExpenses):null;
    const net=rows.every(r=>r.revenueCents!=null)?rows.reduce((a,r)=>a+r.revenueCents,0):null;
    const students=rows.reduce((a,r)=>a+r.students,0);
    const pe=ceilPE(expense,net,students);
    return {year:YEAR,weeklyCents:WEEKLY,weeklyDifferenceCents:rows.reduce((a,r)=>a+r.weeklyCents,0)-WEEKLY,
      monthlyTeachingCents:null,tuitionInstallments:11,additionalExpenseCents:0,
      totalExpensesCents:expense,recurringRevenueCents:net,
      enrollmentRevenueCents:approved?moneyEvidence(evidence.enrollmentRevenue,'year'):null,
      students,pe,margin:pe==null?null:students-pe,resultCents:expense!=null&&net!=null?net-expense:null,
      above:rows.filter(r=>r.margin>0).length,at:rows.filter(r=>r.margin===0).length,
      below:rows.filter(r=>r.margin!=null&&r.margin<0).length,undetermined:rows.filter(r=>r.pe==null).length,
      rows,source:evidence?.source||null};
  }
  async function load(client){
    check(client?.auth,'Conexão Supabase não configurada');
    const auth=await client.auth.getUser();
    check(!auth.error&&auth.data?.user?.id,'Entre com sua conta Supabase');
    const profile=await client.from('profiles').select('id,role,ativo').eq('id',auth.data.user.id).single();
    check(!profile.error&&profile.data?.ativo===true&&profile.data.role==='master','Consulta financeira restrita ao Master ativo');
    async function pages(table,fields){
      const all=[];
      for(let start=0;;start+=500){
        const r=await client.from(table).select(fields).order('id').range(start,start+499);
        check(!r.error,`Leitura de ${table} indisponível; confira configuração e permissões`);
        check(Array.isArray(r.data),'Resposta de leitura inválida');all.push(...r.data);if(r.data.length<500)return all;
      }
    }
    const [turmas,closed,plan]=await Promise.all([
      pages('turmas','id,serie,turma,capacidade,matriculados'),
      client.from('teaching_cost_snapshots').select('version,payload').eq('year',YEAR).eq('status','approved').order('version',{ascending:false}).limit(1).maybeSingle(),
      client.from('financial_evidence').select('version,snapshot_version,payload').eq('year',YEAR).eq('status','approved').order('version',{ascending:false}).limit(1).maybeSingle()
    ]);
    check(!closed.error&&closed.data?.payload,'Fechamento docente ainda não disponibilizado no Supabase');
    check(Number.isSafeInteger(closed.data.version)&&closed.data.version>0,'Versão do fechamento inválida');
    const compatible=!plan.error&&Number.isSafeInteger(plan.data?.version)&&plan.data.version>0&&plan.data.snapshot_version===closed.data.version;
    const data=snapshot(closed.data.payload,turmas,compatible?plan.data?.payload:null);
    data.evidenceUnavailable=Boolean(!compatible||!plan.data?.payload);
    data.snapshotVersion=closed.data.version;
    return data;
  }
  const api=Object.freeze({validateLedger,snapshot,load,ceilPE,revenueEvidence,canonical});
  if(typeof module==='object'&&module.exports)module.exports=api;else root.Seven7Finance=api;
})(typeof window==='undefined'?globalThis:window);
