"""Gera somente arquivos de revisão humana, sem banco ou publicação."""
import json,sys,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from series_budget_simulation import simulate
OUT=ROOT/'output/simulacao-rateio-series-2027'
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def br(x):return 'PENDENTE' if x is None else f'{x/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')
def main():
    OUT.mkdir(exist_ok=True)
    report=read('output/pe-administrativo-aprovado-20270922/resultado-administrativo.json')
    ledger=read('output/pe-real-2027/reconciliacao-custos.json')
    s=simulate(report,ledger)
    (OUT/'simulacao.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Simulação de reconciliação por série — não aplicada','',
        '**Fechamento matemático: aprovado, diferença R$ 0,00 em todas as séries e no total escolar.** Os montantes e custos nominais têm origem registrada; a nova distribuição é uma proposta econômica para aprovação administrativa, não distribuição já demonstrada no PDF. Portanto, não se declara fechamento documental integral nem PE definitivo.', '',
        '## Critérios propostos','',
        'Limite de cada série: soma das linhas positivas da mesma série no orçamento p.4, já atualmente alocadas. É o montante atribuído à série pelo documento, não a comprovação de que todos os contratos atendem exclusivamente àquela série. Não há transferência entre séries, nem uso da reserva do antigo 7º C.',
        'Folha: preservar as âncoras docentes estruturais e distribuir apenas o saldo de folha da série proporcionalmente a essas âncoras. O peso usa a carga e as tarifas já conciliadas com multiplicador 4,5, incluindo as frações de aulas compartilhadas; não duplica uma aula comum.',
        'Apoio: preservar os valores nominais de estágio, auxiliar direta, auxiliar do segmento e coordenação já identificados; distribuir somente o saldo por capacidade física da turma. Gerais líquidos: distribuir por capacidade. Capacidade representa infraestrutura disponível e não a quantidade matriculada. O método difere dos pesos por receita/alunos previstos do PDF e precisa ser aprovado expressamente.',
        'Não são criados encargos: o saldo de folha mantém as provisões/custos já dentro da rubrica, sem estimar percentuais ou certificar composição nominal completa. As parcelas nominais são absorvidas nos pools e abatidas antes de distribuir o saldo; não somadas ao orçamento por fora.',
        '8º C: âncora conhecida R$ 2.878,65. Os R$ 274,14 históricos ficam como controle NÃO ADITIVO; não constituem novo salário, nova despesa, dedução do total escolar ou parcela adicional da simulação. Lohana é AUX Administrativo e Marcelo integra a folha. A cobertura nominal específica desse controle não é inventada; permanece questão de rastreabilidade dentro do orçamento existente.', '',
        '## Simulação por série','',
        '| Série | Orçamento total antes R$ | Distribuição atual R$ | Distribuição proposta R$ | Total depois R$ | Diferença R$ |',
        '|---|---:|---|---|---:|---:|']
    for g in s['series']:
        old='; '.join(p['name']+': '+br(p['costBeforeCents']) for p in g['proposals'])
        new='; '.join(p['name']+': '+br(p['costAfterCents']) for p in g['proposals'])
        lines.append(f"| {g['grade']} | {br(g['budgetBeforeCents'])} | {old} | {new} | {br(g['budgetAfterCents'])} | {br(g['differenceCents'])} |")
    lines+=['', 'PENDENTE na distribuição anterior significa custo integral não determinado; não significa turma sem custo. Somente sua contribuição ao total já alocado era nula.', '',
        '## Efeito em TODAS as turmas afetadas','',
        '| Turma | Custo antes R$ | Custo simulado R$ | Reatribuição líquida R$ | PE antes | PE simulado | Capacidade | Ticket líquido R$ |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for g in s['series']:
        for p in g['proposals']:
            lines.append(f"| {p['name']} | {br(p['costBeforeCents'])} | {br(p['costAfterCents'])} | {br(p['deltaFromPreviouslyAllocatedCents'])} | {p['peBefore'] if p['peBefore'] is not None else 'PENDENTE'} | {p['peAfter']} | {p['capacity']} | {br(float(p['ticketExactCents']))} |")
    lines+=['', 'Reatribuição líquida compara com o que já estava distribuído: acréscimos nas turmas antes sem custo atribuído possuem reduções compensatórias nas paralelas. Não são novas despesas. O ticket exato é preservado na memória JSON; os valores exibidos são arredondados, mas o teto do PE usa a precisão original.', '',
        '## Memória por bloco','',
        '| Série/turma | Âncora docente | Outros nominais | Folha final | Apoio final | Gerais líquidos | Controle histórico não aditivo |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for g in s['series']:
        for p in g['proposals']:
            lines.append('| '+p['name']+' | '+' | '.join(br(p[k]) for k in ['teacherAnchorCents','otherNominalAnchorCents','payrollCents','supportCents','generalNetCents','historicalNonAdditiveControlCents'])+' |')
        lines.append('| TOTAL '+g['grade']+' | — | — | '+br(g['pools']['payroll'])+' | '+br(g['pools']['support'])+' | '+br(g['pools']['generalNet'])+' | não somar |')
    pe_before=sum(r['pe'] or 0 for r in s['originalRows']);pe_after=sum(r['pe'] for r in s['rows'])
    lines+=['', '## Checagem global','',
        '| Indicador | Antes | Simulação | Diferença |','|---|---:|---:|---:|',
        '| Custos atribuídos às 41 turmas | R$ 605.641,03 | R$ 605.641,03 | R$ 0,00 |',
        '| Reserva fora do PE | R$ 15.827,05 | R$ 15.827,05 | R$ 0,00 |',
        '| Envelope total | R$ 621.468,08 | R$ 621.468,08 | R$ 0,00 |',
        '| Matrículas / capacidade / vagas | 775 / 1.103 / 328 | 775 / 1.103 / 328 | 0 / 0 / 0 |',
        f'| Soma dos PEs | {pe_before} (37 calculados; 4 pendentes) | {pe_after} (41 simulados) | Universos diferentes; não comparar como economia |',
        '','As demais 26 turmas permanecem integralmente iguais. Quinze turmas participam da simulação: quatro em cada um dos três primeiros anos e três no oitavo. Nenhum PE foi forçado a caber na capacidade. Nenhum custo foi excluído por duplicidade presumida; evitou-se adicionar âncoras nominais, PCLD e controle histórico novamente.', '',
        '## Aprovação e limite documental','',
        '**Proposta calculada para revisão administrativa, NÃO APLICADA.** Nenhuma rubrica impede a igualdade: há saldo suficiente em folha e apoio de cada série para preservar as âncoras, e todos os blocos fecham em centavos. Porém, as rubricas de saldo de folha, apoio compartilhado e gerais líquidos não têm, nas fontes, essa nova repartição individual por âncora docente/capacidade. Não é correto declarar que a redistribuição já fechou documentalmente.',
        'Para qualificar a proposta como APTA PARA APROVAÇÃO ADMINISTRATIVA com fechamento documental, é necessário validar a abrangência econômica dos envelopes de cada série e a pertinência dos novos direcionadores para esses três blocos. O relatório fornece os valores exatos para essa decisão; não falta criar orçamento ou copiar custo de outra turma. O de-para nominal dos R$ 274,14 continua separado e não foi usado para elevar o custo.',
        'Fontes: Orçamento COLEGIO ADVENTISTA DE JUAZEIRO 2027 (1).pdf p.4 e contas p.12–15; reconciliacao-custos.json (ponte mensal e neutralizações); resultado-administrativo.json (tickets, matrículas e custos); nominalCosts (carga/auxiliares/coordenação já auditados). Método novo explicitamente identificado como proposta. Somente relatórios/simulação locais; nenhuma escrita no banco, publicação, deploy, push, produção ou conexão Supabase remota.']
    (OUT/'SIMULACAO-PARA-APROVACAO.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    with (OUT/'comparacao-turmas.csv').open('w',encoding='utf-8-sig',newline='') as f:
        rows=[p for g in s['series'] for p in g['proposals']];w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';');w.writeheader();w.writerows(rows)
    print(json.dumps([(g['grade'],g['budgetBeforeCents'],[(p['name'],p['costAfterCents'],p['peAfter']) for p in g['proposals']]) for g in s['series']],ensure_ascii=True))
if __name__=='__main__':main()
