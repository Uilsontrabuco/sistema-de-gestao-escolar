import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pe_real import AUDIT
from scripts.audit_pe_real import br,val


def main():
    d=json.loads((AUDIT/'resultado.json').read_text(encoding='utf-8'))
    import sqlite3
    from benefits_2027 import is_planned,apply_benefit_view
    from enrollment_2027 import project_current
    with sqlite3.connect(f'file:{(ROOT/"data/caj.sqlite3").as_posix()}?mode=ro',uri=True) as db:
        local=json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
    if any(is_planned(b) for b in local['benefits']):
        d=apply_benefit_view(project_current(d,state=local),local)
        (AUDIT/'resultado.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    s=d['summary'];c=d['costReconciliation']['summary'];e=d['enrollmentSummary']
    lines=['# FECHAMENTO PE REAL 2027','',
        '**BASE:** 41 turmas · 1.103 vagas · 775 matriculados · 37 novos · 738 rematrículas · 328 vagas líquidas. Vagas negativas preservadas.','',
        f"**TOTAL ECONÔMICO A CONCILIAR:** R$ {br(c['managerialBeforeCents'])} antes da substituição das estimativas de descontos (já sem PCLD).",
        f"**TOTAL COMPROVADO EM VALOR/CRITÉRIO E DESTINO:** R$ {br(c['documentedAssignedCents'])}.",
        '**TOTAL NEUTRALIZADO POR DUPLICIDADE:** PCLD R$ 42.117,80, já neutralizada antes desta execução; não abatida novamente. Identidade duplicada de descontos por evento: ainda não determinada.',
        f"**TOTAL FORA DO PE:** R$ {br(c['discountsReclassifiedCents'])} de estimativas orçadas de descontos, substituídas pela base individual, sem apagamento contábil; PCLD R$ 42.117,80 já excluída da abertura.",
        f"**TOTAL PENDENTE DE DESTINO:** R$ {br(c['remainingDestinationPendingCents'])}, mais custos adicionais não mensurados e ponte nominal ainda não fechada.",
        f"**% FINANCEIRO COM DESTINO COMPROVADO:** {c['financeCoverageKnownPercent']:.4f}% do envelope conhecido após reclassificação. Não é confiança estatística nem comprovação nominal completa.",'',
        f"**Ponte dos R$ 623.208,36:** R$ 623.208,36 − R$ {br(c['newlyResolvedNetCents'])} resolvidos financeiramente − R$ 177.901,08 reclassificados = **R$ {br(c['remainingDestinationPendingCents'])}**. A composição integral por conta, segmento, critério e turma está em [DECOMPOSICAO_CUSTOS_2027.md](DECOMPOSICAO_CUSTOS_2027.md).",
        '**Limite:** o orçamento é o alvo financeiro, a folha de agosto é composição histórica. Resolver valor e critério agregado não demonstra a evolução de cada posto/encargo em 2027. Nenhum saldo foi usado para inventar lotação. Os custos nominais homologados não foram somados novamente aos envelopes.','',
        '**Saneamento:** quatro conflitos resolvidos por evidência nominal e cobrança histórica; Marcando Vidas 45% uma única vez e bolsa filantrópica 50%. A concessão composta com percentual individual explícito de 95% é reconhecida uma única vez, sem regra geral de acumulação. Os 114 registros sem turma foram individualizados; nenhum corresponde apenas a uma grafia alternativa das 41 turmas. [Fontes, 114 linhas, quatro resoluções e classificação de cada centavo](SANEAMENTO_DOCUMENTAL.md).',
        '**A–E:** R$ 623.208,36 − A R$ 0,00 − B R$ 0,00 − C R$ 177.901,08 − D R$ 429.480,23 = **E R$ 15.827,05**. D comprova distribuição financeira do orçamento, não identidade nominal; B zero significa nenhuma baixa adicional por evento certificado, não ausência de sobreposição.','',
        'Pessoal: [2.118 linhas de cruzamento nominal por rubrica](PESSOAL_RUBRICAS_2027.md), preservando função, departamento e fonte histórica. 3º EM B/C e demais linhas inativas do médio têm zero alunos e zero custo na p.4; não viram turmas adicionais nem herdam custos. O PDF atual não contém 3º EM B ativo.','',
        '## G2','',
        '**G2 — premissa de planejamento confirmada em 21/09/2026:** desconto de 12% exclusivo dos ingressantes G2 2027 enquanto não existir mix individual. Ticket exato = 930,69 × 0,88 × 0,955 = R$ 782,151876 (exibição R$ 782,15). Inadimplência uma vez; PCLD não reaplicada. O mix individual da própria turma substituirá integralmente os 12%, sem acumulação.','']
    for r in d['rows'][:2]:
        b=r['costBridge']
        lines.append(f"{r['name']}: custo documental R$ {br(b['printedCostCents'])} + ajuste explícito de arredondamento R$ {br(b['roundingBridgeCents'])} − PCLD R$ {br(b['pcldRemovedCents'])} − estimativa de descontos substituída R$ {br(b['discountReclassifiedCents'])} = **custo orçado reconciliado R$ {br(b['costCents'])}**. Folha R$ {br(b['payrollCents'])}, apoio R$ {br(b['supportCents'])}, demais despesas R$ {br(b['generalCents'])}; já incluem os rateios da p.4. Não se adiciona R$ 3.301,29 do antigo rateio por capacidade. Auxiliares/estagiárias e encargos nominais são composição dentro desses blocos, não acréscimos. Custo real adicional ausente/indevido: não quantificado, não presumido zero. Mensalidade oficial R$ 930,69; ticket previsto R$ {br(r['ticketCents'])}; **PE REAL de planejamento = {val(r['pe'])} alunos**. A premissa atual resulta em teto(10.755,30 / 782,151876) = 14. Custo permanece parcialmente comprovado, sem declaração de fechamento definitivo. Referências 15/22/7 preservadas apenas como histórico.")
    lines+=['',f"## 41 turmas — capacidade {e['capacity']}; matriculados {e['enrolled']}; novos {e['new']}; rematrículas {e['re']}; vagas líquidas {e['vacancies']}",'',
        'Fonte atual: Turmas CAJ 2027 (2).pdf, duas páginas. A linha 1º EM B está sem números; não cria turma adicional. 1º EM A corresponde ao cadastro 1º EM. Valores negativos de vagas preservados. Receita atual = matrículas × ticket do mix observado; é estimativa, pois a planilha não está identificada como relação nominal dos 775 matriculados. A matrícula não modifica custo ou PE.','',
        '| Turma | Cap. | Matr. | Novos | Remat. | Vagas | Mensalidade R$ | Desconto médio financeiro R$ | Ocup. % | Custo reconciliado R$ | Ticket R$ | PE real calculado | PE % | Matr. − PE | Situação | Receita proj. R$ | Resultado proj. R$ | Status |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|']
    for r in d['rows']:
        values=[r['name'],r['capacity'],r['enrolled'],r['newStudents'],r['reenrolled'],r['vacancies'],br(r['tuitionCents']),br(r.get('averageFinancialDiscountCents')),f"{r['occupancyPercent']:.2f}",br(r['consideredCostCents']),br(r['ticketCents']),val(r['pe']),f"{r['percentCapacity']:.2f}" if r['pe'] is not None else 'PENDENTE',val(r['distanceToPE']),r['enrollmentSituation'],br(r['projectedRevenueCents']),br(r['projectedResultCents']),r['status']]
        lines.append('| '+' | '.join(map(str,values))+' |')
    lines+=['',f"**{s['partial']} PEs calculados parcialmente comprovados; {s['audit']} em auditoria; 0 integralmente comprovados; 0 inviabilidades definitivas declaradas.** APE e memória por turma estão em resultado.json e no botão local “Ver memória de cálculo”.",
        f"Receita projetada conhecida sobre as matrículas atuais: R$ {br(e['knownProjectedRevenueCents'])}; {e['missingRevenueClasses']} turmas ainda sem receita projetável. Descontos individuais válidos e vinculados: R$ {br(s['discountCents'])}; todos os benefícios validáveis da planilha, inclusive não vinculados: R$ {br(s['allValidatedWorkbookDiscountCents'])}. Não equivalem à receita/desconto real dos 775 alunos sem vínculo nominal. Inadimplência de 4,5% uma vez; sem desconto estrutural adicional de 3%.",
        'Taxas de rateio testadas: receita prevista por segmento p.6–7; receita bruta por turma para apoio/gerais p.4; alunos previstos dentro do segmento para folha p.4. O rateio por capacidade do cenário antigo não foi reaplicado. Contas analíticas gerais apresentam R$ 0,04 acima do total oficial: diferença explicitada, não ocultada em pessoa/rubrica.','',
        'Mensalidades: orçamento oficial p.2, coluna 2027 — EI 930,69; FI 964,67; FII 1.239,81; EM 1º/2º 1.425,59; 3º EM 1.461,05. O desconto médio financeiro é a soma dos valores individuais dividida pela quantidade validada, não média de categorias. PCLD neutralizada no PE para evitar dupla incidência com inadimplência. Receitas 3182019/3195130 não financiam o PE real sem prova de disponibilidade/recorrência.','',
        '## PENDÊNCIAS RESTANTES','',
        '| Informação indispensável | Valor envolvido | Turmas/uso |','|---|---|---|',
        '| Destino financeiro do 7º C do orçamento e cobertura das turmas sem linha financeira ativa | R$ 15.827,05 líquidos de PCLD/descontos substituídos; valores nominais dessas turmas são referência dentro do envelope, não acréscimo | 7º C documental, 1º/2º/3º D e 8º C; identificar destino sem transferir por nome |',
        '| Custo de Paula e ponte de alterações de postos/encargos 2026→2027 | Paula: não determinado; estágio não identificado nominalmente R$ 2.863,57 já dentro de 4119040, não custo adicional | G3 B e centros de Jailane/Romilton/Veroneide; garantir cobertura completa sem duplicar o orçamento |',
        '| Composição nominal 2027 que valide as rubricas já quantificadas no orçamento | R$ 387.591,93 em contas comprovadas; diferença nominal não determinada, não novo saldo financeiro de R$ 623 mil | Pessoal escola/segmentos; fechar suficiência e identidade dos componentes, mantendo Lohana/Marcelo fora de docentes |',
        '| Mix de descontos das turmas sem base, vínculo dos códigos não homologados e identificação da população efetivamente matriculada | Receita não determinada; 114 registros sem correspondência de turma | G2 A/B, G5 C, 8º C; EFUND04TD/06TD/07TC e EMERE01MB/TC. Não presumir mix nem aplicar progressão novamente |',
        '| Regra dos quatro benefícios conflitantes e ponte por evento das concessões contábeis | Linhas 275, 276, 482 e 697; R$ 177.901,08 substituídos financeiramente, sem conciliação nominal de identidade | 3º A, 5º A e 7º C da planilha; confirmar 45/100, 50/45 e 50+45 e vínculo com bolsas/comercial/contas 4126005/4126007 |','',
        'Verificações completas e preservação: [TESTES.md](TESTES.md). Sem deploy, push, acesso a Supabase remoto, mudança de usuários/permissões ou importação em produção. Atualização de matrículas somente em data/caj.sqlite3; backup anterior preservado.']
    (AUDIT/'FECHAMENTO_PE_REAL_2027.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if d.get('sanitation'):
        # Substitui a lista anterior, sem repetir pendências já resolvidas.
        report='\n'.join(lines).split('## PENDÊNCIAS RESTANTES')[0]+pending_table(d)
        (AUDIT/'FECHAMENTO_PE_REAL_2027.md').write_text(report,encoding='utf-8')
    if d.get('benefitSummary'):
        path=AUDIT/'FECHAMENTO_PE_REAL_2027.md'
        text=path.read_text(encoding='utf-8')
        b=d['benefitSummary']
        note=(f"\n**BASE DE BENEFÍCIOS PREVISTOS CONFIRMADA:** {b['total']} registros persistidos localmente; "
              f"{b['active']} ATIVOS com vínculo nominal demonstrado; {b['waiting']} PREVISTOS aguardando matrícula/vínculo nominal; "
              f"{b['pending']} pendentes de turma. Todos os 1.016 têm ID nominal recuperado por correspondência exata e única na exportação. "
              "A diferença 1.016 × 775 NÃO é divergência. Zero benefícios ativados não significa zero alunos matriculados: o PDF comprova os totais, mas não suas identidades. "
              "PE utiliza o mix completo previsto por turma. Caixa atual usa somente matrículas nominalmente vinculadas.\n")
        text=text.replace('**TOTAL ECONÔMICO A CONCILIAR:**',note+'\n**TOTAL ECONÔMICO A CONCILIAR:**',1)
        text=text.replace('A receita atual =', 'A projeção pelo mix previsto =')
        text=text.replace('Receita atual = matrículas × ticket do mix observado; é estimativa, pois a planilha não está identificada como relação nominal dos 775 matriculados.', 'Projeção de planejamento = matrículas × ticket previsto; não é caixa atual. A base de benefícios antecipados está confirmada, independentemente das 775 matrículas.')
        text=text.replace('Não equivalem à receita/desconto real dos 775 alunos sem vínculo nominal.', 'São benefícios previstos confirmados, não receita de caixa dos 775. Não se exige que as populações coincidam.')
        text='\n'.join(line for line in text.splitlines() if not line.startswith('| Identidade da população de descontos versus matrículas'))+'\n'
        # Mantém uma única tabela principal; acrescenta indicadores de benefício/ticket atual.
        text=text.replace('| Status |\n|---', '| Benefícios previstos | Ativos | Aguardando matrícula | Ticket atual R$ | Receita atual vinculada R$ | Status |\n|---',1)
        lines=text.splitlines()
        for i,line in enumerate(lines):
            if line.startswith('|---') and i and 'Benefícios previstos' in lines[i-1]:lines[i]+='---:|---:|---:|---:|---:|'
            for r in d['rows']:
                if line.startswith('| '+r['name']+' |'):
                    old='| '+r['status']+' |'
                    new='| '+' | '.join(map(str,[r['plannedBenefitCount'],r['activeBenefitCount'],r['waitingBenefitCount'],br(r['currentTicketCents']),br(r['currentRevenueCents']),r['status']]))+' |'
                    lines[i]=line.replace(old,new)
                    break
        text='\n'.join(lines)+'\n'
        text=text.replace('**Saneamento:**','**G2:** custo R$ 10.755,30 por turma; premissa específica de 12% enquanto não houver benefícios individuais, substituída automaticamente pelo mix real cadastrado. Nenhum benefício ou matrícula fictícia foi criado.\n\n**Saneamento:**',1)
        text+='\nFluxo persistente e critérios de ativação: [BENEFICIOS_PREVISTOS_2027.md](BENEFICIOS_PREVISTOS_2027.md).\n'
        path.write_text(text,encoding='utf-8')
    print(json.dumps(dict(costs=c,enrollment=e,partial=s['partial'],audit=s['audit']),ensure_ascii=True))


def pending_table(d):
    by_name={r['name']:r for r in d['rows']}
    result=['## PENDÊNCIAS EXATAS APÓS A PESQUISA','',
        '“Não localizado” refere-se às fontes examinadas; não afirma inexistência fora delas. Limites abaixo isolam cada pendência e mantêm os demais parâmetros fixos. Custo sem valor não permite máximo finito inventado.','',
        '| Item exato | Valor exato conhecido | Turma/pessoa | Documento ou campo específico não localizado | Impacto mínimo/máximo no PE |','|---|---|---|---|---|',
        '| Destino da linha 7º Ano C do orçamento p.4 | R$ 15.827,05/mês | 7º C documental; atuais 1º D, 2º D, 3º D, 8º C sem ponte financeira | De-para financeiro aprovado do orçamento para a estrutura de 41 turmas, preservando contas e custos herdados | PE total dessas quatro turmas indeterminado; limites da parcela conhecida isolada abaixo, sem autorizar distribuição |',
        '| Custo e inclusão do posto adicional | Não determinado; R$ 2.863,57 é saldo agregado de estágio, não salário | Paula Araujo Dias / 955 / G3 B | Verbas/contrato do posto, jornada, encargos e vínculo com 4119040 em 2027 | Aumento mínimo 0 se já incluída; máximo não delimitável sem custo. Com custo atual/mix fixos, PE parcial 21; fórmula teto((15.460,75 + custo adicional líquido)/ticket) |',
        '| Evolução nominal dos postos e rubricas para 2027 | R$ 387.591,93 alvo; diferença nominal ainda não mensurada | Jailane/952 substitui Romilton/679; Veroneide/953 vaga nova; composição restante dos 19 códigos de pessoal | Quadro nominal de formação dessas contas 2027 e verbas dos vínculos 952/953, não nova cópia da folha de agosto já fornecida | Nenhum acréscimo automático: 0 de efeito se todos cobertos; máximo não delimitável sem valor e destino. Romilton não soma segundo posto |',
        '| Distribuição de benefícios ausente | Custo orçado G5 C R$ 13.444,13; custo 8º C sem ponte | G5 C e 8º C | Benefícios atuais dessas turmas, distintos das turmas históricas | G5 C: mínimo teórico 16 com custo fixo, máximo não finito; 8º C depende também do numerador |',
        '| Destino de 114 registros nominalmente individualizados | Valores individuais em normalizacao-114.json; não constituem custo novo | 4º D (21), 6º D (16), 7º C (27), 1º EM B (26), 1º EM C (24) escritos na planilha | Vínculo atual desses IDs com turmas existentes ou confirmação de que estão fora da população de 775; grafia não resolve mudança de letra | Não delimitável por turma sem destino. Nenhum registro foi transferido por aproximação |',
        '| Identidade da população de descontos versus matrículas | 1.016 registros de descontos versus 775 matrículas agregadas | 41 turmas; 902 registros vinculados/validados | Relação dos IDs efetivamente matriculados em 2027 ligada aos benefícios; o PDF fornecido contém quantidades, não esses IDs | Mix pode alterar o ticket entre zero e a mensalidade × 0,955; máximos não finitos sem população. Projeção atual é estimativa |',
        '| Ponte das concessões por evento/competência | 4126005 R$ 48.388,20; 4126007 R$ 129.512,88; 3149026 R$ -34.646,32; bolsas discriminadas na memória | Concessões da escola, sem lotação inventada | Chave aluno/evento/competência → conta contábil, ausente das planilhas e demonstrativos fornecidos | Efeito adicional atual 0: não reaplicar concessões no custo/ticket; eventual revisão de mix não delimitável sem vínculo. Não é nova despesa de R$ 177.901,08 |','',
        'Limites apenas da parcela sem destino de R$ 15.827,05, se integralmente atribuída a uma única turma e mantendo o ticket observado (cenário matemático, não alocação):']
    for name in ('1º D','2º D','3º D','8º C'):
        b=next(x for x in d['sanitation']['bounds'] if x['name']==name)
        result.append(f"- {name}: incremento entre 0 e {b['additionalKnownReserveImpactCeiling'] if b['additionalKnownReserveImpactCeiling'] is not None else 'não delimitável'} alunos; o PE total continua sem custo integral comprovado.")
    result+=['','Verificações e preservação: [TESTES.md](TESTES.md). Sem deploy, push, Supabase remoto ou mudança de usuários/permissões. Matrículas preservadas no banco local; backup anterior mantido.','']
    return '\n'.join(result)


if __name__=='__main__':main()
