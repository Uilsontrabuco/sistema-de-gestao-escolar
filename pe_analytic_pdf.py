"""PDF renderer: uses the same read-only model returned to the screen."""
from decimal import Decimal
from html import escape
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

def cash(value):
    if value is None:return 'Não demonstrado'
    return 'R$ '+f'{Decimal(str(value))/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')

def render_pdf(model, class_id=None):
    rows=model['rows'] if class_id is None else [r for r in model['rows'] if r['id']==class_id]
    if not rows:raise ValueError('Turma não encontrada.')
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Cell',fontName='Helvetica',fontSize=7,leading=9,spaceAfter=2))
    styles['BodyText'].fontSize=9;styles['BodyText'].leading=12
    def p(value,style='BodyText'):return Paragraph(escape(str(value)),styles[style])
    story=[]
    def section(title):story.extend([Spacer(1,10),p(title,'Heading2')])
    def table(headers,data,widths=None):
        content=[[p(c,'Cell') for c in headers]]+[[p(c,'Cell') for c in row] for row in data]
        t=Table(content,colWidths=widths or [511/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dae6f0')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#b4c1ce')),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        story.append(t)
    if class_id is None:
        story+=[p('RELATÓRIO GERAL PE 2027','Title'),p('Colégio Adventista de Juazeiro'),p(model.get('presentationLabel','Candidata local - não publicada')+'. Relatório confidencial. Valores iguais aos exibidos na tela.')]
        story.append(p(model['functionalAllocationNote']))
        table(['Turma','Cap.','Custo','Ticket','PE','% cap.','Margem','Status'],[[r['turma'],r['capacidade'],cash(r['custoTotalCentavos']),cash(r['ticketLiquidoCentavosExato']),r['peCorrigido'],f"{r['percentualCapacidade']:.1f}%",r['margemFisica'],r['status']] for r in rows],[43,27,66,60,25,38,35,217])
        story.append(PageBreak())
    for index,r in enumerate(rows):
        if index:story.append(PageBreak())
        story.extend([p('Colégio Adventista de Juazeiro','Title'),p('Ponto de Equilíbrio 2027 - Relatório Analítico da Turma','Heading1'),p(r['turma']+' | '+r['segment'],'Heading2'),p('CONFIDENCIAL - '+model.get('presentationLabel','candidata local, não publicada.')),p(f"Capacidade: {r['capacidade']} | Matriculados: {r['matriculados']} (informativo) | Mensalidade: {cash(r['tuitionCents'])}"),p('Gerado em: '+model['generatedAt']),p('Auditoria: '+r['status'])])
        story.append(p(r['functionalAllocationNote']))
        if model.get('privacyNote'):story.append(p(model['privacyNote']))
        section('1. Receita por aluno')
        v=r['revenue'];story.append(p(v['basis']+' | Registros considerados: '+str(v['quantity'])))
        table(['Etapa','Valor por aluno'],[['Mensalidade bruta',cash(r['tuitionCents'])],['(-) Comercial/premissa, sem somar novamente aos benefícios',cash(v['premiseCents'])],['(-) Demais benefícios: impacto médio',cash(v['benefitCents'])],['Ticket após descontos',cash(v['afterDiscountCents'])],['(-) Inadimplência 4,5%, uma vez',cash(v['delinquencyCents'])],['TICKET LÍQUIDO UTILIZADO NO PE',cash(r['ticketLiquidoCentavosExato'])]],[365,146])
        table(['Tipo','Percentual','Qtd.','Impacto no grupo','Origem'],[[b['type'],str(Decimal(b['rate'])*100)+'%',b['quantity'],cash(b['impactCents']),b['origin']] for b in r['benefitDetails']] or [['Premissa gerencial','Ver composição',0,cash(v['premiseCents']),'Não é benefício individual ativo']],[90,75,25,75,246])
        story.append(p('Bolsas 100% zeram a receita uma vez. Percentuais e tickets integrais são preservados; valores monetários exibidos são arredondados.'))
        section('2. Custo docente - composição da turma' if model.get('privacyNote') else '2. Custo docente - professor por professor')
        table(['Professor','Disciplina/função','Aulas semanais atribuídas','Hora-aula*','Semanal','Fator','Mensal'],[[t['name'],t['role'],t['lessons'],cash(t['rateCents']),cash(t['weeklyCents']),t['multiplier'],cash(t['monthlyCents'])] for t in r['teacherDetails']] or [['Identificação não disponível','Pendente','—','—','—','4,5','—']],[98,112,57,67,67,30,80])
        story.append(p('* Valor por aula equivalente do detalhamento. Parcelas compartilhadas já estão fracionadas para esta turma; não representam remuneração integral. Fontes são projeções documentais, não salários certificados.'))
        if r['teacherBridgeCents']:story.append(p('PONTE DE CONCILIAÇÃO: '+cash(r['teacherBridgeCents'])+'. '+r['teacherBridgeNote']))
        story.append(p('TOTAL DOCENTES = '+cash(r['docenteCentavos'])))
        section('3. Auxiliares e estagiárias')
        table(['Nome','Função / vínculo','Custo integral','Parcela','Atribuído'],[[t['name'],t['role']+' / '+t['className'],cash(t['monthlyCents']),t['share'],cash(t['allocatedCents'])] for t in r['auxiliaryDetails']] or [['Sem parcela direta registrada','—','—','—',cash(0)]],[135,95,70,131,80])
        story.append(p('TOTAL AUXILIARES/ESTAGIÁRIAS = '+cash(r['auxEstagiariaCentavos'])))
        section('4. Outros custos diretos')
        table(['Descrição','Conta/origem','Valor','Critério'],[[t['description'],t['origin'],cash(t['cents']),t['criterion']] for t in r['otherDirectDetails']] or [['Nenhuma parcela adicional na engine','Composição preservada',cash(r['outrosDiretosCentavos']),'Não inventar despesa']])
        for title,key,total in [('5. Rateio do segmento','segmentDetails','rateioSegmentoCentavos'),('6. Rateio global','globalDetails','rateioGlobalCentavos')]:
            section(title)
            table(['Conta/despesa','Total da conta','Critério','Parcela da turma','Origem'],[[t['account'],cash(t['totalCents']),t['criterion'],cash(t['allocatedCents']),t['origin']] for t in r[key]],[100,65,115,75,156])
            story.append(p('TOTAL = '+cash(r[total])))
        labels={'payrollCents':'Folha','supportCents':'Apoio','generalCents':'Gerais brutos','pcldRemovedCents':'PCLD retirada','discountReclassifiedCents':'Descontos orçamentários retirados','generalNetCents':'Gerais líquidos'}
        table(['Ponte da origem orçamentária','Valor'],[[labels[k],cash(v)] for k,v in r['sourceBridge'].items()],[365,146])
        story.append(p('Sem vínculo por conta e turma, a parcela permanece explicitamente pendente. Esta abertura não distribui novamente contas escolares nem homologa o saldo gerencial.'))
        section('7. Composição do custo total')
        table(['Grupo','Valor','Participação'],[[c['label'],cash(c['cents']),f"{100*c['cents']/r['custoTotalCentavos']:.2f}%"] for c in r['components']]+[['CUSTO ECONÔMICO MENSAL',cash(r['custoTotalCentavos']),'100%']],[280,140,91])
        section('8. Cálculo do PE')
        story.append(p('PE = TETO(CUSTO ECONÔMICO MENSAL ÷ TICKET LÍQUIDO POR ALUNO)'))
        story.append(p(cash(r['custoTotalCentavos'])+' ÷ '+cash(r['ticketLiquidoCentavosExato'])+' = '+f"{Decimal(r['ratio']):.6f}"+' (quociente com ticket integral).'))
        story.append(p('PONTO DE EQUILÍBRIO = '+str(r['peCorrigido'])+' ALUNOS','Heading2'))
        story.append(p(f"Capacidade: {r['capacidade']} | PE/capacidade: {r['percentualCapacidade']:.2f}% | Margem física: {r['margemFisica']}"))
        section('9. POR QUE O PE DESTA TURMA É ESTE?');story.append(p(r['explanation']))
        section('10. Alertas')
        status='PE SUPERIOR À CAPACIDADE' if r['peCorrigido']>r['capacidade'] else 'PE IGUAL À CAPACIDADE' if r['peCorrigido']==r['capacidade'] else 'PE ACIMA DE 90% DA CAPACIDADE' if r['percentualCapacidade']>90 else 'PE DENTRO DA CAPACIDADE'
        story.append(p(status,'Heading2'))
        if r['peCorrigido']>r['capacidade']:story.append(p('Com as premissas atuais, mesmo com 100% das vagas ocupadas, a receita projetada da turma não cobre integralmente o custo econômico atribuído.'))
        table(['Receita máxima projetada','Custo mensal','Saldo na lotação máxima'],[[cash(r['capacityRevenueCents']),cash(r['custoTotalCentavos']),cash(r['capacityBalanceCents'])]])
        section('11. Rastreabilidade')
        story.append(p('Multiplicador docente: 4,5; inadimplência: 4,5%; descontos/benefícios: uma vez; PCLD neutralizada no PE gerencial para evitar dupla contagem; PE independente da matrícula atual.'))
        story.append(p('Fontes: candidata local reconciliada; checkpoint conservador; matriz histórica por série; orçamento 2027 p.4; projeção docente documental; fonte privada de benefícios e composição nominal.'))
        story.append(p('Rateios gerenciais: PENDENTES DOCUMENTALMENTE. Data do artefato de cálculo: '+model['calculationAt']+'. '+model['calculationDateNote']))
        story.append(p('Identificador da candidata: '+model['snapshotSha256'],'Cell'))
    out=BytesIO()
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('Helvetica',7);canvas.drawString(42,23,'7&7 | Confidencial | '+model.get('presentationLabel','Candidata local - não publicada'));canvas.drawRightString(A4[0]-42,23,str(doc.page));canvas.restoreState()
    SimpleDocTemplate(out,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=36,bottomMargin=40,title='PE 2027 - Relatório analítico',author='7&7').build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
