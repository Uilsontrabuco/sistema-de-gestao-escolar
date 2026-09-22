"""Audita uma simulação congelada; não aplica rateio nem consulta o banco."""
import json,sys,hashlib
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/auditoria-criterios-rateio-2027'
SOURCE=ROOT/'output/simulacao-rateio-series-2027/simulacao.json'
def br(c):return 'N/D' if c is None else f'{Decimal(str(c))/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')
BLOCKS={'payrollCents':'Docente/folha','supportCents':'Apoio','generalNetCents':'Gerais/rateios'}
def original_blocks(row):
    b=row.get('costBridge')
    return dict(payrollCents=b['payrollCents'],supportCents=b['supportCents'],generalNetCents=b['generalCents']-b['pcldRemovedCents']-b['discountReclassifiedCents']) if b else dict.fromkeys(BLOCKS,0)

def main():
    OUT.mkdir(exist_ok=True);raw=SOURCE.read_bytes();s=json.loads(raw)
    originals={r['id']:r for r in s['originalRows']};flows=[];details=[];nominal_checks=[]
    for g in s['series']:
        for p in g['proposals']:
            original=originals[p['id']];old=original_blocks(original)
            assert p['payrollCents']>=p['teacherAnchorCents']
            assert p['supportCents']>=p['otherNominalAnchorCents']
            assert p['costAfterCents']==sum(p[k] for k in BLOCKS)
            known=sum(c['cents'] for c in original['nominalCosts'])
            assert p['teacherAnchorCents']+p['otherNominalAnchorCents']+p['historicalNonAdditiveControlCents']==known
            check=dict(name=p['name'],teacherBeforeCents=original['teacherCents'],teacherPreservedCents=p['teacherAnchorCents'],
                otherKnownPreservedCents=p['otherNominalAnchorCents'],historicalNonAdditiveControlCents=p['historicalNonAdditiveControlCents'],
                unidentifiedPayrollResidualCents=p['payrollResidualCents'],unidentifiedSupportResidualCents=p['supportResidualCents'])
            nominal_checks.append(check)
            cost_pct=None if p['costBeforeCents'] is None else (p['costAfterCents']/p['costBeforeCents']-1)*100
            pe_delta=p['peDelta']
            material=p['previouslyUnknown'] or abs(cost_pct or 0)>=20 or (pe_delta is not None and abs(pe_delta)>=3)
            reason=('Nova cobertura a partir do mesmo envelope, preservando âncoras; não é despesa criada.' if p['previouslyUnknown'] else
                    'Redistribuição do peso antes baseado em alunos/receita prevista: folha por âncora docente, apoio nominal preservado e saldos/gerais por capacidade.')
            details.append(dict(**p,costPercentChange=cost_pct,material=material,economicReason=reason,
                blocksBefore=old,blocksDelta={k:p[k]-old[k] for k in BLOCKS},othersDeltaCents=0))
        for key,block in BLOCKS.items():
            donors=[];receivers=[]
            for p in g['proposals']:
                old=original_blocks(originals[p['id']])[key];change=p[key]-old
                if change<0:
                    anchor=p['teacherAnchorCents'] if key=='payrollCents' else p['otherNominalAnchorCents'] if key=='supportCents' else 0
                    assert -change<=old-anchor
                    donors.append([p['name'],-change])
                elif change>0:receivers.append([p['name'],change])
            assert sum(v for _,v in donors)==sum(v for _,v in receivers)
            # Convenção para explicar a ponte, não histórico de transferências reais.
            i=j=0
            while i<len(donors) and j<len(receivers):
                value=min(donors[i][1],receivers[j][1])
                flows.append(dict(grade=g['grade'],block=block,source=donors[i][0],destination=receivers[j][0],cents=value,
                    evidence='Linha da série no orçamento p.4; ponte matemática proposta entre saldos agregados, não lançamento nominal original'))
                donors[i][1]-=value;receivers[j][1]-=value
                if donors[i][1]==0:i+=1
                if receivers[j][1]==0:j+=1
    assert sum(d['deltaFromPreviouslyAllocatedCents'] for d in details)==0
    assert sum(r['consideredCostCents'] or 0 for r in s['originalRows'])==60564103
    assert sum(r['consideredCostCents'] for r in s['rows'])==60564103
    assert s['reserveBeforeCents']==s['reserveAfterCents']==1582705
    lines=['# Auditoria dos critérios da simulação — para aprovação humana','',
      '**Conclusão técnica: REVISÃO NECESSÁRIA.** A matemática conserva todos os totais e as âncoras nominais identificadas. A exceção é econômica/documental: o saldo não individualizado de folha e apoio e o bloco de gerais foram tratados como redistribuíveis por uma regra proposta, sem prova de que não contenham custos exclusivos das turmas de origem.', '',
      'A simulação matemática foi aprovada para prosseguir na auditoria; essa autorização não foi interpretada como aprovação definitiva do rateio. O arquivo da simulação foi lido sem alteração. Nenhuma escrita no banco, acesso remoto, produção, publicação, deploy ou push.', '',
      '## Quinze turmas, uma por uma','',
      '| Turma | Custo antes R$ | Custo depois R$ | Diferença na alocação R$ | Diferença % | PE antes | PE depois | Motivo econômico da proposta |',
      '|---|---:|---:|---:|---:|---:|---:|---|']
    for d in details:
        pct='N/A: custo anterior não determinado' if d['costPercentChange'] is None else f"{d['costPercentChange']:+.2f}%".replace('.',',')
        lines.append(f"| {d['name']} | {br(d['costBeforeCents'])} | {br(d['costAfterCents'])} | {br(d['deltaFromPreviouslyAllocatedCents'])} | {pct} | {d['peBefore'] if d['peBefore'] is not None else 'N/D'} | {d['peAfter']} | {d['economicReason']} |")
    lines += ['', 'Nas quatro turmas com N/D, a diferença em R$ é a nova parcela do orçamento que passa a ser atribuída em simulação, comparada à contribuição anteriormente não alocada. Não significa que o custo real anterior fosse zero; a diferença percentual não é calculável. As reduções nas outras turmas são contrapartidas de repartição, não economias operacionais.', '',
      '## Alterações por categoria e origem','',
      '| Turma | Docente/folha Δ R$ | Apoio Δ R$ | Gerais/rateios Δ R$ | Outros Δ R$ |',
      '|---|---:|---:|---:|---:|']
    for d in details:lines.append('| '+d['name']+' | '+' | '.join(br(d['blocksDelta'][k]) for k in BLOCKS)+' | 0,00 |')
    lines += ['', 'Origem: linhas positivas de cada série na p.4 do orçamento, nos blocos Folha, Apoio e Gerais. Folha/apoio pertencem ao envelope de contas 411*; gerais líquidos derivam das demais contas operacionais, com PCLD e descontos já neutralizados. Não há de-para documental que permita chamar a transferência de saldo, por exemplo, salário de determinado funcionário ou conta analítica individual. A tabela abaixo usa a linha/bloco como origem, não inventa rubrica nominal.', '',
      '| Série | Bloco | Linha de origem | Turma de destino | Valor redistribuído R$ |','|---|---|---|---|---:|']
    for f in flows:lines.append(f"| {f['grade']} | {f['block']} | {f['source']} — orçamento p.4 | {f['destination']} | {br(f['cents'])} |")
    lines += ['', 'Esta é uma ponte matemática determinística para explicar a proposta: fontes e destinos percorridos na ordem A/B/C/D. Outros pareamentos produziriam o mesmo saldo final. Não é prova de um lançamento histórico nem de que um serviço específico de uma origem foi efetivamente prestado ao destino.', '',
      '## Custos nominais protegidos','',
      '| Turma | Âncora docente preservada R$ | Outros nominais preservados R$ | Controle histórico não aditivo R$ | Saldo de folha redistribuído na turma R$ | Saldo de apoio R$ |',
      '|---|---:|---:|---:|---:|---:|']
    for n in nominal_checks:lines.append('| '+n['name']+' | '+' | '.join(br(n[k]) for k in ['teacherPreservedCents','otherKnownPreservedCents','historicalNonAdditiveControlCents','unidentifiedPayrollResidualCents','unidentifiedSupportResidualCents'])+' |')
    lines += ['', 'Para cada origem doadora foi verificado: saída de folha ≤ folha original − âncora docente, e saída de apoio ≤ apoio original − âncora nominal de apoio. Assim, nenhuma saída consome as âncoras identificadas. Cada turma mantém seu próprio valor nominal; custos de uma professora, estagiária ou auxiliar não foram copiados para outra.',
      'Outros nominais incluem estágio, auxiliar exclusiva, auxiliares do segmento e coordenação, conforme nominalCosts de cada turma. Exemplos: 1º C mantém seu estágio, 2º A/C mantêm seus estágios e 3º A/B/D mantêm seus respectivos postos; os pools C28/C29 já identificados permanecem nos valores próprios. As frações de aulas compartilhadas estão dentro da âncora docente, não são transferidas novamente.',
      '8º C: âncora R$ 2.878,65, mais controle histórico R$ 274,14 mantido separado e não aditivo. Lohana AUX Administrativo e Marcelo na folha permanecem confirmações resolvidas. A simulação não identifica uma linha autônoma de pagamento desses R$ 274,14 e não os soma ou deduz do envelope.',
      '**Limite da confirmação:** foi demonstrado que nenhum custo nominal IDENTIFICADO foi retirado da sua turma. Não é possível garantir a afirmação mais ampla de que nenhum custo específico desconhecido foi transferido: folha residual, apoio residual e gerais não estão inteiramente individualizados. Conservar o total e os pisos conhecidos não comprova que todo excedente seja compartilhado.', '',
      '## Variações materiais','',
      'Critério de destaque usado somente nesta auditoria: mudança de pelo menos 3 alunos no PE, ou 20% no custo, além dos quatro primeiros PEs calculados. Não é parâmetro novo do motor.','',
      '| Turma | PE antes → depois | Variação de custo | Explicação |','|---|---|---:|---|']
    for d in details:
        if not d['material']:continue
        pct='Nova alocação; percentual N/A' if d['costPercentChange'] is None else f"{d['costPercentChange']:+.2f}%".replace('.',',')
        lines.append(f"| {d['name']} | {d['peBefore'] if d['peBefore'] is not None else 'N/D'} → {d['peAfter']} | {pct} | {'Entrada no mesmo envelope financiada por contrapartidas explícitas.' if d['previouslyUnknown'] else 'Mudança do peso de receita/alunos previstos para âncora docente e capacidade, repartindo o mesmo orçamento entre mais turmas; nenhuma redução de salário comprovada.'} |")
    lines += ['', 'O 3º A aumenta R$ 166,49 (+1,49%) e mantém PE 17; não é aumento material pelo critério declarado. Há movimentos opostos dentro de alguns blocos: o saldo líquido por turma não mostra sozinho toda a ponte, por isso as transferências foram discriminadas por categoria.', '',
      '## Confirmações globais','',
      '| Controle | Antes | Depois | Diferença |','|---|---:|---:|---:|',
      '| Custos atribuídos às 41 turmas | R$ 605.641,03 | R$ 605.641,03 | R$ 0,00 |',
      '| Reserva fora do PE | R$ 15.827,05 | R$ 15.827,05 | R$ 0,00 |',
      '| Envelope escolar | R$ 621.468,08 | R$ 621.468,08 | R$ 0,00 |',
      '| Turmas / matriculados / capacidade / vagas | 41 / 775 / 1.103 / 328 | 41 / 775 / 1.103 / 328 | 0 |',
      '', 'Nenhum custo criado ou excluído no total. Nenhum custo nominal conhecido transferido. A ausência de transferência indevida de custos específicos NÃO IDENTIFICADOS não pode ser confirmada documentalmente.', '',
      '## Conclusão técnica — REVISÃO NECESSÁRIA','',
      'Exceções a resolver antes da aprovação definitiva:',
      '1. Folha residual das quatro séries: distinguir encargos/provisões e outros custos vinculados a postos específicos de serviços efetivamente comuns. Só o saldo demonstradamente comum pode seguir o direcionador docente proposto.',
      '2. Apoio residual: confirmar se contém postos/contratos exclusivos das linhas A/B/C que precisam de âncora adicional antes de repartir o restante por capacidade.',
      '3. Gerais/rateios: identificar eventuais despesas diretamente vinculadas a sala/turma que não podem seguir uma distribuição uniforme por capacidade, preservando os contratos e a reserva.',
      'Não se exige reabrir salários, jornada, existência das turmas ou pessoas já aprovadas. A exceção é a natureza econômica dos saldos redistribuídos e sua abrangência. Um mapa nominal/contratual desses saldos, ou evidência administrativa específica de que atendem conjuntamente às turmas da série, resolve essa etapa. A proposta continua congelada, apenas auditada, sem aplicação.']
    (OUT/'AUDITORIA-DOS-CRITERIOS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    result=dict(conclusion='REVISÃO NECESSÁRIA',details=details,flows=flows,nominalChecks=nominal_checks,
        knownNominalAnchorsPreserved=True,allUnidentifiedExclusiveCostsProvenProtected=False,
        schoolBeforeCents=60564103,schoolAfterCents=60564103,reserveCents=1582705,
        simulationSha256=hashlib.sha256(raw).hexdigest())
    (OUT/'auditoria.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    assert SOURCE.read_bytes()==raw
    print(json.dumps(dict(turmas=len(details),transfers=len(flows),conclusion=result['conclusion']),ensure_ascii=True))
if __name__=='__main__':main()
