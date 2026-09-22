"""Saneamento incremental. Reutiliza motor, documentos e critérios já conciliados."""
import json
import sys
import re
from copy import deepcopy
from collections import defaultdict, Counter
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pe_real import AUDIT, calculate, normalized, money, class_key, ceil_ratio
from enrollment_2027 import project_current
from scripts.audit_pe_real import br, write
from scripts.reconcile_pe_real_costs import reconcile, apply_costs


def sanitize_records(records, research):
    """Correção nominal explícita corroborada; sem progressão e sem soma de bolsas."""
    result=deepcopy(records); resolutions=[]
    export=next(x for x in research['sources'] if Path(x['path']).name=='Descontos 2027 - ABN  CAJ.xlsx')
    rates={275:Decimal('.45'),276:Decimal('.45'),482:Decimal('.95'),697:Decimal('.5')}
    for r in result:
        if r['sourceRow'] not in rates:continue
        match=next(m for m in export['matches'] if r['studentKey'] in m['targets'])
        values=match['values'];rate=rates[r['sourceRow']]
        assert normalized(values[5])==r['studentKey'] and values[11]==r['benefit']
        assert str(values[12])==str(r['scholarshipRaw'])
        old_tuition=113744 if str(values[7]).startswith('EFUND06') else 88502
        assert money(Decimal(old_tuition)*(1-rate))==money(Decimal(str(values[13]))*100)
        if r['sourceRow']==482:
            assert Decimal(str(r['conditionalRaw']))==rate
            rule='Percentual individual explícito 95% (G482), corroborado por cobrança histórica de 44,25 sobre 885,02. Não inferido pela soma de 50 e 45; não generalizar.'
        else:
            assert Decimal(str(r['scholarshipRaw']))/100==rate
            rule='Benefício nominal e percentual de bolsa explícitos prevalecem sobre G divergente, conforme comando de saneamento; exportação nominal corrobora.'
        r.update(rate=str(rate),discountCents=money(Decimal(r['grossCents'])*rate))
        r['postDiscountCents']=r['grossCents']-r['discountCents']
        r['issues']=[i for i in r['issues'] if i not in ('BOLSA E CONDICIONAL DIVERGENTES','BENEFÍCIO NÃO CLASSIFICADO OU ACUMULAÇÃO SEM REGRA')]
        r['benefitValid']=not [i for i in r['issues'] if i!='SEM CORRESPONDÊNCIA DE TURMA']
        r['valid']=not r['issues'];r['resolutionRule']=rule
        resolutions.append(dict(row=r['sourceRow'],student=r['student'],studentId=values[3],sourceClass=r['sourceClass'],
            benefit1=r['benefit']+' / '+str(r['scholarshipRaw']),benefit2=str(r['conditionalRaw']),
            source1=f"{r['source']}:Todos os Descontos!E{r['sourceRow']}:G{r['sourceRow']}",
            source2=f"{export['path']}:Export!L{match['row']}:N{match['row']}",rule=rule,rate=str(rate),
            historicalChargedCents=money(Decimal(str(values[13]))*100),historicalTuitionCents=old_tuition,
            discount2027Cents=r['discountCents'],status='COMPROVADO'))
    return result,resolutions


def normalized_label(code):
    m=re.fullmatch(r'(EINFA|EFUND|EMERE)(\d{2})[MT]([A-D])',str(code))
    if not m:return None
    kind,grade,letter=m.groups();grade=int(grade)
    return f'G{grade} {letter}' if kind=='EINFA' else f'{grade}º EM {letter}' if kind=='EMERE' else f'{grade}º {letter}'


def class_exceptions(records, data):
    names={r['name'] for r in data['rows']}
    items=[]
    for r in records:
        if r['classId'] is not None:continue
        label=normalized_label(r['sourceClass'])
        assert label not in names # nenhuma equivalência simples ficou por aplicar
        items.append(dict(id=f"Todos os Descontos:{r['sourceRow']}",student=r['student'],sourceClass=r['sourceClass'],
            normalizedClass=label,status='EM AUDITORIA',
            reason='Série e letra preservadas; não existe essa turma nas 41 linhas numéricas do PDF atual. Mudança de letra/série seria transferência, não normalização.',
            grossCents=r['grossCents'],discountCents=r['discountCents']))
    return items


