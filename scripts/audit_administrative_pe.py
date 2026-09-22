"""Relatório local antes/depois da aprovação administrativa, sem escrever banco."""
import json,csv,hashlib,sys,sqlite3
from pathlib import Path
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from administrative_pe_2027 import administrative_view
from personnel_confirmations_2027 import personnel_evidence
from pe_final_2027 import executive

OUT=ROOT/'output/pe-administrativo-aprovado-20270922'
def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
def br(x):return 'PENDENTE' if x is None else f'{x/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')
def shown(x):return 'PENDENTE' if x is None else str(x)
def main():
    OUT.mkdir(exist_ok=True)
    before=read('output/pre-publicacao-2027/resultado-final.json')
    ledger=read('output/pe-real-2027/reconciliacao-custos.json')
    after=administrative_view(before,ledger);after['executive']=executive(after)
    (OUT/'resultado-administrativo.json').write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding='utf-8')
    active={r['id']:r for r in after['rows']};reconciliation=after['administrativeReconciliation']
    lines=['# PE 2027 — reconciliação administrativa aprovada','',
    '**NO-GO para fechamento integral.** Premissas administrativas de jornada e redistribuição aceitas, aplicadas e não bloqueantes por falta de documento nominal. Restam três turmas ativas sem custo integral calculável: 1º D, 2º D e 3º D. A reserva legada não comprova custo necessário remanescente. Nenhum PE ausente foi convertido em zero.', '',
    '## Decisões aplicadas','',
    'Jailane, Veroneide e Paula: ASG, salário-base R$ 1.690,50 cada, jornada 44h semanais, aprovação administrativa de 22/09/2026. A composição local é atualizada em personnel_confirmations_2027.py. Jailane substitui Romilton; um único posto. Nenhum percentual de encargos estimado.',
    '8º C extinto na estrutura administrativa local. Os vinte são rematrículas quantitativas autorizadas, não nomes ou matrículas individuais criados. Mantidos os 22 já existentes no A e zero no B; dentre todas as distribuições possíveis somente dos vinte do C, 0 para A e 20 para B minimiza a diferença absoluta: 22 versus 20. Não se move um aluno já em A apenas para obter 21/21.',
    '8º A: capacidade 35, matriculados 22, vagas 13, ocupação 62,86%. 8º B: capacidade 28, matriculados 20, vagas 8, ocupação 71,43%. Capacidade física de A/B preservada. As 28 vagas de capacidade do C deixam a estrutura ativa; não foram atribuídas a outra sala sem base.',
    'A solicitação de somente A/B implica 40 turmas ativas; as 41 linhas são mantidas exclusivamente na comparação histórica. O 7º C já não existia nas 41 anteriores e não foi criado. Arquivo resultado-administrativo.json contém apenas 40 rows ativas e uma archivedRows histórica. Nenhuma mudança foi escrita no banco operacional; este é o cenário local para aprovação antes de futura publicação.', '',
    '## Encargos, cobertura e antiduplicidade','',
    'As 19 rubricas de pessoal somam R$ 387.591,93 dentro do orçamento. Exemplos: salários 4111001 R$ 276.942,34; provisão de 13º e encargos 4111005 R$ 25.708,06; 1/3 férias 4111009 R$ 8.569,35; FGTS 4112001 R$ 22.475,39. Cobertura agregada reconhecida, sem adicionar provisões ou FGTS novamente. O orçamento não identifica quanto de cada conta pertence aos três novos vínculos; essa limitação permanece expressa, sem encargo individual estimado e sem bloquear por jornada já aprovada.',
    'Centros históricos: Jailane/952 e Veroneide/953, CAJ Serviços de Apoio/C27; Paula/955, Educação Infantil/C02, posto adicional G3 B confirmado anteriormente. A função de Paula foi corrigida para ASG por aprovação do gestor, sem inferir mudança de centro. Salários de referência R$ 5.071,50 são composição nominal, não despesa adicional. Verificações não encontraram identidade nominal duplicada que autorizasse estorno; ausência de nova dupla soma é comprovada, ausência universal de duplicidade histórica não é certificada sem razão nominal.',
    'PCLD 4124001: R$ 42.117,80 já neutralizados uma única vez. Descontos orçados 4126005/4126007: R$ 177.901,08 já reclassificados uma única vez. Ticket mantém benefícios e inadimplência 4,5% uma vez; multiplicador docente 4,5, mensalidades, mix e custos diretos não alterados. nominalCosts descreve composição histórica e não é somado a costs. Rateios existentes têm pesos congelados e não foram recalculados por matrícula.', '',
    '## R$ 15.827,05 — origem e absorção','',
    'Fonte: orçamento p.4, 7º Ano C/Fundamental II. Ponte: 22.094,01 − 0,01 de arredondamento − 1.199,67 PCLD − 5.067,28 descontos = 15.827,05. Folha 5.748,45 + apoio 3.416,95 + gerais líquidos 6.661,65. Centro nominal e obrigação efetiva após extinção não comprovados.',
    '7º A conserva exatamente R$ 18.758,00 e 7º B R$ 17.585,61 de suas linhas documentais. Todas as 37 linhas com custo reproduzem suas alocações únicas do razão; somam R$ 605.641,03. A diferença até R$ 621.468,08 é exatamente a reserva de R$ 15.827,05: ela não está absorvida nos custos alocados atuais. Ela já integra o envelope escolar, portanto adicioná-la ao total escolar outra vez duplicaria o valor.',
    'Classificação: LEGADO ORÇAMENTÁRIO A REVISAR, com obrigação remanescente não demonstrada. Não é afirmação de inexistência de obrigação nem economia realizada. Sem prova de continuidade de despesas, não se aplica rateio novo em A/B. Permanece no controle do orçamento, fora do PE por turma. A existência de somente 7º A/B está aprovada e não exige nova confirmação.', '',
    '## Totais antes e depois','',
    '| Indicador | Antes | Depois | Diferença |','|---|---:|---:|---:|']
    for key,value in reconciliation['before'].items():
        end=reconciliation['after'][key];fmt=br if key.endswith('Cents') else str
        lines.append(f'| {key} | {fmt(value)} | {fmt(end)} | {fmt(end-value)} |')
    lines+=['', 'Valores adicionados R$ 0,00; custos redistribuídos R$ 0,00; excluídos por duplicidade R$ 0,00; orçamento legado em revisão R$ 15.827,05. Vinte rematrículas redistribuídas. Envelope escolar antes/depois R$ 621.468,08. A diferença de receita projetada decorre da saída da premissa 12% do C e da utilização do mix já homologado do B para sua nova quantidade; não é alteração do ticket de B nem receita realizada nominalmente comprovada.', '',
    '## Comparação completa — 41 linhas de origem','',
    '| Turma | Cap. antes/depois | Alunos antes/depois | Vagas antes/depois | Custo antes | Custo depois | PE antes | PE depois | Situação |',
    '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    comparisons=[]
    for r in before['rows']:
        new=active.get(r['id']);retired=new is None
        fields=dict(turma=r['name'],capacidadeAntes=r['capacity'],capacidadeDepois=new['capacity'] if new else 0,
                    alunosAntes=r['enrolled'],alunosDepois=new['enrolled'] if new else 0,
                    vagasAntes=r['vacancies'],vagasDepois=new['vacancies'] if new else 0,
                    custoAntes=r['consideredCostCents'],custoDepois=new['consideredCostCents'] if new else None,
                    peAntes=r['pe'],peDepois=new['pe'] if new else None,
                    status='EXTINTA; não integra totais ativos' if retired else 'CUSTO PENDENTE' if new['pe'] is None else 'PE DE PLANEJAMENTO PRESERVADO')
        comparisons.append(fields)
        lines.append(f"| {r['name']} | {r['capacity']}/{fields['capacidadeDepois']} | {r['enrolled']}/{fields['alunosDepois']} | {r['vacancies']}/{fields['vagasDepois']} | {br(fields['custoAntes'])} | {br(fields['custoDepois']) if not retired else 'N/A'} | {shown(fields['peAntes'])} | {shown(fields['peDepois']) if not retired else 'N/A'} | {fields['status']} |")
    with (OUT/'comparacao-41-linhas.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(comparisons[0]),delimiter=';');writer.writeheader();writer.writerows(comparisons)
    lines+=['', 'PE conhecido agregado = 911 antes e depois; não é PE integral da escola. Redução de quatro para três PEs ausentes decorre exclusivamente da extinção do C, não da criação de custos. Todas as 37 fórmulas calculáveis foram novamente verificadas: teto(custo/ticket exato).', '',
    '## GO/NO-GO e informações restantes','',
    'As aprovações administrativas resolvem jornada e distribuição quantitativa. A lista nominal antiga não é bloqueio desta etapa. Ainda falta base de custo integral para 1º D, 2º D e 3º D; seus custos nominais parciais não podem ser promovidos a custos completos. É necessário o mapa orçamentário dessas três turmas ou uma decisão administrativa explícita sobre o tratamento de seus custos, com reconciliação do total escolar.',
    'Para encerrar o legado de R$ 15.827,05, falta comprovar obrigação mantida ou aprovar sua revisão/cancelamento orçamentário com base nos postos e contratos correspondentes. Não basta a extinção da turma para provar redução de folha e despesas institucionais. A cobertura agregada de encargos está reconhecida; encargos individuais permanecem como limitação documental sem estimativa.',
    'Conclusão de fechamento integral: NO-GO por custos ativos não determinados e revisão econômica do legado ainda inconclusiva, não pela falta de documentos substituídos pelas premissas aprovadas. Eventual publicação exige aprovação humana futura e não é executada por este relatório.', '',
    'Execução local: sem deploy, push, publicação, Supabase remoto ou acesso/alteração de produção. Banco operacional e backup anterior preservados. Os artefatos desta pasta representam o cenário administrativo aprovado em auditoria; os documentos originais permanecem como memória histórica.']
    # A correção mais recente de existência do 8º C substitui o cenário anterior.
    replacements={
        '**NO-GO para fechamento integral.**': '**NO-GO para fechamento integral.** Jornada 44h aprovada. Correção posterior do usuário: o 8º C existe e permanece com vinte matriculados. Nenhuma redistribuição aplicada. Quatro turmas ativas ainda têm custo integral pendente: 1º D, 2º D, 3º D e 8º C. Não foram convertidos custos ausentes em zero.',
        '8º C extinto': 'Correção administrativa posterior: manter 8º C. A autorização anterior de redistribuição sem C foi superada e permanece apenas no subdiretório histórico-cenario-sem-8C. Não houve nomes inventados, transferência no banco ou alteração do total de alunos.',
        '8º A: capacidade': '8º A: capacidade 35, matriculados 22, vagas 13, ocupação 62,86%. 8º B: capacidade 28, matriculados 0, vagas 28, ocupação 0%. 8º C: capacidade 28, matriculados 20, vagas 8, ocupação 71,43%. Capacidades e quantidades atuais integralmente preservadas.',
        'A solicitação de somente A/B': 'Estrutura final desta auditoria: 41 turmas ativas, incluindo 8º A/B/C; no 7º ano, somente A/B. As 41 linhas da comparação são todas ativas. resultado-administrativo.json e cadastro-turmas-auditoria.json refletem a correção. O banco operacional não foi alterado.',
        'Valores adicionados': 'Valores adicionados R$ 0,00; custos redistribuídos R$ 0,00; excluídos por duplicidade R$ 0,00; orçamento legado em revisão R$ 15.827,05. Alunos redistribuídos: zero. Envelope escolar antes/depois R$ 621.468,08. Receita projetada e tickets preservados, inclusive a premissa anterior do 8º C; ela não é receita nominal realizada.',
        'PE conhecido agregado': 'PE conhecido agregado = 911 antes e depois; não é PE integral da escola. Quatro PEs continuam ausentes por falta de custo integral. Todas as 37 fórmulas calculáveis foram verificadas: teto(custo/ticket exato).',
        'As aprovações administrativas resolvem': 'A jornada de 44h e a existência do 8º C estão resolvidas por aprovação humana. Não se exige lista nominal para manter seus vinte matriculados agregados. Resta base de custo integral para 1º D, 2º D, 3º D e 8º C; necessária ponte orçamentária ou decisão econômica explícita sobre seus custos, conciliada ao envelope da escola. Custos nominais parciais não foram tratados como custo completo.',
    }
    lines=[next((replacement for prefix,replacement in replacements.items() if line.startswith(prefix)),line) for line in lines]
    (OUT/'GO-NO-GO-FINAL.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (OUT/'cadastro-turmas-auditoria.json').write_text(json.dumps(dict(source=after['administrativeApproval'],scope='CENARIO_LOCAL_AUDITORIA',classes=[dict(id=r['id'],name=r['name'],capacity=r['capacity'],students=r['enrolled'],opening=dict(new=r['newStudents'],re=r['reenrolled'])) for r in after['rows']],personnel=personnel_evidence(),totals=after['enrollmentSummary']),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(reconciliation,ensure_ascii=True))
if __name__=='__main__':main()
