"""PDF institucional estável do PE; sem rede, sem gravação ou matrícula fictícia."""
import io
from datetime import datetime
from html import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle
from reportlab.graphics.shapes import Drawing,Rect,String,Line
from pe_final_2027 import executive,diagnostic
from services import SCHOOL,ADDRESS,CNPJ
from personnel_evidence import personnel_note
BLUE=colors.HexColor('#063b76');GOLD=colors.HexColor('#f6c62f');RED=colors.HexColor('#a43139');PALE=colors.HexColor('#edf3fa')

def br(c):return 'PENDENTE' if c is None else 'R$ '+f'{c/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')
def pct(n):return f'{n:.2f}%'.replace('.',',')

def bars(title,items,labels=('Valor',),width=500,height=480):
    d=Drawing(width,height);d.add(String(0,height-16,title,fontName='Helvetica-Bold',fontSize=12,fillColor=BLUE))
    palette=[BLUE,GOLD,RED]
    maximum=max([abs(v) for _,vs in items for v in vs if v is not None]+[1]);left=74;right=70;space=(height-65)/max(len(items),1)
    for j,label in enumerate(labels):d.add(Rect(j*170,height-38,9,9,fillColor=palette[j%3],strokeColor=None));d.add(String(j*170+14,height-37,label,fontSize=8,fontName='Helvetica'))
    for i,(name,values) in enumerate(items):
        y=height-55-(i+1)*space;d.add(String(0,y+2,name,fontSize=8,fontName='Helvetica',fillColor=BLUE))
        for j,v in enumerate(values):
            yy=y+(len(values)-1-j)*3.7
            if v is None:d.add(String(left,yy,'PENDENTE',fontSize=7,fontName='Helvetica',fillColor=RED));continue
            length=abs(v)/maximum*(width-left-right)
            d.add(Rect(left,yy,length,3.4 if len(values)>1 else min(space*.55,16),fillColor=RED if v<0 else palette[j%3],strokeColor=None))
            if len(values)==1:d.add(String(width-right+5,yy,br(v*100) if '(R$)' in title else str(round(v,2)).replace('.',','),fontSize=7,fontName='Helvetica'))
    return d

