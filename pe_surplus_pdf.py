"""Renderer for the shared surplus/deficit view; no independent PE engine."""
from io import BytesIO
from decimal import Decimal as D
from html import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from pe_analytic_pdf import cash

def render_surplus_pdf(model):
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='cell',fontSize=7,leading=9))
    styles['BodyText'].fontSize=9;styles['BodyText'].leading=12
    p=lambda text,style='BodyText':Paragraph(escape(str(text)),styles[style])
    rows=model['rows'];s=model['surplusSummary'];story=[];width=landscape(A4)[0]-64
    def section(text):story.extend([Spacer(1,10),p(text,'Heading2')])
    def table(head,data,weights=None):
        weights=weights or [1]*len(head)
        t=Table([[p(c,'cell') for c in head]]+[[p(c,'cell') for c in row] for row in data],
            colWidths=[width*x/sum(weights) for x in weights],repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dbe8f1')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#b4c3ce')),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        story.append(t)
    story.extend([p('RELATÓRIO DE SUPERÁVIT E DÉFICIT - PE 2027','Title'),p('COLÉGIO ADVENTISTA DE JUAZEIRO','Heading2'),p(model.get('presentationLabel','Candidata local - não publicada')+'. Gerado em '+model['generatedAt']),p(model['currentResultNote'])])
    story.append(p(model['functionalAllocationNote']))
    section('1. Resumo executivo')
    table(['Indicador','Atual comprovável','Estrutural / capacidade máxima'],[
        ['Turmas',f"{s['currentKnown']} comprováveis; {s['currentPending']} pendentes",str(s['classes'])],
        ['Superavitárias',s['currentSurplus'],s['belowCapacity']],['No equilíbrio / limite',s['currentEqual'],s['equalCapacity']],['Deficitárias',s['currentDeficit'],s['aboveCapacity']],
        ['Superávit mensal',cash(s['currentSurplusCents'])+' (somente comprováveis)',cash(s['structuralSurplusCents'])],
        ['Déficit mensal',cash(s['currentDeficitCents'])+' (somente comprováveis)',cash(s['structuralDeficitCents'])],
        ['Saldo parcial comprovável',cash(s['currentKnownNetCents']), '—'],
        ['Saldo consolidado das 41',cash(s['currentAllNetCents']) if s['currentAllNetCents'] is not None else 'PENDENTE: receita atual incompleta',cash(s['structuralNetCents'])],
        ['Custo econômico preservado',cash(s['costCents']),cash(s['costCents'])],['Reserva separada',cash(model['summary']['reservaCentavos']),'Não integra o custo das turmas']],[1.2,2,2])
    story.append(p('A classificação estrutural segue PE versus capacidade. Turmas no limite podem ter saldo monetário positivo por causa do arredondamento para cima do PE. Não são movidas para a categoria superavitária.'))
    story.append(p(model['roundingNote']))
    section('2. Grupos e pendências')
    for label,predicate in [
        ('Superavitárias hoje',lambda r:r['currentStatus']=='SUPERAVITÁRIA'),('Deficitárias hoje',lambda r:r['currentStatus']=='DEFICITÁRIA'),
        ('Estruturalmente superavitárias',lambda r:r['peCorrigido']<r['capacidade']),('PE acima da capacidade',lambda r:r['peCorrigido']>r['capacidade']),
        ('PE igual à capacidade',lambda r:r['peCorrigido']==r['capacidade']),('Pendentes documentais (status das 15 turmas)',lambda r:r['documentaryPending']),
        ('Resultado atual pendente de vínculo',lambda r:r['currentRevenueCents'] is None)]:
        story.append(p(label+': '+(', '.join(r['turma'] for r in rows if predicate(r)) or 'Nenhuma')+'.'))
    story.append(PageBreak());section('3. As 41 turmas - posição atual')
    table(['Turma / segmento','Cap.','Matric. / vagas','Mensalidade','Ticket estrutural','Receita atual','Custo mensal','Resultado atual','Status atual'],[
        [r['turma']+' / '+r['segmentCode'],r['capacidade'],f"{r['matriculados']} / {r['vagas']}",cash(r['tuitionCents']),cash(r['ticketLiquidoCentavosExato']),cash(r['currentRevenueCents']) if r['currentRevenueCents'] is not None else 'PENDENTE',cash(r['custoTotalCentavos']),cash(r['currentBalanceCents']) if r['currentBalanceCents'] is not None else 'PENDENTE',r['currentStatus']] for r in rows],[.8,.4,.65,.8,.85,.8,.85,.85,1.1])
    story.append(p('RESULTADO ATUAL PENDENTE DE VÍNCULO DE BENEFÍCIOS: não foi calculada receita usando benefícios previstos como ativos.'))
    story.append(PageBreak());section('4. As 41 turmas - resultado estrutural')
    table(['Turma','PE','Matric. − PE','Receita máxima','Resultado máximo','PE / cap.','Margem física','Status estrutural','Status documental'],[
        [r['turma'],r['peCorrigido'],r['studentsVersusPE'],cash(r['capacityRevenueCents']),cash(r['capacityBalanceCents']),f"{r['percentualCapacidade']:.2f}%",r['margemFisica'],r['structuralStatus'],r['status']] for r in rows],[.6,.35,.6,.9,.9,.6,.5,1.6,2])
    story.append(PageBreak());section('5. Benefícios previstos x ativos')
    table(['Turma','Ativos/vinculados comprovados','Previstos/inativos','Base do ticket'],[[r['turma'],r['benefitStateCounts']['activeLinked'],r['benefitStateCounts']['plannedInactive'],r['planningTicketNote']] for r in rows],[.6,.9,.8,3])
    story.append(p('Ativo/vinculado exige evidência nominal; a fonte examinada não comprova tais vínculos. Premissas gerenciais não são benefícios individuais.'))
    story.append(PageBreak());section('6. Auditoria dos rateios e maiores componentes')
    selected=[r for r in rows if r['allocationAuditRequired']]
    table(['Turma','Docência %','Aux. %','Outros %','Segmento %','Global %','Rateios totais %','Maior componente'],[
        [r['turma'],*[f"{D(r['componentPercentages'][k]):.2f}%" for k in ['Docentes','Auxiliares/estagiárias','Outros diretos','Rateio do segmento','Rateio global']],f"{D(r['allocationPercent']):.2f}%",max(r['components'],key=lambda c:c['cents'])['label']] for r in selected])
    section('7. Possível concentração de rateio')
    story.append(p(model['auditRule']['criterion']))
    table(['Turma','Rateio por vaga','Média dos outros pares','Diferença','Diferença %'],[[r['turma'],cash(r['allocationPerSeatCents']),cash(r['concentration']['peerMeanCents']),cash(r['concentration']['differenceCents']),f"{D(r['concentration']['differencePercent']):.2f}%"] for r in rows if r['concentration']['flagged']] or [['Nenhum alerta','—','—','—','—']])
    story.append(p('O detector não altera valores nem decide que a alocação está errada. Ausência de alerta não homologa o rateio.'))
    groups=sorted({r['comparisonGroup'] for r in selected})
    for group in groups:
        section('Comparação de equivalentes: '+group)
        table(['Turma','Cap.','Docência','Auxiliares','Segmento','Global','Custo total','Rateio/vaga','Ticket','PE'],[
            [r['turma'],r['capacidade'],cash(r['docenteCentavos']),cash(r['auxEstagiariaCentavos']),cash(r['rateioSegmentoCentavos']),cash(r['rateioGlobalCentavos']),cash(r['custoTotalCentavos']),cash(r['allocationPerSeatCents']),cash(r['ticketLiquidoCentavosExato']),r['peCorrigido']] for r in rows if r['comparisonGroup']==group],[.6,.35,.8,.8,.8,.8,.85,.8,.75,.35])
    story.append(PageBreak());section('8. Caso de auditoria: 6º C')
    r=next(r for r in rows if r['turma']=='6º C');story.append(p(r['structuralExplanation']))
    table(['Componente conhecido','Valor','Participação','Situação'],[
        ['Docência',cash(r['docenteCentavos']),f"{D(r['componentPercentages']['Docentes']):.2f}%",'Âncora preservada da engine'],
        ['Saldo gerencial de folha e apoio - segmento',cash(r['rateioSegmentoCentavos']),f"{D(r['componentPercentages']['Rateio do segmento']):.2f}%",'PARCELA GERENCIAL PENDENTE DOCUMENTAL'],
        ['Quota líquida de despesas gerais - global',cash(r['rateioGlobalCentavos']),f"{D(r['componentPercentages']['Rateio global']):.2f}%",'PARCELA GERENCIAL PENDENTE DOCUMENTAL']],[1.7,1,.8,2])
    b=r['sourceBridge']
    story.append(p(f"Segmento: folha {cash(b['payrollCents'])} + apoio {cash(b['supportCents'])} − docência {cash(r['docenteCentavos'])} = {cash(r['rateioSegmentoCentavos'])}. Global: gerais {cash(b['generalCents'])} − PCLD {cash(b['pcldRemovedCents'])} − descontos orçamentários {cash(b['discountReclassifiedCents'])} = {cash(r['rateioGlobalCentavos'])}. São blocos de origem, não identificação inventada de contas individuais."))
    section('9. Explicação das 41 turmas')
    for r in rows:story.extend([p(r['turma'],'Heading3'),p(r['structuralExplanation']),p(r['currentNote'])])
    section('10. Observações metodológicas e rastreabilidade')
    story.append(p('Multiplicador docente 4,5; inadimplência 4,5% uma vez; benefícios/descontos uma vez. PCLD R$ 42.117,80 neutralizada somente no PE gerencial. Matrículas não participam da fórmula do PE. Nenhuma conta, custo, rateio ou benefício foi alterado pelo relatório.'))
    story.append(p('As 15 turmas mantêm VALIDADO MATEMATICAMENTE / RATEIO GERENCIAL PENDENTE DOCUMENTAL. Nas demais, a preservação gerencial também não comprova cada conta.'))
    story.append(p(model['currentResultNote']));story.append(p(model['roundingNote']))
    story.append(p('Fontes: mesma composição analítica da candidata local; orçamento 2027; matriz histórica e fonte privada de benefícios. Data do artefato: '+model['calculationAt']+'. SHA-256: '+model['snapshotSha256']))
    stream=BytesIO()
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('Helvetica',7);canvas.drawString(32,18,'7&7 | '+model.get('presentationLabel','Candidata local, não publicada')+' | Valores preservados');canvas.drawRightString(landscape(A4)[0]-32,18,str(doc.page));canvas.restoreState()
    SimpleDocTemplate(stream,pagesize=landscape(A4),leftMargin=32,rightMargin=32,topMargin=30,bottomMargin=32,title='Superávit e Déficit - PE 2027').build(story,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()
