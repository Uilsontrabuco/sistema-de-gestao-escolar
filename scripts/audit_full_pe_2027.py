"""Relatório reproduzível local; lê extrações já existentes, sem rede ou banco."""
import hashlib
import json
import re
import sys
from pathlib import Path
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pe_full_audit import full_cost_audit, project_real_discounts
from scripts.generate_approved_pe_2027_preview import money

SOURCE = ROOT / 'output/custeio-real-2027/fontes/Orçamento COLEGIO ADVENTISTA DE JUAZEIRO 2027 (1).pdf.txt'
OUT = ROOT / 'output/auditoria-pe-completo-2027'
PARENTS = {'4121000','4121500','4122000','4123000','4124000','4126000',
           '4125000','4129100','4129500','4140000','4190000'}


def amount(text):
    text = text.strip()
    if text == '-':
        return 0
    return int(Decimal(text.replace('.', '').replace(',', '.').replace('(', '-').replace(')', ''))*100)


def budget_accounts():
    text = SOURCE.read_text(encoding='utf-8')
    lines = text.split('PÁGINA 12\n', 1)[1].split('RESULTADO DO EXERCÍCIO', 1)[0].splitlines()
    accounts = []
    page = 12
    for line in lines:
        if line.startswith('PÁGINA '):
            page = int(line.split()[-1])
        match = re.match(r'^(\d{7})\s+(.+?)\s+(\(?[\d.]+,\d{2}\)?|-)\s*(?:(\(?[\d.]+,\d{2}\)?|-))?\s*$', line)
        if not match:
            if re.match(r'^\d{7}\s', line):
                raise ValueError(f'Conta não interpretada: {line}')
            continue
        code, name, monthly, annual = match.groups()
        monthly = amount(monthly)
        is_parent = code in PARENTS
        category = 'D' if is_parent or code.startswith('411') else 'C'
        treatment = 'COMPOSICAO_NAO_SOMAR_NOVAMENTE' if category == 'D' else 'DENTRO_DO_ENVELOPE_GERAL'
        if code.startswith('3'):
            category, treatment = 'E', 'RECEITA_OU_DEDUCAO_DE_RECEITA_NAO_E_DESPESA'
        elif code == '4124001':
            category, treatment = 'E', 'PRESERVADA_ORCAMENTO_NEUTRALIZADA_PE'
        elif code in ('4126005','4126007'):
            category, treatment = 'F', 'PRESERVADA_ATE_CONCILIACAO_COM_DESCONTOS_NO_TICKET'
        elif not monthly and not is_parent:
            category, treatment = 'E', 'SEM_VALOR_ORCADO'
        accounts.append(dict(id=f'{page}/{len(accounts)+1}/{code}', code=code, description=name.strip(), monthlyCents=monthly,
                             annualCents=amount(annual) if annual else None,
                             category=category, treatment=treatment, isParent=is_parent,
                             sourcePage=page))
    # O PDF repete 3195130 para Subvenção/Dízimo (zero) e Outras Subvenções.
    # Não colapsar linhas pelo código: preservar descrição, valor e identidade.
    for account in accounts:
        account['repeatedSourceCode'] = sum(a['code'] == account['code'] for a in accounts) > 1
    return accounts


