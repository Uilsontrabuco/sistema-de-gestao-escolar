/* Registros do navegador preservados, sem inventar destinatários ou aprovações. */
(() => {
  'use strict';
  const originalBenefits = benefits;
  const originalRequests = requests;
  const originalBudget = budget;
  const originalDelinquency = delinquency;
  benefits = function () {
    const records = S.recoveredLegacy?.benefits || [];
    const rows = records.map(r => `<tr><td>${e(r.student)}</td><td>${e(r.parent)}</td><td>${e(r.className)}</td><td>${e(r.benefit)}</td><td>${money(r.value)}</td><td>${e(r.status)}</td><td>${e(r.date)}</td></tr>`).join('');
    return originalBenefits() + (records.length ? '<h2>Entregas recuperadas</h2><p>Registros originais preservados. Não representam uma concessão nova de desconto.</p>' + table(['Aluno','Responsável','Turma','Benefício','Valor registrado','Situação','Data'], rows, 7, '') : '');
  };
  requests = function () {
    const records = S.recoveredLegacy?.requests || [];
    const rows = records.map(r => `<tr><td>${e(r.protocol)}</td><td>${e(r.requester)}</td><td>${e(r.title)}</td><td>${e(r.destination)}</td><td>${e(r.status)}</td><td>${e(r.detail)}</td><td>${e(r.date)}</td></tr>`).join('');
    return originalRequests() + (records.length ? '<h2>Solicitações recuperadas</h2><p>Histórico original preservado. O cadastro antigo não identifica o destinatário individual; nenhuma aprovação ou atribuição foi criada.</p>' + table(['Protocolo','Solicitante','Título','Setor','Situação','Detalhes','Data'], rows, 7, '') : '');
  };
  budget = function () {
    const notice = S.budget?.some(r => r.sourceStatus === 'recovered_unverified')
      ? '<p class="notice">Os valores recuperados do navegador ainda precisam de conferência documental. Não constituem orçamento certificado nem evidência para um ponto de equilíbrio definitivo.</p>' : '';
    const records = S.recoveredLegacy?.imports || [];
    const rows = records.map(r => `<tr><td>${e(r.type)}</td><td>${e(r.file)}</td><td>${e(r.date)}</td><td>${e(r.detail)}</td></tr>`).join('');
    return notice + originalBudget() + (records.length ? '<h2>Histórico de importações recuperado</h2>' + table(['Tipo','Arquivo','Data','Resultado registrado'], rows, 4, '') : '');
  };
  delinquency = function () {
    const recovered = S.recoveredLegacy?.delinq;
    if (!recovered) return originalDelinquency();
    const rows = Object.entries(recovered).map(([key,value]) => `<tr><td>${e(key)}</td><td>${e(value)}</td></tr>`).join('');
    return originalDelinquency() + '<h2>Indicadores recuperados do navegador</h2><p>Proveniência preservada; valores sem documento de suporte não foram certificados.</p>' + table(['Indicador original','Valor registrado'],rows,2,'');
  };
})();
