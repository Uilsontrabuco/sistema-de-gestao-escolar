"""Emissão local reproduzível, sem alteração do banco ou fontes anteriores."""
import sys,json,sqlite3
from contextlib import closing
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from benefits_2027 import apply_benefit_view
from enrollment_2027 import project_current
from pe_real import load_report
from pe_final_2027 import final_view,executive
from pe_executive_pdf import executive_pdf,br
from personnel_confirmations_2027 import personnel_evidence,personnel_note
OUT=ROOT/'output/pre-publicacao-2027'

def main():
 with closing(sqlite3.connect(f'file:{(ROOT/"data/caj.sqlite3").as_posix()}?mode=ro',uri=True)) as db:
  s=json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
 d=final_view(apply_benefit_view(project_current(load_report(),state=s),s),s);d['executive']=executive(d)
 (OUT/'pessoal-confirmado-2027.json').write_text(json.dumps(personnel_evidence(),ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'resultado-final.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
 pdf=ROOT/'output/pdf/RELATORIO-EXECUTIVO-PE-2027.pdf';pdf.parent.mkdir(exist_ok=True)
 pdf.write_bytes(executive_pdf(d))
 r=next(r for r in d['rows'] if r['name']=='G3 B');ticket=Decimal(r['netRevenueCents'])/r['acceptedStudentCount'];headroom=ticket*r['pe']-r['consideredCostCents'];threshold=int(headroom.to_integral_value(rounding=ROUND_FLOOR))+1
 bound=dict(className='G3 B',costCents=r['consideredCostCents'],ticketExactCents=str(ticket),currentPE=r['pe'],minimumAdditionalCost=0,maximumAdditionalCost=None,firstAdditionalCentChangingPE=threshold,nextPE=r['pe']+1)
 (OUT/'paula-materialidade-final.json').write_text(json.dumps(bound,ensure_ascii=False,indent=2),encoding='utf-8')
 lines=['# Ponte documental final e custos nominais','',
 'Não transferido: orçamento (1), p.8 conferida visualmente; versões sem sufixo, (2) e (3) também lidas. 7º C: 27 na coluna 2027 e vazio em 2026. 8º C: 27 na coluna 2026 e vazio em 2027. Isso contradiz a ponte proposta de 7º C anterior para 8º C atual.',
 'A existência de 8º C no PDF de turmas atual e ausência de 7º C não corrigem automaticamente o exercício da despesa. A declaração operacional não substitui a retificação documental exigida pelo próprio comando.',
 'Correção posterior do usuário: somente 7º A/B e 8º A/B. Portanto, 8º C não é destino aprovado. Destino dos 20 matriculados, capacidade final de 8º A/B e destino financeiro permanecem sem informação. Fotografia de 41 linhas preservada para não excluir alunos ou inventar vagas.', '',
 '## Antiduplicidade do saldo','',
 'Custo econômico atual de 8º C = NÃO DETERMINADO, e não zero. Os valores nominais históricos são referência dentro do envelope, não custo econômico já alocado. Não houve qualquer adição. Reserva permanece R$ 15.827,05; soma alocada R$ 605.641,03; envelope R$ 621.468,08. Blocos: folha 5.748,45 + apoio 3.416,95 + gerais líquidos 6.661,65. Nenhuma segunda aplicação.',
 'Cenário exclusivamente condicional se houvesse comprovação futura: 15.827,05 / 1.041,936324 => teto 16; 20 - 16 = 4; margem física 12; ocupação 71,43%; receita 20.838,73; resultado 5.011,68. NÃO é PE efetivo, não autoriza manter 8º C nem transferir custo.', '',
 '## Nominal','',
 'Reutilizada pesquisa já concluída: folha agosto, 2.118 linhas nominais e pesquisa adicional registrada em pesquisa-saneamento.json. Paula/955, Jailane/952 e Veroneide/953 aparecem no cadastro, sem verbas na folha de agosto. Não foi encontrada nova evidência de valor nas fontes existentes. Paula é posto adicional G3 B; Jailane substitui Romilton, apenas um posto; Veroneide é vaga nova. Paula não é a única lacuna nominal demonstrada.',
 f"G3 B: custo atual {br(r['consideredCostCents'])}, ticket {br(float(ticket))}, PE {r['pe']}. Seja x o acréscimo mensal líquido efetivamente não coberto: PE(x)=teto(({r['consideredCostCents']}/100 + x)/(ticket exato/100)). Mínimo x=0 somente como limite, não custo de Paula; máximo não delimitável sem verbas/cobertura. Primeiro acréscimo em centavos que eleva o PE para {r['pe']+1}: {br(threshold)}. Folga exata até o próximo aluno: {headroom/100} reais.",
 'Documento necessário: verbas, jornada, encargos e inclusão orçamentária de 955/952/953 e ponte nominal 2027. Não usar saldo agregado de estágio R$ 2.863,57 como salário de Paula.', '',
 '## Novos tickets','',
 'G5 C: 964,67 × 0,88 × 0,955 = 810,708668; custo 13.444,13; PE 17; 14 matriculados; distância -3; ocupação 63,64%; receita 11.349,92; resultado -2.094,21. Mensalidade FI é premissa expressa, separada da documental EI 930,69.',
 '8º C da fotografia: ticket condicional 1.041,936324; custo/PE efetivos pendentes. A correção de estrutura impede tratá-lo como turma final aprovada.',
 'G2 A/B mantidos integralmente: ticket 782,151876 e PE 14. Nenhuma reimportação, progressão ou alteração dos 1.016 benefícios.'
 ]
 lines=[personnel_note() if line.startswith('Reutilizada pesquisa já concluída:') else
        'Documento ainda necessário: jornada, demais verbas, encargos e conta orçada de 955/952/953, com ponte nominal 2027. Os salários de R$ 1.690,50 estão confirmados pelo gestor; não usar saldo agregado de estágio como salário de Paula.' if line.startswith('Documento necessário: verbas, jornada, encargos') else line for line in lines]
 (OUT/'PONTE-E-NOMINAL-FINAL.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps(dict(pdf=str(pdf),executive=d['executive'],paula=bound),ensure_ascii=True))
if __name__=='__main__':main()