def financial_ledger(costs):
    entries=[]
    for a in costs['accounts']:
        if a['code']=='4124001':continue # já fora do saldo de abertura de 623.208,36
        category='C' if a['code'] in ('4126005','4126007') else 'D'
        entries.append(dict(account=a['code'],rubric=a['description'],cents=a['monthlyCents'],category=category,
            source=f"Orçamento 2027 p.{a['sourcePage']}",segment=a['segmentAllocationCents'],
            classDestination='Blocos documentais p.4; composição conta→pessoa→turma não certificada' if a['code'].startswith('411') else 'Receita bruta prevista por turma p.4; 7º C sem destino atual',
            criterion=a['criterion'],scope=a['scope'],
            proof='Valor orçado e critério de bloco; não é comprovação nominal',
            treatment='Fora do custo econômico: benefício já representado no ticket individual; conta contábil preservada' if category=='C' else 'Compartilhado conforme demonstrações do orçamento'))
    entries += [dict(account='CONTROLE_NOMINAL_ANTERIOR',rubric='Dedução da parcela já reconhecida antes do saldo 623.208,36; sem atribuição fictícia às rubricas',cents=-17616080,category='D'),
                dict(account='ARREDONDAMENTO_OFICIAL',rubric='Analítico geral para total oficial',cents=-4,category='D'),
                dict(account='DESTINO_7C_SAIDA_D',rubric='Reclassificar parcela sem destino atual para E',cents=-1582705,category='D'),
                dict(account='DESTINO_7C_ENTRADA_E',rubric='7º Ano C documental sem turma correspondente',cents=1582705,category='E')]
    totals={k:sum(e['cents'] for e in entries if e['category']==k) for k in 'ABCDE'}
    assert sum(totals.values())==62320836
    assert totals==dict(A=0,B=0,C=17790108,D=42948023,E=1582705)
    return dict(entries=entries,totals=totals,
        note='B=0 é ausência de baixa nova por identidade de evento comprovada, não prova de inexistência de sobreposição. PCLD já excluída da abertura. C são estimativas contábeis substituídas no ticket. D é conciliação financeira agregada, não fechamento nominal.')


def personnel_groups(costs):
    groups=defaultdict(lambda:dict(cents=0,accounts=[]))
    for a in costs['accounts']:
        code=a['code']
        if not code.startswith('411'):continue
        group=('ESTAGIÁRIOS' if code=='4119040' else 'SERVIÇOS DE TERCEIROS' if code.startswith('4119') and code!='4119520'
               else 'PROVENTOS E PROVISÕES' if code.startswith('4111') else 'ENCARGOS' if code.startswith('4112')
               else 'ENCARGOS PESSOAIS' if code.startswith('4114') else 'OUTROS COMPONENTES')
        groups[group]['cents']+=a['monthlyCents'];groups[group]['accounts'].append(code)
    assert sum(x['cents'] for x in groups.values())==38759193
    return dict(groups)


def bounds(data,records):
    result=[]
    for r in data['rows']:
        group=[x for x in records if x['classId']==r['id']]
        missing=[x for x in group if not x['valid']]
        knownpost=sum(x['postDiscountCents'] for x in group if x['valid'])
        n=len(group);cost=r['consideredCostCents']
        if cost is not None and n:
            netmin=money(Decimal(knownpost)*Decimal('.955'))
            netmax=money(Decimal(knownpost+sum(x['grossCents'] for x in missing))*Decimal('.955'))
            low=ceil_ratio(cost*n,netmax);high=ceil_ratio(cost*n,netmin)
            scope='Variação apenas dos benefícios pendentes encontrados; não cobre alunos ausentes nem custo adicional desconhecido.'
        elif cost is not None:
            low=ceil_ratio(cost*1000,r['tuitionCents']*955);high=None
            scope='Custo orçado fixo; mix ausente entre 0% e 100% de benefício. Limite superior não finito, inclusive receita zero.'
        else:low=high=None;scope='Numerador sem ponte financeira; PE total não delimitável.'
        result.append(dict(id=r['id'],name=r['name'],minimumPE=low,maximumPE=high,
            unknownBenefits=len(missing),scope=scope,
            additionalKnownReserveImpactCeiling=ceil_ratio(1582705*r['acceptedStudentCount'],r['netRevenueCents']) if r['ticketCents'] else None))
    return result


