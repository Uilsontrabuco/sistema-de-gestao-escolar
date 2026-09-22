from private_artifacts import load_private_json, private_text
"""Projeção estrutural 2027 dos postos diretos de estágio do CAJ.

Fonte: Relação Estagiárias OF.xlsx. Os nomes identificam somente a evidência da
configuração vigente em 2026; não representam compromisso de permanência em
2027. Datas de término registradas na fonte não eliminam o posto estrutural.
"""
import re
import unicodedata
SOURCE_NAME = 'Relação Estagiárias OF.xlsx'
PROJECTION_LABEL = 'Projeção 2027 — estrutura de estagiárias baseada na relação vigente 2026'

def normalized_person_name(value):
    """Normalização conservadora usada exclusivamente para detectar repetição."""
    text = ' '.join(str(value or '').replace('\xa0', ' ').split()).casefold()
    return ''.join((ch for ch in unicodedata.normalize('NFKD', text) if not unicodedata.combining(ch)))

def canonical_class_name(value):
    text = str(value or '').replace('º', '').replace('°', '')
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().upper()
    text = re.sub('[^A-Z0-9]+', '', text)
    match = re.fullmatch('G([2-5])([A-D])', text)
    if match:
        return f'G{match.group(1)} {match.group(2)}'
    match = re.fullmatch('([1-9])([A-D])', text)
    if match:
        return f'{match.group(1)}º {match.group(2)}'
    return str(value or '').strip()

def projection_from_rows(rows, classes):
    """Agrupa uma pessoa entre turnos sem alterar sua grafia original."""
    class_by_name = {canonical_class_name(room['name']): room for room in classes}
    grouped = {}
    order = []
    for row in rows:
        person = str(row['person']).strip()
        key = normalized_person_name(person)
        if not key:
            raise ValueError('Pessoa direta ausente')
        if key not in grouped:
            grouped[key] = dict(person=person, shifts=[], classIds=[], sourceRows=[], sourceClasses=[])
            order.append(key)
        item = grouped[key]
        shift = str(row['shift']).strip().casefold()
        canonical = canonical_class_name(row['className'])
        room = class_by_name.get(canonical)
        if room is None:
            raise ValueError(f"Turma de estágio não localizada: {row['className']}")
        if shift not in item['shifts']:
            item['shifts'].append(shift)
        if room['id'] not in item['classIds']:
            item['classIds'].append(room['id'])
        item['sourceRows'].append(row.get('sourceRow'))
        item['sourceClasses'].append(row['className'])
    return [dict(grouped[key], source=SOURCE_NAME, nature='custo direto', projectionLabel=PROJECTION_LABEL, personnelIdentityUse='EVIDENCIA_CONFIGURACAO_BASE_2026_NAO_PERMANENCIA_2027') for key in order]

def official_projection(classes):
    _private_values = load_private_json('personnel_projection.json')
    OFFICIAL_ROSTER_2026 = _private_values['OFFICIAL_ROSTER_2026']
    rows = [dict(sourceRow=number, person=person, shift=shift, className=class_name) for number, person, shift, class_name in OFFICIAL_ROSTER_2026]
    return projection_from_rows(rows, classes)
