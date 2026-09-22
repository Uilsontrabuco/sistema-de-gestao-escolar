"""PE com distribuição individual local. Não acessa banco ou serviços remotos."""
from private_artifacts import private_path
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import hashlib
import json
import re
import unicodedata
from pe_layers import build_layers, ceil_ratio, validate_recognition

ROOT = Path(__file__).resolve().parent
AUDIT = ROOT / 'output/pe-real-2027'


def normalized(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(value or '')) if not unicodedata.combining(c)).upper().split())


def money(value):
    return int(Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def class_key(code):
    """Somente decodifica a turma escrita; nunca progride série ou une letras."""
    m = re.fullmatch(r'(EINFA|EFUND|EMERE)(\d{2})([MT])([A-D])', str(code or '').strip())
    if not m:
        return None
    kind, grade, shift, letter = m.groups()
    grade = int(grade)
    if kind == 'EMERE':
        return f'caj-2027-caj-{grade}-em' if letter == 'A' else None
    return f'caj-2027-caj-{"g" if kind == "EINFA" else ""}{grade}-{letter.lower()}'


def benefit_rate(label, scholarship, conditional):
    """Colunas repetidas não são cumulativas; divergência é bloqueada."""
    if conditional is None or isinstance(conditional, bool):
        return None, 'PERCENTUAL AUSENTE'
    try:
        rate = Decimal(str(conditional))
        if not rate.is_finite() or not 0 <= rate <= 1:
            return None, 'PERCENTUAL INVÁLIDO'
        if normalized(label) == '_SEM BOLSA' and scholarship is None:
            return rate, None
        if not label or scholarship is None or '|' in str(scholarship) or '|' in str(label):
            return None, 'BENEFÍCIO NÃO CLASSIFICADO OU ACUMULAÇÃO SEM REGRA'
        grant = Decimal(str(scholarship).replace('%', '').replace(',', '.')) / 100
        if grant != rate or not 0 <= grant <= 1:
            return None, 'BOLSA E CONDICIONAL DIVERGENTES'
        return rate, None
    except Exception:
        return None, 'PERCENTUAL INVÁLIDO'


def import_rows(rows, source):
    layers = build_layers()
    classes = {r['id']: r for r in layers['rows']}
    nonempty = [(i, list(r)) for i, r in enumerate(rows, 3) if any(v is not None for v in r)]
    counts = Counter(normalized(r[3]) for _, r in nonempty if r[3])
    records = []
    for line, raw in nonempty:
        unit, series, code, name, label, grant, conditional = raw[:7]
        cid = class_key(code)
        rate, issue = benefit_rate(label, grant, conditional)
        issues = [issue] if issue else []
        if not name: issues.append('ALUNO AUSENTE')
        if name and counts[normalized(name)] > 1: issues.append('ALUNO DUPLICADO/HOMÔNIMO SEM MATRÍCULA')
        if normalized(unit) != 'CAJ': issues.append('UNIDADE NÃO HOMOLOGADA')
        grade_match = re.search(r'\d+', str(series or ''))
        code_match = re.fullmatch(r'(EINFA|EFUND|EMERE)(\d{2})[MT][A-D]', str(code or ''))
        if not grade_match or not code_match or int(grade_match[0]) != int(code_match[2]):
            issues.append('SÉRIE E TURMA DIVERGENTES')
        if not code: issues.append('ALUNO SEM TURMA')
        if cid not in classes: issues.append('SEM CORRESPONDÊNCIA DE TURMA')
        gross = classes[cid]['tuitionCents'] if cid in classes else None
        if gross is None and code_match:
            kind, grade = code_match[1], int(code_match[2])
            gross = (93069 if kind=='EINFA' and 2<=grade<=5 else
                (96467 if grade<=5 else 123981) if kind=='EFUND' and 1<=grade<=9 else
                (146105 if grade==3 else 142559) if kind=='EMERE' and 1<=grade<=3 else None)
        # Desconto não classificado permanece desconhecido; não vira 0%.
        discount = money(Decimal(gross) * rate) if gross is not None and rate is not None else None
        post = gross - discount if discount is not None else None
        records.append(dict(sourceRow=line, source=source, sheet='Todos os Descontos',
            student=name, studentKey=normalized(name), unit=unit, series=series,
            sourceClass=code, classId=cid if cid in classes else None,
            benefit=label, scholarshipRaw=grant, conditionalRaw=conditional,
            rate=str(rate) if rate is not None else None, grossCents=gross,
            discountCents=discount, postDiscountCents=post, issues=issues,
            valid=not issues, economicEventId=f'{source}:Todos os Descontos:{line}',
            benefitValid=not [i for i in issues if i!='SEM CORRESPONDÊNCIA DE TURMA'],
            commercialPercent=None, otherBenefits=None,
            recognition='UMA REDUÇÃO DE RECEITA; F/G iguais não somados'))
    return records


def calculate(records, layers=None, *, allow_partial_mix=False):
    layers = layers or build_layers()
    valid = [s for s in records if s['valid']]
    validate_recognition([dict(economicEventId=s['economicEventId'], side='student', kind='discount') for s in valid])
    if len({s['studentKey'] for s in valid}) != len(valid):
        raise ValueError('Aluno duplicado')
    groups = defaultdict(list)
    for s in records:
        if s['classId']: groups[s['classId']].append(s)
    result = []
    for r in layers['rows']:
        group = groups[r['id']]
        accepted = [s for s in group if s['valid']]
        n = len(accepted)
        gross = sum(s['grossCents'] for s in accepted) if n else None
        discount = sum(s['discountCents'] for s in accepted) if n else None
        post = gross - discount if n else None
        net = money(Decimal(post) * Decimal('.955')) if n else None
        ticket = Decimal(net) / n if n else None
        cost = r['managerial']['costCents']
        pending = r['pendingCosts']['knownCents']
        mix_complete = bool(n) and n == len(group)
        # Sem alunos ou com benefício conflituoso, não extrapola a amostra restante.
        eligible = mix_complete or (allow_partial_mix and bool(n))
        pe = ceil_ratio(cost * n, net) if eligible else None
        reference = Decimal(r['tuitionCents']) * Decimal('.955')
        ape = float(Decimal(cost) / reference) if cost is not None else None
        components = r['managerial']['costs']
        by_kind = {c['kind']: c['cents'] for c in components}
        benefits = defaultdict(lambda: dict(count=0, discountCents=0, sourceRows=[]))
        for s in accepted:
            b = benefits[str(s['benefit'])+' / '+str(Decimal(s['rate'])*100)+'%']
            b['count'] += 1; b['discountCents'] += s['discountCents']; b['sourceRows'].append(s['sourceRow'])
        total_gross = sum(s['grossCents'] or 0 for s in group)
        coverage_revenue = gross / total_gross * 100 if total_gross and gross is not None else None
        coverage_cost = cost / (cost+pending) * 100 if cost is not None and cost+pending else None
        closed = r['managerial']['completeCostCoverage'] and mix_complete
        status = 'PE REAL COMPROVADO' if closed else ('PE REAL PARCIALMENTE COMPROVADO' if pe is not None else 'PE AINDA EM AUDITORIA')
        result.append(dict(id=r['id'], name=r['name'], capacity=r['capacity'], tuitionCents=r['tuitionCents'],
            sourceStudentCount=len(group), acceptedStudentCount=n, issues=[dict(row=s['sourceRow'],issues=s['issues']) for s in group if not s['valid']],
            grossCents=gross, discountCents=discount, postDiscountCents=post,
            delinquencyCents=post-net if n else None, netRevenueCents=net,
            ticketCents=float(ticket) if ticket is not None else None,
            teacherCents=by_kind.get('docentes'),
            assistantsInternsCents=sum(by_kind.get(k,0) for k in ('estagiarias','auxiliar-direta','auxiliares-segmento')),
            coordinationCents=by_kind.get('coordenacao-segmento'),
            otherDirectCents=None, chargesAdditionalCents=None, operationalCents=None,
            verifiedCostCents=cost, pendingCostCents=pending, unknownCosts=r['pendingCosts']['unknownItems'],
            consideredCostCents=cost, knownCostEnvelopeCents=cost+pending,
            costCoveragePercent=coverage_cost, revenueCoveragePercent=coverage_revenue,
            peConfidencePercent=None, confidenceReason='Coberturas financeiras não são probabilidade; total de custo e representatividade do mix ainda não fechados.',
            ape=ape, pe=pe, percentCapacity=pe/r['capacity']*100 if pe is not None else None,
            physicalMargin=r['capacity']-pe if pe is not None else None,
            physicallyInfeasible=bool(closed and pe is not None and pe>r['capacity']),
            status=status, completeCostCoverage=closed, completeMix=mix_complete,
            partialMixAuthorized=bool(allow_partial_mix and n and not mix_complete),
            averageFinancialDiscountCents=discount/n if n else None,
            costs=components, pendingCosts=r['pendingCosts']['items'], benefits=dict(benefits),
            historicalDocumentaryPE=r['documentary']['printedPE'], historicalProvisionalPE=r['provisional']['pe'],
            note='Estimativa parcial: custos comprovados disponíveis; mix da planilha, sem confirmação de base integral de matrícula. Não é PE definitivo.'))
    summary=dict(classes=len(result),capacity=sum(r['capacity'] for r in result),records=len(records),
        validRecords=len(valid),rejectedRecords=len(records)-len(valid),unmappedRecords=sum(s['classId'] is None for s in records),
        consideredCostCents=sum(r['consideredCostCents'] for r in result),
        verifiedCostCents=sum(r['verifiedCostCents'] for r in result),pendingCostCents=sum(r['pendingCostCents'] for r in result),
        discountCents=sum(r['discountCents'] or 0 for r in result),netRevenueCents=sum(r['netRevenueCents'] or 0 for r in result),
        delinquencyCents=sum(r['delinquencyCents'] or 0 for r in result),
        confirmed=sum(r['status']=='PE REAL COMPROVADO' for r in result),
        partial=sum(r['status']=='PE REAL PARCIALMENTE COMPROVADO' for r in result),
        audit=sum(r['status']=='PE AINDA EM AUDITORIA' for r in result),
        infeasible=sum(r['physicallyInfeasible'] for r in result),
        pcldExpenseCents=0,structuralDiscountPercent=0,delinquencyPercent=4.5,
        accountingMatchedCents=None)
    return dict(contractVersion='pe-real-2027-v1',rows=result,summary=summary,definitivelyClosed=False)


def load_report():
    """Somente agregados; arquivo nominal da auditoria não é servido."""
    source=AUDIT/'resultado.json'
    if not source.exists():source=private_path('pe_real_2027_snapshot.json')
    result=json.loads(source.read_text(encoding='utf-8'))
    if source.name=='pe_real_2027_snapshot.json':result['packagedRuntime']=True
    return result