def main():
    prior=json.loads((AUDIT/'resultado.json').read_text(encoding='utf-8'))
    if not (AUDIT/'resultado-antes-saneamento.json').exists():write('resultado-antes-saneamento.json',prior)
    research=json.loads((AUDIT/'pesquisa-saneamento.json').read_text(encoding='utf-8'))
    records,resolutions=sanitize_records(json.loads((AUDIT/'registros-locais.json').read_text(encoding='utf-8')),research)
    data=calculate(records,allow_partial_mix=True)
    for key in ('source','manifest','discountBridge'):data[key]=deepcopy(prior[key])
    data['sanitation']=dict(resolvedBenefits=len(resolutions),secondProgressionApplied=False,
        policy='Somente benefício individual nominal comprovado; matrícula não altera PE.',partialMixPermitted=True,
        benefitCategories={'Marcando Vidas':'45% uma única vez','Bolsa filantrópica':'50% uma única vez'},
        userClarification='Marcando Vidas 45% não se repete como 45% + 45%; 50% é bolsa filantrópica.')
    costs=reconcile();data=apply_costs(data,costs);data=project_current(data)
    data['summary']['allValidatedWorkbookDiscountCents']=sum(x['discountCents'] for x in records if x['benefitValid'])
    data['summary']['confirmed']=0
    data['sanitation']['financialLedger']=financial_ledger(costs)
    data['sanitation']['personnelGroups']=personnel_groups(costs)
    data['sanitation']['bounds']=bounds(data,records)
    # Benefícios individualizados ficam no arquivo local; resposta da API só contém agregados.
    exceptions=class_exceptions(records,data)
    data['exceptions']=dict(unmapped=dict(Counter(x['sourceClass'] for x in exceptions)),invalidBenefits=[],duplicateStudents=0)
    groups=defaultdict(lambda:dict(count=0,discountCents=0,rows=[]))
    for r in records:
        if r['benefitValid']:
            groups[r['benefit']]['count']+=1;groups[r['benefit']]['discountCents']+=r['discountCents'];groups[r['benefit']]['rows'].append(r['sourceRow'])
    data['discountBridge']['benefits']=dict(groups)
    data['discountBridge']['treatment']='Contas contábeis preservadas; 4126005/4126007 fora do numerador e sem desconto comercial estrutural adicional. Identidade por evento não certificada.'
    data['discountBridge']['grossDifferenceAgainstFinancialAccountsCents']=data['summary']['allValidatedWorkbookDiscountCents']-17790108
    for x in data['discountBridge']['scholarshipComparisons']:
        rate='1' if x['candidateAccount']=='3149121' else '0.5'
        x['individualCents']=sum(r['discountCents'] for r in records if r['benefitValid'] and r['benefit']=='CEBAS - Ebolsa' and r['rate']==rate)
        x['differenceCents']=x['individualCents']-x['budgetCents']
    write('registros-saneados-locais.json',records);write('normalizacao-114.json',exceptions)
    write('conflitos-resolvidos.json',resolutions);write('classificacao-centavos.json',data['sanitation']['financialLedger'])
    write('ponte-descontos.json',data['discountBridge']);write('resultado.json',data)
    render_sanitation(data,exceptions,resolutions,research)
    render_personnel(costs)
    print(json.dumps(dict(summary=data['summary'],enrollment=data['enrollmentSummary'],resolved=len(resolutions)),ensure_ascii=True))


