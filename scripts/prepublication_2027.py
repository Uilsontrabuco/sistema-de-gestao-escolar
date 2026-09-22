"""Checkpoint incremental: somente evidências existentes e leituras locais."""
import sys,json,sqlite3,hashlib,subprocess
from contextlib import closing
from pathlib import Path
from decimal import Decimal
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pe_real import AUDIT,ceil_ratio,calculate
from benefits_2027 import apply_benefit_view,summarize,is_planned
from enrollment_2027 import project_current,snapshot
from scripts.reconcile_pe_real_costs import reconcile,apply_costs
from scripts.sanitize_pe_real import normalized_label
from scripts.audit_pe_real import br
OUT=ROOT/'output/pre-publicacao-2027'

def collect():
    with closing(sqlite3.connect(f'file:{(ROOT/"data/caj.sqlite3").as_posix()}?mode=ro',uri=True)) as db:
        state=json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
    costs=reconcile();old=json.loads((AUDIT/'resultado.json').read_text(encoding='utf-8'))
    records=json.loads((AUDIT/'registros-saneados-locais.json').read_text(encoding='utf-8'))
    fresh=calculate(records,allow_partial_mix=True);fresh['sanitation']=old['sanitation']
    fresh=apply_benefit_view(project_current(apply_costs(fresh,costs),state=state),state)
    keys=('capacity','enrolled','newStudents','reenrolled','vacancies','consideredCostCents','ticketCents','pe','distanceToPE','status')
    assert all(all(a[k]==b[k] for k in keys) for a,b in zip(old['rows'],fresh['rows']))
    names={c['name']:c['id'] for c in state['classes']}
    exceptions=[dict(sourceRow=r['sourceRow'],code=r['sourceClass'],normalized=normalized_label(r['sourceClass']),status='PREVISTO COM TURMA VÁLIDA' if normalized_label(r['sourceClass']) in names else 'PENDENTE DE TURMA') for r in records if not r['classId']]
    assert len(exceptions)==114 and all(r['status']=='PENDENTE DE TURMA' for r in exceptions)
    b=summarize(state);buckets=dict(ATIVOS=b['active'],PREVISTOS=b['waiting'],PENDENTES_DE_TURMA=sum(x.get('linkStatus')=='TURMA_INVALIDA' for x in state['benefits'] if is_planned(x)))
    buckets['AMBIGUOS']=b['total']-sum(buckets.values())
    assert sum(buckets.values())==1016 and len({x['id'] for x in state['benefits'] if is_planned(x)})==1016
    source=snapshot();actual={c['id']:c for c in state['classes']}
    assert all(actual[r['id']]['students']==r['students'] and actual[r['id']]['capacity']==r['capacity'] for r in source['rows'])
    reserve=next(a for a in costs['allocations'] if not a['classId']);assert reserve['costCents']==1582705
    parts=[dict(valueCents=reserve['payrollCents'],account='411* — bloco folha p.4; divisão nominal/por conta da turma não demonstrada',rubric='Folha',criterion='Alunos previstos dentro de FII'),dict(valueCents=reserve['supportCents'],account='411* — bloco apoio p.4; não adicionar estágio novamente',rubric='Apoio',criterion='Receita bruta prevista p.4'),dict(valueCents=reserve['generalCents']-reserve['pcldRemovedCents']-reserve['discountReclassifiedCents'],account='Contas gerais p.12–15, excluídas 4124001/4126005/4126007',rubric='Gerais líquidos',criterion='Receita bruta prevista p.4')]
    for p in parts:p.update(classification='E',origin='Orçamento 2027 p.4: 7º Ano C',destination='Não comprovado na estrutura atual',segment='FII documental',className=None,peTreatment='Reserva explícita, não atribuída a nenhuma turma')
    assert sum(p['valueCents'] for p in parts)==1582705
    bounds=[]
    for r in fresh['rows']:
        ticket=Decimal(r['planningAssumption']['ticketExactCents']) if r.get('planningAssumption') else (Decimal(r['netRevenueCents'])/r['acceptedStudentCount'] if r['acceptedStudentCount'] and r['netRevenueCents'] else None)
        base=r['consideredCostCents'];upper=ceil_ratio((base or 0)+1582705,ticket)
        bounds.append(dict(name=r['name'],potentialUnmapped=r['name'] in ('1º D','2º D','3º D','8º C'),baselinePE=r['pe'],minimumIncrement=0,maximumIncrement=upper-r['pe'] if upper is not None and r['pe'] is not None else ceil_ratio(1582705,ticket),ticketCents=str(ticket) if ticket else None,qualification='Somente parcela conhecida; total não delimitável sem custo integral/mix' if base is None or ticket is None else 'Custo e ticket fixos; cenário extremo, não alocação'))
    return dict(report=fresh,benefits=buckets,exceptions=exceptions,reserve=reserve,parts=parts,bounds=bounds)

