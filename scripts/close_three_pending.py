"""Fecha a auditoria documental, preservando motor, banco e PEs existentes."""
import csv,json,hashlib,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from personnel_confirmations_2027 import personnel_evidence
OUT=ROOT/'output/auditoria-tres-pendencias-20270922';OUT.mkdir(exist_ok=True)
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def br(c):return 'PENDENTE' if c is None else f'{c/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')
def main():
    costs=read('output/pe-real-2027/reconciliacao-custos.json')
    report=read('output/pre-publicacao-2027/resultado-final.json')
    people=personnel_evidence()['rows']
    for p in people:
        old=next(x for x in costs['historicalPayroll'] if str(x['code'])==p['employeeId'])
        p.update(historicalDepartment=old['department'],historicalGroup=old['classGroup'],rosterCell=old['rosterCell'],weeklyHours=None,chargesCents=None,confirmedBudgetAccount=None)
    reserve=next(a for a in costs['allocations'] if not a['classId'])
    assert reserve['costCents']==1582705
    assert reserve['payrollCents']+reserve['supportCents']+reserve['generalCents']-reserve['pcldRemovedCents']-reserve['discountReclassifiedCents']==1582705
    assert sum(r['consideredCostCents'] or 0 for r in report['rows'])+reserve['costCents']==62146808
    with sqlite3.connect('file:'+str(ROOT/'data/caj.sqlite3')+'?mode=ro',uri=True) as db:
        payload=db.execute('select payload from state where id=1').fetchone()[0];state=json.loads(payload)
    assert not [b for b in state['benefits'] if b['classId']=='caj-2027-caj-8-c']
    controls=dict(capacity=1103,enrolled=775,new=37,re=738,vacancies=328,costAllocatedCents=60564103,reserveCents=1582705,economicEnvelopeCents=62146808,peKnown=911,peUnknown=4)
    data=dict(status='NO-GO',people=people,reserve=reserve,before=controls,after=controls.copy(),costChangeCents=0,studentTransfers=0,definitivePEChanges=0,
              duplicateAddedCents=0,absenceOfHistoricalDuplicationCertified=False,
              stateSha256=hashlib.sha256(payload.encode()).hexdigest(),backupSha256=hashlib.sha256((ROOT/'output/pre-publicacao-2027/backup-retomada-pessoal-20270922.zip').read_bytes()).hexdigest())
    (OUT/'auditoria.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUT/'alunos-8C-pendentes-identificacao.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f,delimiter=';');writer.writerow(['Controle de pendência (não matrícula)','Nome','Matrícula oficial','Origem','Destino aprovado','Situação'])
        for i in range(1,21):writer.writerow([i,'NÃO IDENTIFICADO','','8º C','','Obter relação nominal e decisão 8º A/B; não é cadastro de aluno'])
    lines=['# GO/NO-GO — três pendências PE 2027','', '**NO-GO.** Auditoria encerrada até obtenção das evidências abaixo. Nenhum PE foi promovido a definitivo por esta execução.','',
    '## 1. Pessoal','',
    '| Pessoa | Salário-base confirmado | Centro/grupo do cadastro histórico | Jornada | Encargos | Cobertura nominal 2027 |',
    '|---|---:|---|---|---|---|']
    for p in people:lines.append(f"| {p['name']} | {br(p['monthlySalaryCents'])} | {p['historicalDepartment']} / {p['historicalGroup']}; {p['rosterCell']} | PENDENTE | PENDENTE | PENDENTE |")
    lines += ['', 'Função atual das três: Auxiliar de Serviços Gerais, confirmação do gestor em 21/09/2026. Paula: cadastro histórico Educação Infantil/C02 e função de estagiária são históricos; função corrigida pelo gestor e posto adicional G3 B preservado. A mudança de função não prova mudança de centro. Jailane/Veroneide: Serviços de Apoio/C27; não atribuídas a uma turma por suposição.',
    'Jailane substitui Romilton/679; não são dois postos. Cadastro histórico de Romilton: Planilha Funcionários - CAJ.xlsx, CAJ!102, Serviço de Apoio/Zeladoria. Suas verbas históricas não provam jornada ou encargos atuais da substituta. Não copiados descontos pessoais, FGTS ou provisões de outro empregado.',
    'Salários somados apenas como referência nominal: R$ 5.071,50. Acréscimo aplicado: R$ 0,00. Custo total e cobertura desconhecidos continuam PENDENTES, não zero. O envelope de pessoal R$ 387.591,93 já contém as contas abaixo; não somar novamente as parcelas nominais. O saldo de estágio R$ 2.863,57 não identifica Paula e não deve ser usado para cobrir automaticamente uma ASG.', '',
    '| Conta orçamentária | Rubrica | Mensal escola | Fonte |','|---|---|---:|---|']
    for a in costs['accounts']:
        if a['code'].startswith('411'):lines.append(f"| {a['code']} | {a['description']} | {br(a['monthlyCents'])} | Orçamento p.{a['sourcePage']} |")
    lines += ['', 'As contas comprovam valores escolares, não cobertura individual. Não foi identificada dupla contagem nominal comprovada que autorizasse estorno. Foi verificada ausência de nova dupla soma nesta execução; não é possível certificar ausência global de duplicidade histórica sem ponte pessoa→conta.', '',
    '## 2. Vinte matriculados do antigo 8º C','',
    'Turmas CAJ 2027 (2).pdf p.1: 8º A 35/22/13; 8º B 28/0/28; 8º C 28/20/8 (capacidade/matriculados/vagas). A versão (1) mostra 19 no C, também sem nomes. Não há prova de transferência posterior para A/B. Mantidos A=35/22/13 e B=28/0/28. Nenhuma capacidade recalculada por suposição.',
    'Os cinco Relatório de alunos por turma*.xlsx têm somente um cabeçalho. Relação de alunos completa*.pdf pertence à Escola Adventista de Jacobina, não ao CAJ. Controle matriculas 2026 contém quadro de expectativa com referência interna a 2023. Nenhuma dessas fontes identifica os vinte de 2027.',
    'A base local não possui estudantes nominais vinculados a esses vinte: enrollments mantém totais/histórico vazio; nenhum benefício está ligado ao 8º C. Lista de controle: alunos-8C-pendentes-identificacao.csv, 20 pendências SEM nomes inventados; não são 20 novos cadastros. Necessária relação nominal oficial CAJ/2027, matrícula e destino aprovado A/B, mais capacidades finais aprovadas.', '',
    '## 3. Reserva de R$ 15.827,05','',
    'Origem: Orçamento 2027 (1).pdf p.4, linha 7º Ano C, segmento Fundamental II, 27 alunos previstos, receita bruta R$ 33.474,86. Não é uma conta contábil individual nem o centro nominal de um empregado. Departamento/centro analítico que vincule toda a parcela aos postos atuais: PENDENTE.',
    'Ponte exata: custo impresso 22.094,01 − ajuste de arredondamento 0,01 − PCLD 1.199,67 − descontos 5.067,28 = 15.827,05. Componentes: folha 5.748,45 + apoio 3.416,95 + gerais 12.928,60 − PCLD 1.199,67 − descontos 5.067,28 = 15.827,05.',
    'Gerais líquidos = R$ 6.661,65. PCLD: conta 4124001. Descontos: contas 4126005/4126007, parcela conjunta; não há divisão nominal certificada por evento. Folha/apoio são blocos da p.4, e contas 411* são a composição escolar das p.12–13; não foi inventada distribuição de cada conta entre os R$ 5.748,45 e R$ 3.416,95.',
    'Critérios já verificados pelo código reconcile_pe_real_costs.py: folha por alunos previstos dentro do segmento; apoio/gerais por receita bruta da p.4. Não foi feito novo rateio. P.8 identifica 7º C em 2027 e 8º C em 2026: falta retificação/de-para financeiro aprovado para beneficiar turma atual. Reserva permanece fora do PE por turma, dentro da conciliação da escola.', '',
    '## Totais antes/depois e impacto','',
    '| Controle | Antes | Depois | Diferença |','|---|---:|---:|---:|']
    for k,v in controls.items():lines.append(f'| {k} | {br(v) if k.endswith("Cents") else v} | {br(v) if k.endswith("Cents") else v} | 0 |')
    lines += ['', 'Cada uma das três pendências teve impacto aplicado de R$ 0,00 e zero transferências. Impacto econômico futuro não mensurado, pois faltam cobertura e destino. Soma do PE calculável 911 não é PE definitivo da escola: há quatro turmas sem numerador completo e composição nominal ainda pendente.', '',
    '## Quadro preservado das 41 turmas','',
    '| Turma | Capacidade | Matriculados | Vagas | Custo atual | PE atual preservado | PE definitivo nesta auditoria |','|---|---:|---:|---:|---:|---:|---|']
    for r in report['rows']:lines.append(f"| {r['name']} | {r['capacity']} | {r['enrolled']} | {r['vacancies']} | {br(r['consideredCostCents'])} | {r['pe'] if r['pe'] is not None else 'PENDENTE'} | Não certificado: {r['status']} |")
    lines += ['', '## Documentos ou decisões ainda necessários','',
    '1. RH/contabilidade: quadro nominal 2027 de Jailane/952, Veroneide/953 e Paula/955 com jornada, demais verbas, encargos e contas/centros que já cobrem cada posto, incluindo substituição de Romilton. Uso: fechar custo total e eliminar eventual dupla contagem.',
    '2. Secretaria/direção: relação nominal dos vinte do antigo 8º C, matrícula oficial, decisão individual A/B e capacidades finais dessas turmas. Uso: transferência comprovada, ocupação, vagas e projeção de receita.',
    '3. Responsável pelo orçamento: retificação/de-para aprovado da linha 7º C/2027 para os centros/turmas atuais, com memória de folha, apoio e gerais. Uso: destinar R$ 15.827,05 sem aproximação.', '',
    'Execução exclusivamente local. Nenhum deploy, push, publicação, conexão Supabase remota ou acesso/alteração de produção. Banco consultado somente em modo de leitura; motor e PEs não editados. Backup anterior preservado por hash. Pesquisa dirigida registra hashes das fontes; arquivos temporários de bloqueio ~$ não são documentos legíveis e não constituem evidência.']
    (OUT/'GO-NO-GO-FINAL.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(data['before']))
if __name__=='__main__':main()
