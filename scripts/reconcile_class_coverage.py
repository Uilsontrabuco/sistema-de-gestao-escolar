"""Liga as quatro turmas ao orçamento distribuído; sem modificar motor/banco."""
import json,sys,hashlib
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pe_real import money
TARGETS=('1º D','2º D','3º D','8º C')
OUT=ROOT/'output/reconciliacao-cobertura-quatro-turmas'
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def br(x):return 'NÃO DETERMINADO' if x is None else f'{Decimal(str(x))/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')

def reconcile(report,nominal,teaching,budget):
    rows=[]
    by_id={r['classId']:r for r in budget['allocations'] if r['classId']}
    assert len(by_id)==sum(r['classId'] is not None for r in budget['allocations'])
    assert sum(r['costCents'] for r in by_id.values())==60564103
    assert sum(r['costCents'] for r in budget['allocations'] if not r['classId'])==1582705
    for name in TARGETS:
        current=next(r for r in report['rows'] if r['name']==name)
        source=next(r for r in nominal['rows'] if r['name']==name)
        load=next(r for r in teaching['classes'] if r['class_name']==name)
        assert current['id'] not in by_id
        assert money(Decimal(str(load['weekly_cost']))*450)==current['teacherCents']
        assert len({a['occurrence_id'] for a in load['shared_allocations']})==len(load['shared_allocations'])
        normal_shared=sum(money(Decimal(str(a['weekly_cost']))*100) for a in load['shared_allocations'] if a['occurrence_id']!='O0789')
        excluded=27414 if name=='8º C' else 0
        shared_monthly=money(Decimal(normal_shared)*Decimal('4.5'))
        direct_monthly=current['teacherCents']-shared_monthly-excluded
        assert direct_monthly>=0
        parts=[dict(category='A',component='Docência em ocorrências exclusivas/complementos homologados',classCents=direct_monthly,
                    source='Extração nominal + grade oficial 2026 projetada; tarifas 2027; mensalização 4,5. Ajuste de centavos preserva total da turma.',budgetCoverage='Composição estrutural; não lançamento adicional'),
               dict(category='B',component='Aulas compartilhadas já conciliadas',classCents=shared_monthly,
                    source='Mesmas ocorrências/pools e frações financeiras registradas; somente parcela desta turma.',budgetCoverage='Já dentro do total docente; não repetir')]
        if excluded:parts.append(dict(category='D',component='Cobertura de ocorrências históricas administrativas do 8º C',classCents=excluded,
            source='O0731/O0732 Lohana AUX administrativo, 234,99; O0789 Marcelo integrante da folha, 39,15. Não são docentes/salários novos.',
            budgetCoverage='Existência das pessoas resolvida; não demonstrada equivalência entre tarifa histórica de ocorrência e parcela salarial já coberta'))
        for p in source['components']:
            if not p['verified'] or p['kind']=='docentes' or not p['cents']:continue
            parts.append(dict(category='A' if p['kind'] in ('estagiarias','auxiliar-direta') else 'B',component=p['kind'],classCents=p['cents'],source=p['evidence'],budgetCoverage='Composição nominal homologada dentro do envelope; não adicionar'))
        stage='FII' if name=='8º C' else 'FI'
        pool=budget['payrollTests'][stage]
        parts.append(dict(category='C',component='Ligação da turma ao pool de folha do segmento',classCents=None,poolCents=pool['totalCents'],
            source=f"Orçamento p.4: segmento {stage}, divisor {pool['students']} alunos previstos; turma atual pertence ao segmento; peso da seção ausente/zero na fonte.",
            budgetCoverage='Orçamento do segmento existente; vínculo ao pool comprovado, quinhão da turma não determinado. Valor do pool é referência não aditiva.'))
        parts.append(dict(category='C',component='Serviços escolares/apoio e gerais já orçados',classCents=None,poolCents=None,
            source='Orçamento p.4,6–7,12–15: pools escolares; apoio por receita bruta e gerais por receita. Mesma escola/unidade; falta participação financeira da seção.',
            budgetCoverage='Existência e destinação escolar comprovadas; não significa rateio individual determinado.'))
        parts.append(dict(category='D',component='Peso e contrapartida para integrar a turma no rateio financeiro',classCents=None,
            source='Não há linha financeira positiva para a seção; base local sem costLines/rateioRules ativos cadastrados.',
            budgetCoverage='Definir origem dentro do orçamento já distribuído: peso estrutural da turma e parcela a retirar dos demais destinos. Não usar matrícula atual automaticamente.'))
        partial=sum(p['classCents'] or 0 for p in parts if p['category'] in ('A','B'))
        assert partial+excluded==sum(p['cents'] for p in source['components'] if p['verified'])
        peers=[]
        for other in report['rows']:
            if other['name'].split()[0]!=name.split()[0]:continue
            assignment=by_id.get(other['id'])
            t=next(t for t in teaching['classes'] if t['class_id']==other['id'])
            own_shared={a['occurrence_id'] for a in load['shared_allocations']}
            peers.append(dict(name=other['name'],teacherCents=other['teacherCents'],costCents=other['consideredCostCents'],
                assignment=assignment,sharedOccurrences=sorted(own_shared & {a['occurrence_id'] for a in t['shared_allocations']})))
        rows.append(dict(name=name,classId=current['id'],parts=parts,peers=peers,teachers=load['teacher_costs'],
            sharedAllocations=load['shared_allocations'],weeklyCost=load['weekly_cost'],weeklyMinutes=load['weekly_minutes'],
            totalStructuralTeacherCents=current['teacherCents'],locatedABCents=partial,historicalAdminOccurrenceCents=excluded,
            integralCostBefore=current['consideredCostCents'],integralCostAfter=None,peBefore=current['pe'],peAfter=None,
            ticketCents=current['ticketCents'],capacity=current['capacity'],enrolled=current['enrolled'],
            sourceMapProblem='LINHA_AUSENTE' if source['document'] is None else 'LINHA_ZERADA_EXCLUIDA_POR_FILTRO',
            closeByLinkOnly=False))
    pools=[]
    for stage in ['FI','FII']:
        allocations=[r for r in budget['allocations'] if r['segment']==stage]
        pools.append(dict(segment=stage,positiveBudgetRows=len(allocations),
            activeRecipients=sum(r['classId'] is not None for r in allocations),
            sourceForecastStudents=sum(r['students'] for r in allocations),
            assignedCostCents=sum(r['costCents'] for r in allocations if r['classId']),
            legacyReserveCents=sum(r['costCents'] for r in allocations if not r['classId'])))
    return dict(rows=rows,pools=pools,addedCostCents=0,redistributedCostCents=0,legacyReserveCents=1582705,
                assignedCostCents=60564103,economicEnvelopeCents=62146808,closure='NO-GO')