def main():
    OUT.mkdir(parents=True,exist_ok=True);d=collect();(OUT/'verificacao.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Saldo de R$ 15.827,05 — fechamento incremental','',
    'Origem comprovada: 7º Ano C, orçamento p.4. Destino atual não comprovado. Os 27 benefícios EFUND07TC corroboram o código ausente, mas não autorizam transferir custo nem criar turma.',
    'Ponte: R$ 22.094,01 impresso − R$ 0,01 arredondamento − R$ 1.199,67 PCLD − R$ 5.067,28 concessões = R$ 15.827,05. Sem nova baixa ou rateio por capacidade.',
    'Classificação final do saldo: A=0; B=0; C=0; D=0; E=R$ 15.827,05. As exclusões anteriores não são novas resoluções. Identidade nominal de cada conta dentro do bloco não pode ser inferida por proporcionalidade.', '',
    '| Valor R$ | Conta/rubrica | Origem | Destino | Segmento | Critério | Tratamento | Evidência |','|---:|---|---|---|---|---|---|---|']
    for p in d['parts']:lines.append(f"| {br(p['valueCents'])} | {p['account']} / {p['rubric']} | {p['origin']} | {p['destination']} | FII | {p['criterion']} | E; fora das 41 alocações | reconciliacao-custos.json; contas p.12–15 e bloco p.4 |")
    lines+=['','## Materialidade','', 'Mínimo zero se nenhuma parcela for destinada à turma. Máximo condicional: teto((custo-base + 15.827,05)/ticket) − PE-base; se custo-base ausente, apenas teto(15.827,05/ticket) para a parcela isolada. Máximos individuais não podem ocorrer simultaneamente. Não são lotações aprovadas.', '', '| Turma | PE-base | Acréscimo mínimo | Máximo condicional da parcela | Qualificação |','|---|---:|---:|---:|---|']
    for b in d['bounds']:lines.append(f"| {b['name']} | {b['baselinePE'] if b['baselinePE'] is not None else 'PENDENTE'} | 0 | {b['maximumIncrement'] if b['maximumIncrement'] is not None else 'não finito com ticket desconhecido'} | {b['qualification']} |")
    lines+=['','As quatro turmas sem ponte são 1º D, 2º D, 3º D e 8º C; isso não comprova que herdem 7º C. Para 8º C o ticket também não está determinado. Paula e alterações nominais sem valor impedem um teto finito para o custo total: este ensaio mensura exclusivamente o saldo conhecido.','', 'Documento indispensável: de-para financeiro aprovado entre 7º C do orçamento e estrutura atual, por bloco/conta; composição nominal de postos 2027 e benefícios de G5 C/8º C seguem pendências já registradas.']
    (OUT/'SALDO-E-MATERIALIDADE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    lines=['# 114 benefícios — último reprocessamento','',str(d['benefits']),'','Ausência de matrícula não é erro. Normalização não reaplica progressão nem altera letra/ano.', '', '| Código | Registros | Nome normalizado | Resultado |','|---|---:|---|---|']
    counts=Counter((r['code'],r['normalized']) for r in d['exceptions'])
    for (code,name),count in counts.items():lines.append(f'| {code} | {count} | {name} | PENDENTE DE TURMA |')
    (OUT/'BENEFICIOS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(benefits=d['benefits'],reserve=d['reserve']['costCents'],classes=len(d['report']['rows']))))
if __name__=='__main__':main()
