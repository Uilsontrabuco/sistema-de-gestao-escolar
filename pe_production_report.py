"""Authenticated reports over validated, non-nominal class results.

No source imports, payroll records, database reads or recalculation of the PE.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

RESULTS = Path(__file__).with_name('pe_financial_results_2027.json')
RESULTS_SHA256 = '504357f79ad4397d2fa9b34146e1273e910ea7b138075ffb8163e45f38872698'


def load_production_report():
    raw = RESULTS.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RESULTS_SHA256:
        raise ValueError('Resultados financeiros divergem da versão validada.')
    report = json.loads(raw)
    rows = report['rows']
    if (report['schemaVersion'] != 1 or len(rows) != 41
            or len({r['id'] for r in rows}) != 41
            or sum(r['capacidade'] for r in rows) != 1103
            or sum(r['matriculados'] for r in rows) != 775
            or sum(r['custoTotalCentavos'] for r in rows) != 60564103
            or report['summary']['diferencaCentavos'] != 0):
        raise ValueError('Resultados financeiros indisponíveis ou inconsistentes.')
    for row in rows:
        if sum(c['cents'] for c in row['components']) != row['custoTotalCentavos']:
            raise ValueError('Composição financeira inconsistente.')
    report.update(generatedAt=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                  snapshotSha256=hashlib.sha256(raw).hexdigest(), readOnly=True,
                  presentationLabel='Resultados financeiros validados — acesso restrito')
    return report
