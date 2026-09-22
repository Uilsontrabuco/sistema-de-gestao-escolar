"""Relatório único das 41 turmas usando o mesmo motor da interface local."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pe_layers import build_layers
OUT=ROOT/'output/arquitetura-pe-2027'


def money(cents):
    return 'PENDENTE' if cents is None else f'{cents/100:,.2f}'.replace(',','X').replace('.',',').replace('X','.')


def main():
    d=build_layers();s=d['summary'];OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'camadas.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Arquitetura do PE 2027 — três camadas', '',
        '**ARQUITETURA DO PE 2027 VALIDADA** após a execução registrada em TESTES.md. '
        '**PE gerencial 2027 ainda não documentalmente fechado.**', '',
        'A interface e a rota local autenticada `/api/break-even/layers?year=2027` usam o mesmo motor `pe_layers.py`. '
        'A fonte empacotada é independente dos diretórios temporários/relatórios, e não contém credenciais. '
        'As rotas antigas permanecem para compatibilidade e testes; a interface PE 2027 apresenta somente a arquitetura nova, '
        'inclusive ao abrir a integração financeira. Não houve migração ou gravação de dados escolares.', '',
        '## Contratos e limites', '',
        '**A — Orçamentário:** preserva alunos previstos, mensalidades, outras receitas, gratuidades/convênios, desconto '
        'comercial, receita líquida, custos, fórmula, fonte/página e PE impresso. O teto solicitado nesta execução é '
        'armazenado separadamente e aparece junto ao número impresso. Em 17 turmas, divergem: o teto fica PENDENTE DOCUMENTAL '
        'até comprovação da precisão/fórmula da planilha geradora 2027. Nenhum PDF ou relatório anterior foi reescrito. '
        'G2 A/B continuam 15 em ambos. Não se aplica 4,5% à receita p. 4 nem se estorna PCLD nesta camada.', '',
        '**B — Gerencial:** ticket = mensalidade oficial × 0,97 × 0,955, uma vez; PE = teto(custo comprovado / ticket). '
        'A base comprovada usa os cinco componentes homologados: docentes, estágio, auxiliar direta, auxiliares de segmento '
        'e coordenação de segmento. O custeio docente permanece o homologado; os custos nominais são da base agosto/2026, '
        'com lotações/critérios já aprovados C02/C28/C29. Isto comprova a base usada, não a suficiência de todo o custo 2027. '
        'Não foram promovidos residuais ou saldo institucional a custo comprovado.', '',
        'Os rateios nominais já aprovados ficam congelados na base homologada; mudar capacidade na análise altera apenas '
        'PE%, margem física e receita/resultado na capacidade, não redistribui custos automaticamente. Nova regra de rateio '
        'dependerá de evidência e versão própria. Os demais valores ficam em CUSTO PENDENTE DE COMPROVAÇÃO. '
        'A simulação provisória mantém o total anterior e não decreta inviabilidade física.', '',
        '**C — Projeção real:** estrutura preparada, sem alunos/descontos importados. Quantidade, receita, ticket médio, '
        'impacto dos descontos, margem e distância ao PE permanecem desconhecidos, não zero. O contrato futuro exige base '
        'completa, cobertura reconciliada com fonte e identidade única por evento econômico. Bolsas, gratuidades e descontos '
        'são benefícios por aluno/período; seu total substitui os 3%, com inadimplência uma vez. A projeção calcula margem '
        'contra custos comprovados parciais e não modifica nenhum PE estrutural. Distância em alunos ao PE não garante '
        'equilíbrio quando o ticket real for diferente: a margem é apresentada separadamente.', '',
        '## Tabela única das 41 turmas', '',
        'Valores mensais em R$. PE Orçamentário = teto reconstruído **[PDF impresso]**. A diferença é gerencial comprovado '
        'menos teto orçamentário. “Comprovado” refere-se à base parcial: nenhuma turma tem cobertura de custo completa. '
        'PE%, margem física e resultado na capacidade usam a base comprovada. Custo pendente é o montante conhecido; '
        'Paula permanece também como pendência sem valor, nunca custo zero presumido.', '',
        '| Turma | Cap. | PE Orçamentário [PDF] | PE Gerencial comprovado¹ | PE provisório | Δ doc × gerencial | Custo documental | Custo comprovado¹ | Custo pendente conhecido | Ticket | PE %¹ | Margem física¹ | Status | Observação |',
        '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|']
    for r in d['rows']:
        a=r['documentary'];b=r['managerial'];p=r['provisional'];src=a['sourceValues']
        doc=f"{a['pe']} [{a['printedPE']}]" if a['pe'] is not None else 'SEM CORRESPONDÊNCIA'
        note=a['status']+'; custos incompletos'
        if r['pendingCosts']['unknownItems']:note+='; Paula sem valor'
        if p['aboveCapacityWarning']:note+='; provisório acima da capacidade, sem inviabilidade definitiva'
        cells=[r['name'],str(r['capacity']),doc,str(b['pe']),str(p['pe']),str(r['documentaryManagerialDifference']) if r['documentaryManagerialDifference'] is not None else 'ND',
            money(round(float(src['totalCost'])*100)) if src else 'PENDENTE',money(b['costCents']),money(r['pendingCosts']['knownCents']),money(b['ticketCents']),
            f"{b['percentCapacity']:.1f}%",str(b['physicalMargin']),r['status'],note]
        lines.append('| '+' | '.join(cells)+' |')
    lines += ['', '¹ Base comprovada parcial. Uma margem física ou econômica positiva aqui não certifica viabilidade integral.', '',
        '## Consolidação A–K', '',
        f"A. **{s['printedDocumentaryConfirmed']} valores impressos comprovados**; {s['documentaryConfirmed']} tetos coincidem com o impresso e estão COMPROVADOS; 17 tetos têm divergência de formatação/precisão pendente.",
        f"B. **{s['managerialConfirmed']} PEs calculados exclusivamente sobre bases comprovadas parciais**; **{s['managerialCompletelyClosed']} PEs com cobertura de custos documentalmente fechada**.",
        f"C. **{s['provisional']} cenários provisórios**, separados dos demais indicadores.",
        f"D. **{s['pendingDocumentary']} turmas com pendência de custo**; esses contadores não são categorias mutuamente exclusivas.",
        f"E. **{s['unmatched']} turmas sem correspondência financeira documental direta:** 1º D, 2º D, 3º D e 8º C. As linhas 7º C e 3º EM B permanecem no arquivo de origem, sem transferência para outra turma.",
        f"F. **{s['physicallyInfeasible']} turmas comprovadamente inviáveis fisicamente** pela base comprovada disponível. Isso não comprova viabilidade final das demais.",
        f"G. **Custos comprovados da base: R$ {money(s['verifiedMonthlyCents'])}/mês.**",
        f"H. **Custos pendentes conhecidos: R$ {money(s['pendingKnownMonthlyCents'])}/mês**, mais uma posição sem valor (Paula). "
        f"Não são despesas novas: comprovados + pendentes conhecidos = R$ {money(s['provisionalMonthlyCents'])}, total gerencial histórico preservado.",
        'I. **PCLD:** R$ 42.117,80 preservados no documental; R$ 0,00 adicionados ao gerencial, cujo ticket já considera 4,5% de inadimplência. '
        'A razão provisória parte da base anterior já neutralizada, sem novo estorno. Testes rejeitam segunda incidência.',
        'J. **Descontos:** R$ 177.901,08 das contas 4126005/4126007 permanecem dentro dos custos pendentes, '
        'não são somados novamente à pendência nem entram na base comprovada. Status COBERTURA DE DESCONTOS PENDENTE DE RECONCILIAÇÃO. '
        'O importador real não foi executado; não há rota de importação nesta camada. Receitas 3182019/3195130 '
        'permanecem no documental e fora do gerencial, com critério pendente.',
        'K. **Testes:** contagem e logs finais em TESTES.md. As 353 verificações anteriores são repetidas, sem alterar suas expectativas.', '',
        '## G2 — resultado preservado e novas bases explícitas', '',
        '- G2 A: documental 15; gerencial parcial 7 (R$ 5.800,47 ÷ R$ 862,14); provisório 22; pendente conhecido R$ 12.921,10.',
        '- G2 B: documental 15; gerencial parcial 7 (R$ 5.777,34 ÷ R$ 862,14); provisório 22; pendente conhecido R$ 12.944,23.',
        'A base comprovada inclui docentes, estágio nominal, auxiliares de segmento e coordenação com critérios homologados. '
        'Os complementos originais, gerais não conciliados e institucional ficam fora dessa base. '
        'Os R$ 5.178,48 de diferença contra o PDF permanecem na reconciliação anterior; não são o total das pendências '
        'do novo contrato gerencial, porque também há custos agregados originais ainda sem composição.', '',
        '## Interface, segurança e preservação', '',
        'Prévia verificada em navegador com banco temporário, incluindo login, menu PE, 41 linhas e valores G2. '
        'A navegação a partir do Dashboard foi corrigida no adaptador novo. Consultas usam a permissão financeira existente, '
        'sem modificar usuários/permissões. O arquivo privado de evidências não é servido diretamente. '
        'Somente server.py (rota/arquivo estático) e index.html (carregamento do adaptador) recebem mudanças pontuais; '
        'cópias anteriores estão nesta pasta. Módulos de cálculo legados, dados, capacidades e documentos anteriores foram preservados.', '',
        '## Lista única de documentos/informações ainda indispensáveis', '',
        '1. **Memória nominal de custos 2027 por funcionário, rubrica e centro/turma, com encargos/isenções e critérios de rateio.** '
        'Uso: comprovar os residuais, gerais, institucional e a evolução dos custos históricos, sem duplicar as bases já reconhecidas.',
        '2. **Comprovação do custo completo e inclusão orçamentária de Paula e dos postos alterados (Jailane/Romilton e Veroneide).** '
        'Uso: concluir valores hoje ausentes ou mudanças de posto sem presumir salário ou lotação.',
        '3. **Composição por benefício/evento de 4126005/4126007 e relação com 3149026, bolsas e convênios.** '
        'Uso: liberar o reconhecimento único dos descontos no custo ou receita antes da futura projeção real.',
        '4. **Ponte financeira dos custos das turmas D, 8º C, 7º C e 3º EM B.** '
        'Uso: comprovar o destino dos custos agregados, sem copiar ou dividir valores por inferência.', '']
    (OUT/'RELATORIO.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(s))


if __name__=='__main__':main()
