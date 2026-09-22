"""Empacota evidências homologadas; não recalcula ou edita auditorias anteriores."""
import json
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'output/auditoria-documental-41-turmas-2027/auditoria.json'


def main():
    data=json.loads(AUDIT.read_text(encoding='utf-8'))
    result=dict(schemaVersion=1,year=2027,source='Orçamento COLEGIO ADVENTISTA DE JUAZEIRO 2027 (1).pdf',
        auditSha256=hashlib.sha256(AUDIT.read_bytes()).hexdigest(),sourceHashes=data['sourceHashes'],
        costBasis='Grade homologada com tarifas 2027; pessoal nominal agosto/2026 e decisões C02/C28/C29. Cobertura incompleta.',
        verifiedComponents=['docentes','estagiarias','auxiliar-direta','auxiliares-segmento','coordenacao-segmento'],
        evidence={'docentes':'Grade homologada × 4,5, tarifas oficiais; sem encargos adicionais presumidos',
          'estagiarias':'Folha agosto/2026 e lotação C02; bolsa, seguro e consultoria',
          'auxiliar-direta':'Folha agosto/2026 e lotação exclusiva de Maria Edna em G4 B',
          'auxiliares-segmento':'Folha nominal agosto/2026; C29; rateio homologado por capacidade do segmento, pesos congelados',
          'coordenacao-segmento':'Folha nominal agosto/2026; C28; divisão igual por turma do segmento, pesos congelados'},
        tuitionSource='PDF 2027, página 2, linha Reajustado',
        institutionalRevenue={'monthlyCents':2692103,'accounts':['3182019','3195130'],'availableForManagement':False},
        discountCoverage={'status':'COBERTURA DE DESCONTOS PENDENTE DE RECONCILIAÇÃO','monthlyCents':17790108,'accounts':['4126005','4126007'],'reconciled':False},
        pcld={'officialCents':4211780,'managementIncludedCents':0,'delinquencyPercent':4.5},
        unmatchedSourceRows=data['excludedSourceRows'],rows=[])
    for r in data['rows']:
        c=r['current']
        result['rows'].append(dict(id=c['classId'],name=r['name'],capacity=r['currentCapacity'],
            tuitionCents=round(c['grossTuition']*100),document=r['document'],
            components=[dict(id=c['classId']+'/'+k,kind=k,cents=round(float(v)*100),
                evidence=result['evidence'].get(k),verified=k in result['verifiedComponents']) for k,v in r['currentComponents'].items()],
            historicalPCLDNeutralizedCents=round(c['pcldNeutralizedMonthly']*100),
            unknownCosts=([dict(person='Paula',role='Estagiária adicional G3 B',cents=None,reason='Custo e inclusão orçamentária não comprovados')] if r['name']=='G3 B' else [])))
    (ROOT/'pe_layers_2027_source.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
