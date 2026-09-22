"""Comparação de arquivos locais, sem calcular PE ou acessar rede/banco."""
import argparse
import copy
import json
from pathlib import Path

def validate(expected, candidate):
    errors=[]
    erows=expected.get('rows',[]);rows=candidate.get('rows',[])
    if len(rows)!=41:errors.append('quantidade de turmas diferente de 41')
    ids=[r.get('id') for r in rows]
    if len(set(ids))!=len(ids):errors.append('ID duplicado')
    if set(ids)!={r['id'] for r in erows}:errors.append('conjunto de IDs divergente')
    names=[r.get('turma') for r in rows]
    if len(set(names))!=len(names):errors.append('turma duplicada')
    if any(type(r.get('peAlunos')) is not int or r['peAlunos']<0 for r in rows):errors.append('PE ausente/inválido')
    if sum(r.get('custoTotalCentavos',0) for r in rows)!=60564103:errors.append('custo total divergente')
    for field,total in [('capacidade',1103),('matriculados',775),('vagas',328)]:
        if sum(r.get(field,0) for r in rows)!=total:errors.append(f'total {field} divergente')
    if candidate.get('reserveCents')!=1582705:errors.append('reserva divergente')
    if candidate.get('checkpointId')!=expected.get('checkpointId'):errors.append('checkpoint divergente')
    if candidate.get('reserveIncludedInClassCost') is not False:errors.append('reserva incorporada/sem segregação')
    byid={r.get('id'):r for r in rows}
    for e in erows:
        r=byid.get(e['id'])
        if r is None:continue
        for key,value in e.items():
            if r.get(key)!=value:errors.append(f'{e["id"]}: {key} diverge do snapshot aprovado')
        parts=['docenteCentavos','diretosExclusivosCentavos','rateioSerieNovoCentavos','rateioSegmentoCentavos',
               'coberturaAnteriorMantidaCentavos','folhaGlobalCentavos','apoioGlobalCentavos','geraisGlobalCentavos']
        if sum(r.get(k,0) for k in parts)!=r.get('custoTotalCentavos'):
            errors.append(f'{e["id"]}: componentes somados com lacuna/duplicidade')
    if errors:raise ValueError('; '.join(errors))
    return dict(valid=True,classes=41,totalCents=60564103,reserveCents=1582705)

def self_test(expected):
    validate(expected,expected)
    mutations=[lambda c:c['rows'].pop(),lambda c:c['rows'].append(copy.deepcopy(c['rows'][0])),
        lambda c:c['rows'][0].update(peAlunos=None),lambda c:c['rows'][0].update(peAlunos=1),
        lambda c:c['rows'][0].update(custoTotalCentavos=c['rows'][0]['custoTotalCentavos']+1582705),
        lambda c:c.update(reserveIncludedInClassCost=True),lambda c:c.update(reserveCents=0),
        lambda c:c['rows'][0].update(capacidade=0),lambda c:c['rows'][0].update(matriculados=0),
        lambda c:c['rows'][0].update(docenteCentavos=c['rows'][0]['docenteCentavos']*2),
        lambda c:c['rows'][0].update(id=c['rows'][1]['id']),
        lambda c:c['rows'][0].update(ticketLiquidoCentavosExato='0')]
    for mutation in mutations:
        candidate=copy.deepcopy(expected);mutation(candidate)
        try:validate(expected,candidate)
        except ValueError:pass
        else:raise AssertionError('Validação aceitou corrupção proposital')
    return dict(originalAccepted=True,corruptionsRejected=len(mutations))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('expected',type=Path)
    parser.add_argument('candidate',type=Path,nargs='?')
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    expected=json.loads(args.expected.read_text(encoding='utf-8'))
    try:
        result=self_test(expected) if args.self_test else validate(expected,json.loads(args.candidate.read_text(encoding='utf-8')) if args.candidate else expected)
    except (ValueError,KeyError,TypeError) as exc:
        parser.exit(1,'ABORTAR: '+str(exc)+'\n')
    print(json.dumps(result))