def main():
    OUT.mkdir(exist_ok=True)
    paths=['output/pe-administrativo-aprovado-20270922/resultado-administrativo.json','pe_layers_2027_source.json',
           'output/desbloqueio-pe-2027/docencia-reconstruida.json','output/pe-real-2027/reconciliacao-custos.json']
    data=reconcile(*[read(p) for p in paths]);data['hashes']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    (OUT/'cobertura.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Orçamento distribuído × quatro turmas — relatório para aprovação','',
      '**Conclusão: há cobertura econômica em pools escolares e custos diretos/compartilhados identificados. Não se presumiu ausência de custo. Nenhuma das quatro turmas pode receber custo INTEGRAL somente por corrigir uma chave de vínculo: falta a regra/contrapartida para repartir o orçamento já distribuído.** Nenhuma nova despesa ou alteração de PE aplicada.', '',
      '## Por que as paralelas têm PE e as quatro turmas não','',
      'Causa determinística: scripts/reconcile_pe_real_costs.py seleciona sourceRows com students > 0, associa o nome documental ao classId e gera as alocações. apply_costs() procura esse classId; se não existe, define consideredCostCents/pe como None e preserva nominalCosts. Não zera salários nem conclui que a turma não tem custo.',
      '1º D, 2º D e 3º D não têm linha própria na p.4; 8º C tem linha zerada e é excluído pelo filtro positivo. A função source_name() normaliza corretamente 1º D→1º Ano D e 8º C→8º Ano C. Os IDs aparecem na carga, benefícios/cadastro e memória nominal. Portanto, não é erro de grafia, importação de turma ou desaparecimento do professor: é incompatibilidade entre a abrangência do orçamento e a estrutura operacional.',
      'Os planos financeiros locais estão vazios (budget=[], breakEven.plans=[], revenuePlanning.years={}); não existe outro lançamento mapeado oculto que complete a ponte. O valor de cada paralela é uma parcela do orçamento por alunos previstos/receita, não a soma do seu conjunto individual de professores. Por isso, não se pode deduzir automaticamente o custo de D da diferença entre folha orçada e docência de A/B/C.', '',
      '## Classificação exclusiva das parcelas','',
      'A = custo direto atribuído; B = compartilhamento/rateio nominal já reconhecido; C = vínculo demonstrado com orçamento existente, no nível de pool; D = quinhão/contrapartida ou correspondência econômica ainda não demonstrados. C com valor por turma indeterminado não é custo zero nem autorização para dividir o pool. Cada linha recebe uma só letra; pools de C são referências não aditivas aos itens A/B.', '']
    for r in data['rows']:
        lines += [f"## {r['name']}",'',f"Capacidade {r['capacity']}; matriculados {r['enrolled']}; ticket líquido R$ {br(r['ticketCents'])}. Custo docente estrutural preservado R$ {br(r['totalStructuralTeacherCents'])}/mês. Custo integral e PE: NÃO DETERMINADOS.",'',
          '| Situação | Componente | Valor por turma R$/mês | Origem e cobertura |','|---|---|---:|---|']
        for p in r['parts']:
            pool=f" Pool de referência R$ {br(p['poolCents'])}, não somar por turma." if p.get('poolCents') else ''
            lines.append(f"| {p['category']} | {p['component']} | {br(p['classCents'])} | {p['source']} {p['budgetCoverage']}{pool} |")
        lines += ['', '| Autor da ocorrência na fonte | Disciplinas | Aulas equivalentes/semana | Custo semanal R$ | Vínculo |',
                  '|---|---|---:|---:|---|']
        for t in r['teachers']:
            non=t['professor'] in ('Lohana Rodrigues Leite da Silva','Marcelo Rodrigues')
            link=('Histórico, NÃO docente: Lohana AUX Administrativo; Marcelo na folha. Sem salário novo.' if non else ','.join(t.get('occurrence_ids',[])) or t.get('evidence','Regência homologada'))
            lines.append(f"| {t['professor']} | {', '.join(t['disciplines'])} | {t['weekly_lesson_equivalents']:.6g} | {br(Decimal(str(t['weekly_cost']))*100)} | {link} |")
        lines += ['', f"Tarifa FI R$ 16,20/FII R$ 26,11, conforme segmento; custo semanal conciliado R$ {r['weeklyCost']:.2f} × 4,5, com arredondamento total em centavos. Minutos documentais {r['weeklyMinutes']}; complementos em h/a não geram minutos inventados. Não recalcular pools aprovados a partir da soma aparente de aulas.",'',
                  '| Paralela | Docência estrutural R$ | Folha orçada R$ | Apoio R$ | Custo total orçado líquido R$ | Compartilhamentos reais |',
                  '|---|---:|---:|---:|---:|---|']
        for p in r['peers']:
            a=p['assignment'] or {}
            lines.append(f"| {p['name']} | {br(p['teacherCents'])} | {br(a.get('payrollCents'))} | {br(a.get('supportCents'))} | {br(p['costCents'])} | {', '.join(p['sharedOccurrences']) or 'Nenhum ID compartilhado em comum'} |")
        lines += ['', 'As frações compartilhadas já foram atribuídas à turma no ledger docente; não estão integralmente acumuladas na paralela. Para C29/FI, Anny/773: pool R$ 2.638,43 por capacidade congelada. Para C28/FI, Debora/846: pool R$ 2.746,13 entre 18 turmas. No 3º D, Sheila/881: R$ 853,77 (bolsa 759,00, seguro 19,35, consultoria 75,42), folha agosto p.48 e relação OF. Esses vínculos existem; não dependem de copiar pessoa ou custo de outra turma.' if r['name']!='8º C' else 'O compartilhamento O1235 já contém a fração de Simone no 8º C. O0789 é histórico sob Marcelo; vínculo de folha confirmado, mas tarifa de ocorrência não é salário. R$ 274,14 permanecem apenas como memória histórica, sem novo custo.', '',
          '**Dado faltante específico:** '+('peso orçamentário de 8º C na folha FII e na receita prevista usada para apoio/gerais; centro/pool de origem e parcela compensatória nas demais destinações. A existência do 8º C, de Marcelo na folha e a função de Lohana já estão resolvidas. A cobertura das ocorrências O0731/O0732/O0789 precisa ser ligada ao serviço/folha administrativa, não a novos docentes.' if r['name']=='8º C' else f"peso orçamentário de {r['name']} na folha FI e na receita prevista usada para apoio/gerais; qual parcela das alocações atuais já remunera sua docência/apoio e deve ser reatribuída, em vez de somada."),'']
    lines += ['## Concentração econômica e limites da prova','',
      '| Segmento | Linhas financeiras positivas | Destinos ativos | Alunos previstos no orçamento | Custo já alocado R$ | Reserva histórica R$ |','|---|---:|---:|---:|---:|---:|']
    for p in data['pools']:lines.append(f"| {p['segment']} | {p['positiveBudgetRows']} | {p['activeRecipients']} | {p['sourceForecastStudents']} | {br(p['assignedCostCents'])} | {br(p['legacyReserveCents'])} |")
    lines += ['', 'Há concentração MATEMÁTICA dos pools nas linhas financeiras positivas: as seções D e o 8º C recebem peso zero nessa camada. Isso demonstra que a distribuição não contempla todas as turmas ativas. Não demonstra que um valor nominal específico de D foi lançado indevidamente em determinada A/B/C. Os vínculos pessoa→ocorrência são distintos dos pesos financeiros do orçamento.',
      'Não há PE artificialmente baixo calculado para as quatro turmas: seus PEs são nulos, não zero. Os PEs das paralelas podem ser alterados por uma nova repartição aprovada, mas não é possível quantificar seu excesso atribuível às quatro sem o peso/contrapartida. A atual dotação alocada R$ 605.641,03 está integralmente distribuída. Com reserva fixa e sem novo custo, todo X atribuído às quatro exige retirar exatamente X de destinos atuais; não existe saldo livre certificado para somar.',
      'A folha das turmas paralelas inclui custo direto mais composição/serviços não individualizados. Subtrair a docência histórica desse bloco e chamar o saldo de custo de D seria uma aproximação não autorizada. Usar 775 matrículas atuais como novos pesos também recalcularia o custo estrutural por ocupação, contrariando as regras preservadas.', '',
      '## ANTES × RECONCILIADO','',
      '| Turma | Custo integral antes | A/B rastreados R$ | Ocorrência administrativa histórica D R$ | Custo integral reconciliado | PE antes/depois | Fecha apenas por vínculo? |',
      '|---|---|---:|---:|---|---|---|']
    for r in data['rows']:lines.append(f"| {r['name']} | Não determinado | {br(r['locatedABCents'])} | {br(r['historicalAdminOccurrenceCents'])} | Não determinado; pool identificado, quinhão não | Pendente / pendente | Não |")
    lines += ['', 'Resultado: 0 de 4 fechadas integralmente por mera correção de chave. O vínculo econômico com o orçamento foi explicitado, mas um rateio novo não pode ser disfarçado como vínculo já comprovado. A/B rastreados são composição, não novos custos; C contém pools já existentes; D delimita o que falta para obter o numerador integral.',
      'Pedido único para decisão financeira: fornecer/aprovar o de-para de DISTRIBUIÇÃO do orçamento existente para as quatro turmas, com pesos estruturais, pool/centro de origem e redução compensatória das alocações atuais. Não se pede salário, carga ou professor genericamente. Para 8º C, anexar a correspondência das três ocorrências administrativas à cobertura já na folha; não reconfirmar pessoas nem criar salário.',
      'A reserva de R$ 15.827,05 não foi reclassificada, distribuída ou consumida nesta etapa. Custos adicionados/redistribuídos/excluídos: R$ 0,00. PEs calculáveis preservados; 41 turmas, 775 matriculados, capacidade 1.103, vagas 328. Sem banco, produção, acesso remoto, Supabase, deploy, push ou publicação. Relatório para aprovação humana; NO-GO integral permanece.']
    (OUT/'ANTES-X-RECONCILIADO.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(rows=[(r['name'],r['locatedABCents']) for r in data['rows']],pools=data['pools']),ensure_ascii=True))
if __name__=='__main__':main()