def render(data):
    s = data['summary']
    m = lambda n: money(round(n*100))
    lines = ['# Auditoria do custo completo e PE 2027 — 41 turmas', '',
             '**PE NÃO FECHADO DOCUMENTALMENTE.** Cálculo local provisório com conciliação aritmética em centavos.', '',
             'A capacidade homologada de 1.103 vagas e as 41 turmas foram preservadas. '
             'A prévia aprovada de 18/09 permanece intacta. Esta camada inclui o saldo de pessoal institucional '
             'no custo econômico de cada turma por capacidade, após deduzir todos os custos já atribuídos. '
             'A alocação gerencial não cria lotação de funcionário nem comprova a composição nominal do saldo.', '',
             '## Conciliação', '',
             f"- A) Total mensal gerencial distribuído: **{m(s['classAttributedMonthly'])}**.",
             f"- B) Custo anual correspondente (12 meses): **{m(s['managerialAnnual'])}**.",
             f"- C) Rateios e parcelas compartilhadas: **{m(s['allocationsMonthly'])}**.",
             f"- Docentes: {m(s['teachingMonthly'])}; outros diretos, incluindo residuais: {m(s['otherDirectMonthly'])}.",
             f"- D) Orçamento mensal {m(s['officialTotalMonthly'])} − PCLD {m(s['pcldNeutralizedMonthly'])} = {m(s['managerialPETotalMonthly'])}.",
             f"- Antes: {m(s['priorClassAttributedMonthly'])} nas turmas + {m(s['institutionalAllocatedMonthly'])} fora das turmas. Agora: saldo não distribuído **R$ 0,00**.",
             f"- Anual documental oficial: {m(s['officialAnnual'])}; mensal oficial × 12: {m(s['officialMonthlyTimes12'])}. Diferença documental preservada: {s['annualRoundingDifferenceCents']} centavos.",
             '- Blocos R$ 267.630,16 e R$ 119.961,77 compõem R$ 387.591,93 de pessoal. Nenhum deles foi adicionado novamente.',
             '- A soma dos valores mensais impressos das contas analíticas apresenta arredondamento em relação aos totais. Ver diferenças explícitas abaixo; não houve ajuste oculto em conta nominal.', '',
             '## Premissas e receitas', '',
             'Mensalidades: EI 930,69; FI 964,67; FII 1.239,81 (fonte oficial, p. 2); EM 1º/2º 1.425,59; EM 3º 1.461,05. '
             'Ticket mensal = mensalidade × 0,97 × 0,955, arredondado por aluno em centavos. '
             'Desconto estrutural de 3% e inadimplência de 4,5% mantidos. Docentes = custo semanal aprovado × 4,5, '
             'arredondado por turma; nenhuma nova incidência de DSR, encargos ou conversão de duração foi aplicada.', '',
             'São 11 mensalidades, de fevereiro a dezembro. A matrícula de janeiro permanece separada, sem amortização '
             'no ticket mensal, conforme contrato atual de financial_integration.py. Receita na capacidade = ticket × vagas; '
             'não usa matrículas atuais. A receita anual de mensalidades é 11 × a receita mensal, enquanto o custo anual é 12 × o custo mensal. '
             'O resultado anual antes da matrícula está no JSON; o resultado mensal não deve ser multiplicado por 12 como previsão anual.', '',
             'Receitas financeiras, subvenções e receitas educacionais do orçamento são referências institucionais, '
             'não despesas nem receitas recorrentes inventadas por turma. O PE publicado no documento usa outra base '
             '(1.065 alunos planejados, gratuidades e outras receitas), portanto não equivale ao PE estrutural desta auditoria.', '',
             '## Tabela das 41 turmas', '',
             'Valores monetários em R$. Outros diretos incluem estagiárias, Maria Edna e residuais diretos preservados. '
             'Rateios incluem auxiliares/coordenação do segmento, gerais líquidos da PCLD e saldo institucional. '
             '**P = provisório: aritmética conciliada, fechamento documental pendente.**', '',
             '| Turma | Cap. | Mensalidade | Ticket | Docentes/mês | Outros diretos | Rateios | Custo/mês | PE alunos | PE % | Margem física | Receita capacidade | Resultado capacidade | Auditoria |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in data['classes']:
        values = [r['class'], str(r['capacity'])] + [m(r[k]).replace('R$ ', '') for k in
                  ('grossTuition','netTicket','teachingCostMonthly','directCostsIncludingResidualMonthly','allocationsMonthly','totalCostMonthly')]
        values += [str(r['breakEvenStudents']),f"{r['breakEvenPercentCapacity']:.2f}%",str(r['physicalMarginStudents']),
                   m(r['capacityRevenueMonthly']),m(r['capacityResultMonthly']),'P']
        lines.append('| '+' | '.join(values)+' |')
    lines += ['', f"Soma dos PEs individuais: **{s['sumClassBreakEvenStudents']} alunos**; {s['aboveCapacity']} turmas acima da capacidade. "
              'Essa soma não é um PE global independente da composição de alunos por turma.',
              f"Receita mensal líquida na capacidade: **{m(s['capacityRevenueMonthly'])}**; resultado mensal: **{m(s['capacityResultMonthly'])}**.", '',
              '## E) Diferenças e verificações', '',
              '- Corrigida, na camada nova, a exclusão de R$ 202.296,04 de pessoal institucional dos PEs individuais. O total econômico global não aumentou.',
              '- Custos diretos, rateios e PCLD aparecem em razão exclusivo, com identificadores únicos e soma exata. Contas sintéticas/controles nominais não são somados ao razão.',
              '- G2 A/G2 B mantêm seus residuais e lotações; o novo PE passa a refletir também o pessoal institucional. Não houve retorno à regra antiga de substituir lotações comprovadas por rateio global.',
              '- G3 A/G3 B preservam diferenças docentes da fonte e o posto adicional de Paula continua sem custo estimado.',
              '- EM preserva o custo docente de R$ 6.410,25 por turma, reconciliação da matriz 2026 validada para projeção 2027. O custo completo acrescenta as parcelas compartilhadas e institucionais.',
              '- Aulas e docentes não aumentam automaticamente com capacidade; turmas de tamanhos diferentes podem ter a mesma grade. A capacidade influencia os rateios, não cria aulas adicionais.',
              '- Achado adicional: contas 4126005 e 4126007 somam R$ 177.901,08/mês dentro das despesas. A possível sobreposição com reduções de receita precisa de memória contábil; não foi neutralizada por suposição.',
              '- Depreciação está preservada como custo econômico; isenções e receitas não foram adicionadas como despesa.', '',
              '- Lohana/Marcelo: excluídos dos 50 docentes projetados, mas ainda identificados na memória histórica de postos da grade. O JSON registra as ocorrências com projectedTeacher=null; custos estruturais homologados são preservados, sem atribuir esses postos a Telma/Julianne por inferência.',
              '- O código 3195130 aparece duas vezes no PDF: Subvenção/Dízimo sem valor e Outras Subvenções. Ambas as linhas foram preservadas com identificadores distintos; nenhuma foi somada como despesa.', '',
              '## Razão das contas de receita e despesa', '',
              'A direto; B compartilhado; C institucional; D já incluído em outro bloco; E não aplicável como custo adicional; F pendente. '
              'Esta tabela documental NÃO se soma ao razão econômico distribuído. Contas 411 detalham a composição do pessoal já capturado e do seu saldo institucional.', '',
              '| Conta | Descrição | Mensal | Classe | Tratamento | Fonte/página |',
              '|---|---|---:|---|---|---:|']
    for a in data['budgetAccounts']:
        lines.append(f"| {a['code']} | {a['description']} | {money(a['monthlyCents'])} | {a['category']} | {a['treatment']} | {a['sourcePage']} |")
    lines += ['', 'Conciliação dos valores analíticos impressos (centavos):', '',
              '```json', json.dumps(data['accountReconciliation'], ensure_ascii=False, indent=2), '```', '',
              '## F) Lista única de documentos indispensáveis ao fechamento', '',
              '1. Custo mensal completo de Paula Araujo Dias, posto adicional do G3 B, e indicação de sua inclusão ou não no envelope de pessoal.',
              '2. Memória nominal dos residuais G2 A (R$ 3.874,33) e G2 B (R$ 3.897,46), identificando verbas já capturadas em docentes, auxiliares e coordenação.',
              '3. Ponte nominal do envelope de pessoal 2027 para os custos diretos e o saldo institucional de R$ 202.296,04, com folha-base de agosto e identificação dos postos. Deve preservar Telma/Julianne, Lohana apenas auxiliar de coordenação, Marcelo não docente, Jailane em substituição a Romilton e Veroneide como vaga nova. Identificar os docentes atuais dos postos ainda associados historicamente a Lohana/Marcelo, sem duplicar seu custo. Os controles agregados existentes não comprovam ausência de sobreposição por pessoa.',
              '4. Conciliação das contas 4126005/4126007 (R$ 177.901,08/mês) com descontos/gratuidades lançados na receita, incluindo o desconto estrutural de 3%, para definir eventual neutralização no PE e evitar duplicação na próxima importação.', '',
              '## G) Testes e integridade', '',
              'Ver TESTES.md, logs e integridade.json nesta pasta. Testes aprovados certificam as regras e somas verificadas; não resolvem as pendências documentais acima.', '',
              '## H) Descontos reais', '',
              '**As 41 turmas NÃO estão liberadas como base financeira definitivamente validada para a importação oficial dos descontos reais.** '
              'O contrato local de projeção está preparado e testado: mantém PE estrutural, ticket/receita projetada, impacto de descontos, ocupação e margem em campos separados. '
              'Dados incompletos ficam pendentes; desconto real substitui os 3% na projeção e a inadimplência incide uma única vez. '
              'A planilha Descontos_2027_CAJ_Progressao_Series_Atualizada.xlsx não foi aberta nem importada. O leitor XLSX e a ligação à interface ficam para a etapa de importação.', '',
              'Não houve deploy, push, acesso remoto ao Supabase ou alteração de dados de produção. '
              'O módulo homologado e a prévia anterior não foram reescritos. Os relatórios usam as extrações e decisões locais existentes; '
              'não equivalem a uma reextração dos originais ausentes nem a uma consulta da base remota atual.', '']
    return '\n'.join(lines)


def main():
    data = full_cost_audit()
    data['budgetAccounts'] = budget_accounts()
    leaf = [a for a in data['budgetAccounts'] if not a['isParent'] and a['code'].startswith('4')]
    personnel = sum(a['monthlyCents'] for a in leaf if a['code'].startswith('411'))
    general = sum(a['monthlyCents'] for a in leaf if not a['code'].startswith('411'))
    data['accountReconciliation'] = dict(personnelAnalyticMonthlyCents=personnel,
        personnelEnvelopeMonthlyCents=38759193, personnelPrintedRoundingCents=38759193-personnel,
        generalAnalyticMonthlyCents=general, generalEnvelopeMonthlyCents=45389503,
        generalPrintedRoundingCents=45389503-general,
        revenueAnalyticMonthlyCents=sum(a['monthlyCents'] for a in data['budgetAccounts'] if a['code'].startswith('3')),
        revenueOfficialMonthlyCents=90515216,
        expenseAnalyticAnnualCents=sum(a['annualCents'] or 0 for a in leaf),
        expenseOfficialAnnualCents=1009784357,
        note='Ajustes de impressão preservados no envelope; nenhuma conta nominal corrigida por inferência.')
    data['discountProjection'] = project_real_discounts(data)
    data['sourceExtractionSha256'] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'auditoria.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT/'RELATORIO.md').write_text(render(data), encoding='utf-8')
    print(json.dumps(dict(summary=data['summary'], accounts=len(data['budgetAccounts']),
                         reconciliation=data['accountReconciliation']), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