def render_personnel(costs):
    historical=json.loads((ROOT/'output/reconciliacao-pendencias-pe-2027/reconciliacao.json').read_text(encoding='utf-8'))
    payroll={str(p['code']):p for p in historical['payroll']}
    rows=[]
    for p in costs['historicalPayroll']:
        h=payroll.get(str(p['code']))
        treatment=('Substitui Romilton; um posto; verba 2027 não localizada' if str(p['code'])=='952' else
                   'Posto adicional; verba 2027 não localizada' if str(p['code']) in ('953','955') else
                   'Composição histórica; não somar à conta orçada nem inventar evolução salarial/lotação')
        for event in h['events'] if h else [dict(code='SEM_VERBA',description='Ausente da folha',valueCents=None,includedInPriorEconomicBasis=False)]:
            rows.append(dict(employeeCode=p['code'],employee=p['person'],role=p['role'],department=p['department'],
                rosterSource=p['rosterCell'],historicalClassGroup=p['classGroup'],payrollPage=p['payrollPage'],
                event=event,treatment2027=treatment))
    write('pessoal-rubricas-2027.json',rows)
    text=['# Pessoal — cruzamento nominal por rubrica','',
        'Alvo financeiro 2027: R$ 387.591,93. Folha de agosto é composição histórica. Não somar as verbas desta tabela ao orçamento; valores negativos, imunidades, adiantamentos e provisões mantêm o tratamento auditado anterior. O valor de folha não é líquido recebido nem automaticamente custo 2027.','',
        'Romilton/679 permanece apenas no histórico original; não está no cadastro ativo cruzado. Jailane/952 ocupa o posto substituto uma única vez. Lohana continua Auxiliar de Coordenação; Marcelo não foi inserido na base docente. Decisões de 50 docentes, 4,5 e carga oficial não foram modificadas.','',
        '| Código | Funcionário | Função | Departamento | Rubrica | Valor histórico R$ | Integra base histórica? | Fonte | Tratamento 2027 |',
        '|---|---|---|---|---|---:|---|---|---|']
    for r in rows:
        e=r['event'];values=[r['employeeCode'],r['employee'],r['role'],r['department'],str(e['code'])+' '+e['description'],br(e['valueCents']),e['includedInPriorEconomicBasis'],f"Folha agosto p.{r['payrollPage']}; cadastro {r['rosterSource']}",r['treatment2027']]
        text.append('| '+' | '.join(str(v).replace('|',' / ') for v in values)+' |')
    (AUDIT/'PESSOAL_RUBRICAS_2027.md').write_text('\n'.join(text)+'\n',encoding='utf-8')


