/* Apresenta saldo líquido, inclusive negativo; não altera matrículas ou regras de PE. */
(function(){
  function signedStats(stats){return {...stats,vacancies:stats.capacity-stats.total};}
  if(typeof module!=='undefined'&&module.exports){module.exports={signedStats};return;}
  const previous=M.classStats;
  M.classStats=(state,room)=>signedStats(previous(state,room));
  const previousTotals=totals;
  totals=function(){const t=previousTotals();return {...t,vacancies:t.seats-t.enrolled};};
})();
