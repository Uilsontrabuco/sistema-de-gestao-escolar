"""Pesquisa local dirigida às três pendências; não altera dados operacionais."""
import json, re, hashlib, unicodedata, sys
from pathlib import Path
from openpyxl import load_workbook
from pypdf import PdfReader
from zipfile import ZipFile
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/auditoria-tres-pendencias-20270922'
OUT.mkdir(exist_ok=True)
def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD',str(s)).upper() if not unicodedata.combining(c))

def main():
    sources=[]
    for p in Path('D:/').iterdir():
        name=norm(p.name)
        selected=any(t in name for t in ['RELATORIO DE ALUNOS POR TURMA','RELACAO DE ALUNOS COMPLETA','CONTROLE MATRICULAS','FUNCION','ADMISSAO','ADMISSOES','CONTRATACO','RESCISAO DO CONTRATO DE TRABALHO','TERMO ADITIVO AO CONTRATO','FOLHA - ABRIL','TURMAS CAJ 2027'])
        if not p.is_file() or not selected or p.suffix.lower() not in ('.xlsx','.pdf','.docx'):continue
        item=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),personnel=[],classMatches=[],headers=[])
        def inspect(text,location,context=None):
            n=norm(text)
            if any(t in n for t in ['JAILANE','VERONEIDE','PAULA ARAUJO','PAULA ARAÚJO','ROMILTON']):item['personnel'].append(dict(location=location,text=text,context=context))
            if re.search(r'EFUND08[MT]C|8\s*[º°O]?\s*(?:ANO\s*)?[- /]?C\b',n):item['classMatches'].append(dict(location=location,text=text,context=context))
        try:
            if p.suffix.lower()=='.xlsx':
                wb=load_workbook(p,read_only=True,data_only=True)
                for sheet in wb:
                    rows=list(sheet.values)
                    item['headers'].append(dict(sheet=sheet.title,rows=len(rows),firstRows=rows[:8]))
                    for i,row in enumerate(rows):inspect(str(row),f'{sheet.title}!{i+1}',rows[max(0,i-1):i+2])
                wb.close()
            elif p.suffix.lower()=='.pdf':
                for i,page in enumerate(PdfReader(p).pages):
                    text=page.extract_text() or ''
                    item['headers'].append(dict(page=i+1,firstLines=text.splitlines()[:6]))
                    for j,line in enumerate(text.splitlines()):inspect(line,f'p.{i+1} linha {j+1}',text.splitlines()[max(0,j-2):j+4])
            else:
                with ZipFile(p) as z:doc=ElementTree.fromstring(z.read('word/document.xml'))
                text=' '.join(doc.itertext());inspect(text,'document.xml')
        except Exception as e:item['error']=str(e)
        sources.append(item)
    (OUT/'pesquisa-dirigida.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps(dict(sources=len(sources),personnelMatches=sum(len(x['personnel']) for x in sources),classMatches=sum(len(x['classMatches']) for x in sources),errors=[x['path'] for x in sources if 'error' in x])))
if __name__=='__main__':main()