def render_sanitation(data,exceptions,resolutions,research):
    text=['# Saneamento documental incremental','',
        f"{len(research['sources'])} fontes locais adicionais pesquisadas; {len(research['previousResults'])} resultados anteriores com referências pertinentes. Manifesto e ocorrências: pesquisa-saneamento.json. Originais intactos.",'',
        '## 114 registros: normalização sem transferência','',
        'Zero correspondências novas seguras: as letras ausentes não viram outras turmas. Não se aplicou nova progressão. Todos individualizados abaixo. Identificadores de linha são estáveis na planilha atualizada.','',
        '| Aluno / ID da linha | Turma original | Turma normalizada | Status | Motivo |','|---|---|---|---|---|']
    for r in exceptions:text.append(f"| {r['student']} / {r['id']} | {r['sourceClass']} | {r['normalizedClass']} | {r['status']} | {r['reason']} |")
    text+=['','## Quatro conflitos resolvidos','',
        'A exportação nominal está nas séries anteriores; foi usada apenas para corroborar benefício e cobrança, nunca para regredir/progredir novamente ou substituir a mensalidade 2027. Sua coluna N chama-se Mensalidade. Bases históricas 885,02 / 1.137,44 constam no orçamento p.2, linha Atual.','',
        '| Aluno / ID | Turma | Benefício nominal | Condicional divergente | Fonte 1 | Fonte 2 | Regra | Resultado |','|---|---|---|---|---|---|---|---|']
    for r in resolutions:
        values=[r['student']+' / '+r['studentId'],r['sourceClass'],r['benefit1'],r['benefit2'],r['source1'],r['source2'],r['rule'],str(Decimal(r['rate'])*100)+'% — '+r['status']]
        text.append('| '+' | '.join(str(v).replace('|',' / ') for v in values)+' |')
    text+=['','## Ponte financeira A–E','',data['sanitation']['financialLedger']['note'],'',
        'R$ 623.208,36 − A 0,00 − B 0,00 − C 177.901,08 − D 429.480,23 = E 15.827,05.','',
        '| Conta/controle | Rubrica | Valor R$ | Classe | Fonte | Segmento/turma | Critério | Tratamento |','|---|---|---:|---|---|---|---|---|']
    for x in data['sanitation']['financialLedger']['entries']:
        text.append('| '+' | '.join(str(v).replace('|',' / ') for v in [x['account'],x['rubric'],br(x['cents']),x['category'],x.get('source','Controle explícito'),x.get('classDestination','Controle global, não lotação'),x.get('criterion','Não ratear'),x.get('treatment','Ajuste rastreável')])+' |')
    text+=['','## Pessoal — alvo 387.591,93','',
        '| Grupo | Contas | Valor R$ |','|---|---|---:|']
    for k,v in data['sanitation']['personnelGroups'].items():text.append(f"| {k} | {', '.join(v['accounts'])} | {br(v['cents'])} |")
    text+=['','As provisões de 13º incluem encargos na própria rubrica: não foram desmembradas por estimativa nem somadas novamente. Serviços de estágio separados dos demais terceiros. Folha nominal com funcionário/função/departamento/rubricas: ../reconciliacao-pendencias-pe-2027/NOMINAL-AGOSTO.md e reconciliacao.json. Não equiparar valores de agosto ao orçamento 2027.','',
        'Paula Araujo Dias/955 não é Ana Paula docente. Paula, Jailane/952 e Veroneide/953 aparecem no cadastro atual, mas sem verbas na folha de agosto. A pesquisa adicional não trouxe seus custos. Romilton/679 histórico não foi reinserido. Substituição preserva um posto, não duas pessoas simultâneas. Não se pode afirmar que Paula é a única lacuna nominal enquanto faltam as verbas dos outros dois novos vínculos.','',
        'Nenhum contrato/tabela encontrado prova bolsa uniforme da categoria de Paula com jornada e encargos equivalentes; o saldo de estágio 2.863,57 não é seu salário. Contas agregadas estão no envelope, sem somar novamente os postos.','',
        '## Contas e benefícios','',
        'PCLD neutralizada no PE para evitar dupla incidência com inadimplência. Conta 4124001 mantém 42.117,80 no orçamento; parcela gerencial adicional zero. Contas 3182019 (2.805,00) e 3195130 (24.116,03) preservadas no documental e excluídas das receitas do PE real: não localizada comprovação de recorrência e disponibilidade.','',
        '| Conta | Valor orçado R$ | Benefício relacionado | Identificado na planilha R$ | Tratamento no PE | Diferença R$ |','|---|---:|---|---:|---|---:|',
        '| 3149026 | -34.646,32 | Comercial; sem chave nominal de conta | Não segregável | Não aplicar 3% nem nova dedução | Não conciliável por evento |',
        '| 4126005 | 48.388,20 | Financeiros concedidos | Não segregável | Estimativa fora do custo; redução individual uma vez | Não conciliável por evento |',
        '| 4126007 | 129.512,88 | Condicionais concedidos | Não segregável | Estimativa fora do custo; redução individual uma vez | Não conciliável por evento |',
        '| 3149111 / 3149114 | -57.719,94 / -6.212,62 | Funcionários/dependentes; dissídio não equiparado automaticamente | Não segregável | Bolsa no ticket, não custo | Não conciliável por evento |']
    for x in data['discountBridge']['scholarshipComparisons']:
        text.append(f"| {x['candidateAccount']} | -{br(x['budgetCents'])} | {x['benefit']} | {br(x['individualCents'])} | Natureza compatível; receita uma vez | {br(x['differenceCents'])} (universos diferentes) |")
    text+=['','A concessão composta da linha 482 é uma única redução de 95%; não é somada de novo aos subtotais de CEBAS/Marcando Vidas. Convênios/gratuidades sem vínculo de conta não receberam identidade inventada. Arquivo ponte-descontos.json mantém cada categoria e linhas. Nenhum valor contábil foi apagado.']
    (AUDIT/'SANEAMENTO_DOCUMENTAL.md').write_text('\n'.join(text)+'\n',encoding='utf-8')


if __name__=='__main__':main()