def executive_pdf(report):
    rows=report['rows'];e=executive(report);stream=io.BytesIO();w,h=A4
    doc=SimpleDocTemplate(stream,pagesize=A4,leftMargin=42,rightMargin=42,topMargin=104,bottomMargin=48,title='RELATÓRIO EXECUTIVO - PONTO DE EQUILÍBRIO 2027',author=SCHOOL)
    styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='BodyCAJ',fontName='Helvetica',fontSize=9,leading=13,spaceAfter=8,textColor=colors.HexColor('#152238')));styles.add(ParagraphStyle(name='SmallCAJ',parent=styles['BodyCAJ'],fontSize=8,leading=11));styles.add(ParagraphStyle(name='TitleCAJ',fontName='Helvetica-Bold',fontSize=25,leading=31,textColor=BLUE,spaceAfter=22))
    def p(s,style='BodyCAJ'):return Paragraph(escape(str(s)).replace('\n','<br/>'),styles[style])
    def title(s):return Paragraph(escape(s),styles['Heading2'])
    def table(data,widths=None):
        t=Table([[p(v,'SmallCAJ') for v in line] for line in data],colWidths=widths or [511/len(data[0])]*len(data[0]),repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#d5e2f0'))]));return t
    def page(canvas,doc):
        canvas.saveState();canvas.setFillColor(BLUE);canvas.rect(0,h-76,w,76,fill=1,stroke=0);canvas.setFillColor(GOLD);canvas.rect(0,h-80,w,4,fill=1,stroke=0);canvas.setFillColor(colors.white);canvas.setFont('Helvetica-Bold',14);canvas.drawString(32,h-27,SCHOOL);canvas.setFont('Helvetica',9);canvas.drawString(32,h-43,ADDRESS);canvas.drawString(32,h-58,CNPJ);canvas.setStrokeColor(colors.HexColor('#d5e2f0'));canvas.line(32,36,w-32,36);canvas.setFillColor(BLUE);canvas.setFont('Helvetica',8);canvas.drawString(32,23,'7&7 CAJ | PE 2027 | Planejamento auditável');canvas.drawRightString(w-32,23,'Página '+str(doc.page));canvas.restoreState()
    story=[Spacer(1,75),p('RELATÓRIO EXECUTIVO\nPONTO DE EQUILÍBRIO 2027','TitleCAJ'),p(SCHOOL),p('Planejamento financeiro e diagnóstico da fotografia documental'),p(report.get('structureNotice','')),Spacer(1,28),p('Gerado em '+datetime.now().astimezone().strftime('%d/%m/%Y %H:%M %z')),p('Versão institucional PE-2027-v1. Base: orçamento oficial, benefícios previstos e fotografia de matrículas. Valores mensais.'),Spacer(1,25),table([['Comprovação','Situação'],['Cálculos locais','Reproduzíveis; premissas identificadas'],['Fechamento documental','Não encerrado'],['Uso','Revisão gerencial; não representa caixa realizado']]),PageBreak(),title('Dashboard executivo')]
    story+=[p(report.get('structureNotice','')),table([['Indicador','Valor','Escopo'],['Turmas / capacidade',f"41 / {e['capacity']}",'Estrutura atual'],['Matriculados / ocupação',f"{e['enrolled']} / {pct(e['enrolled']/e['capacity']*100)}",'775; novos 37; rematrículas 738'],['PE consolidado conhecido',str(e['peKnown']),f"Soma das {41-e['peMissing']} turmas calculáveis; {e['peMissing']} pendentes. Não é PE completo da escola."],['Receita projetada',br(e['revenue']),'41 turmas; premissas e mix previsto'],['Custo econômico alocado',br(e['cost']),'37 turmas; reserva R$ 15.827,05 separada'],['Resultado comparável',br(e['result']),f"Receita {br(e['comparableRevenue'])} menos custo nas mesmas {e['comparableClasses']} turmas"],['Acima / no / abaixo do PE',f"{e['above']} / {e['at']} / {e['below']}",f"{e['audit']} em auditoria"],['Superlotadas',str(e['overcrowded']),'Vagas negativas preservadas'],['Benefícios previstos','1.016','902 com turma; 114 pendentes; nenhuma matrícula criada']],[160,112,239]),Spacer(1,12),p('Resultados e custos parciais não podem ser subtraídos de receitas de um universo maior. O resultado acima usa somente as mesmas turmas com numerador e denominador calculáveis.'),PageBreak()]
    story+=[bars('Matriculados x PE por turma',[(r['name'],[r['enrolled'],r['pe']]) for r in rows],('Matriculados','PE conhecido')),p('PE ausente permanece pendente. Não é zero. A soma dos PEs por turma não representa compensação financeira entre turmas.'),PageBreak()]
    story+=[bars('Distância até o PE - alunos',[(r['name'],[r['distanceToPE']]) for r in rows],('Matriculados - PE',)),p('Valores negativos indicam falta de matrículas. Valores positivos indicam alunos acima do PE parcial.'),PageBreak()]
    story+=[bars('Ocupação por turma - %',[(r['name'],[r['occupancyPercent']]) for r in rows],('Ocupação',)),p('Ocupação acima de 100% é superlotação. Não limita nem corrige artificialmente o PE.'),PageBreak()]
    blocks={}
    for r in rows:
        for c in r['costs']:blocks[c['kind']]=blocks.get(c['kind'],0)+c['cents']/100
    gross=sum((r.get('planningTuitionCents') or r['tuitionCents'])*r['enrolled'] for r in rows)
    discounted=sum((r.get('planningTuitionCents') or r['tuitionCents']) * .88*r['enrolled'] if r.get('planningAssumption') else (r['postDiscountCents']/r['acceptedStudentCount']*r['enrolled']) for r in rows)
    story+=[bars('Receita x custo - mesmo universo (R$)',[('Receita',[e['comparableRevenue']/100]),('Custo',[e['cost']/100])],height=150),Spacer(1,12),bars('Composição de custos alocados (R$)',[(name.split(' ')[0],[value]) for name,value in blocks.items()],height=170),Spacer(1,12),bars('Impacto de descontos e inadimplência (R$)',[('Bruta',[gross/100]),('Pós-desconto',[discounted/100]),('Líquida',[e['revenue']/100])],height=180),p('Descontos: projeção pelo mix ou premissa; inadimplência 4,5% uma vez. PCLD e estimativas 4126005/4126007 não são somadas ao custo novamente.'),PageBreak()]
    story+=[title('Metodologia e rastreabilidade'),p('PE = TETO(custo econômico / ticket líquido). Ticket = mensalidade após benefício x 0,955. O custo não depende da quantidade matriculada. Receita projetada = matriculados x ticket. Distância = matriculados - PE. Ocupação = matriculados / capacidade. Margem física = capacidade - PE.'),p('G2 A/B: premissa de 12%, mensalidade R$ 930,69; ticket exato R$ 782,151876; PE 14. G5 C: premissa expressa R$ 964,67 e 12%; a mensalidade documental EI R$ 930,69 permanece registrada separadamente. 8º C: mensalidade R$ 1.239,81 e 12%; custo ainda em auditoria.'),p('A premissa desaparece quando existe mix suficiente da própria turma. Para G5 C/8º C, cobertura nominal completa ou base prevista explicitamente homologada; uma linha isolada não comprova o mix da turma. Benefícios previstos independem de matrícula e não são importados novamente.'),p('Fontes: Orçamento COLEGIO ADVENTISTA DE JUAZEIRO 2027 (1).pdf: p.2 mensalidades, p.4 custos por turma, p.8 quadro de alunos, p.12-15 contas; Turmas CAJ 2027 (2).pdf: 41 linhas atuais; planilha de benefícios progredida: 1.016 registros; folha agosto: composição histórica, não novo custo.'),p('Regra documental de progressão: p.8 contém 7º C em 2027 e 8º C em 2026. Não comprova herança 7º C anterior para 8º C atual; R$ 15.827,05 permanecem separados.'),PageBreak()]
    for r in rows:
        story+=[title(r['name']+' - Diagnóstico financeiro'),table([['Indicador','Valor','Indicador','Valor'],['Capacidade',r['capacity'],'Matriculados',r['enrolled']],['Ocupação',pct(r['occupancyPercent']),'Vagas',r['vacancies']],['Mensalidade utilizada',br(r.get('planningTuitionCents',r['tuitionCents'])),'Ticket líquido',br(r['ticketCents'])],['Custo mensal',br(r['consideredCostCents']),'PE',r['pe'] if r['pe'] is not None else 'PENDENTE'],['Matriculados - PE',r['distanceToPE'] if r['distanceToPE'] is not None else 'PENDENTE','Margem física',r['physicalMargin'] if r['physicalMargin'] is not None else 'PENDENTE'],['Receita projetada',br(r['projectedRevenueCents']),'Resultado projetado',br(r['projectedResultCents'])]],[140,115,140,116]),Spacer(1,8),p('STATUS: '+r['status']),title('Por que o resultado é este?'),p(diagnostic(r),'SmallCAJ'),title('Memória resumida e origem'),table([['Bloco econômico','Valor','Fonte']]+[[c['kind'],br(c['cents']),c['evidence']] for c in r['costs']] or [['Custo','Pendente','Sem destino financeiro']],[175,90,246]),p('Docentes, auxiliares, estagiárias, coordenação e encargos são composição dos blocos de folha/apoio. A ponte nominal não é integral: valores por função ausentes não foram inventados nem somados novamente. Outros diretos/rateios: conforme fontes acima.','SmallCAJ'),PageBreak()]
    story+=[title('Pendências e conclusão executiva'),p('1. R$ 15.827,05: retificação do quadro anual/de-para financeiro aprovado. Sem ela não há transferência para 8º C. Folha R$ 5.748,45 + apoio R$ 3.416,95 + gerais líquidos R$ 6.661,65.'),p(personnel_note()),p('3. 114 benefícios: vínculo válido de turma, sem nova progressão. Nenhum aluno fictício; ausência de matrícula não é rejeição.'),p('Conclusão: planejamento parcialmente comprovado. Os tickets novos são calculáveis; a origem histórica do saldo não comprova destino. PRONTO PARA PUBLICAÇÃO: NÃO, até resolução documental dos bloqueadores. Este relatório é um instrumento de revisão, não certificação de custo definitivo.')]
    doc.build(story,onFirstPage=page,onLaterPages=page);return stream.getvalue()
