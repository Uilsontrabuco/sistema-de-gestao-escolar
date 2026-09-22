"""Projeção estrutural 2027 dos postos diretos de estágio do CAJ.

Fonte: Relação Estagiárias OF.xlsx. Os nomes identificam somente a evidência da
configuração vigente em 2026; não representam compromisso de permanência em
2027. Datas de término registradas na fonte não eliminam o posto estrutural.
"""
import re
import unicodedata


SOURCE_NAME = 'Relação Estagiárias OF.xlsx'
PROJECTION_LABEL = 'Projeção 2027 — estrutura de estagiárias baseada na relação vigente 2026'

# Nome original e grafia da turma preservados conforme a fonte oficial.
OFFICIAL_ROSTER_2026 = (
    (1, 'Emilly Gomes Limoeiro', 'MANHÃ', '2°A'),
    (2, 'Gleiciane Maele Silva Duarte Café', 'MANHÃ', '3°A'),
    (3, 'Janaina Raissa dos Santos Souza', 'MANHÃ', 'G5A'),
    (4, 'Joyce dos Santos Pereira', 'MANHÃ', 'G2A'),
    (5, 'Késia Suane Azevedo', 'MANHÃ', 'G3A'),
    (6, 'Larissa Lorrana Miranda de Jesus', 'MANHÃ', 'G2B'),
    (7, 'Maria Gabrielle Pinho da Silva', 'MANHÃ', 'G4A'),
    (8, 'Nathalia Rabelo dos Santos', 'MANHÃ', 'G4A'),
    (9, 'Oslane\u00a0Brito Cordeiro', 'MANHÃ', '4ºA'),
    (10, 'Rebeca de Oliveira azevedo', 'MANHÃ', '3°B'),
    (11, 'Iane Caroline Dantas da Silva', 'TARDE', '7°B'),
    (12, 'Liliane de Santana Martins Paixão', 'TARDE', '1°C'),
    (13, 'Marcia Gabrielle dos Santos Lopes', 'TARDE', '9°C'),
    (15, 'Maria Azenilda de Farias', 'TARDE', '5°C'),
    (16, 'Rebeca Dias de Jesus', 'TARDE', 'G4B'),
    (14, 'Sheila Emanuela Alves Evangelista', 'TARDE', '3°D'),
    (17, 'Sthefany Fernanda Barbosa de Almeida', 'TARDE', '2°C'),
    (18, 'Tamires de Jesus Cruz da Silva', 'TARDE', 'G4B'),
    (19, 'Yasmin Waleska de Jesus Carvalho', 'TARDE', 'G3B'),
)


def normalized_person_name(value):
    """Normalização conservadora usada exclusivamente para detectar repetição."""
    text=' '.join(str(value or '').replace('\u00a0',' ').split()).casefold()
    return ''.join(ch for ch in unicodedata.normalize('NFKD',text) if not unicodedata.combining(ch))


def canonical_class_name(value):
    text=str(value or '').replace('º','').replace('°','')
    text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().upper()
    text=re.sub(r'[^A-Z0-9]+','',text)
    match=re.fullmatch(r'G([2-5])([A-D])',text)
    if match:return f'G{match.group(1)} {match.group(2)}'
    match=re.fullmatch(r'([1-9])([A-D])',text)
    if match:return f'{match.group(1)}º {match.group(2)}'
    return str(value or '').strip()


def projection_from_rows(rows, classes):
    """Agrupa uma pessoa entre turnos sem alterar sua grafia original."""
    class_by_name={canonical_class_name(room['name']):room for room in classes}
    grouped={}
    order=[]
    for row in rows:
        person=str(row['person']).strip()
        key=normalized_person_name(person)
        if not key:raise ValueError('Pessoa direta ausente')
        if key not in grouped:
            grouped[key]=dict(person=person,shifts=[],classIds=[],sourceRows=[],sourceClasses=[])
            order.append(key)
        item=grouped[key]
        shift=str(row['shift']).strip().casefold()
        canonical=canonical_class_name(row['className'])
        room=class_by_name.get(canonical)
        if room is None:raise ValueError(f'Turma de estágio não localizada: {row["className"]}')
        if shift not in item['shifts']:item['shifts'].append(shift)
        if room['id'] not in item['classIds']:item['classIds'].append(room['id'])
        item['sourceRows'].append(row.get('sourceRow'))
        item['sourceClasses'].append(row['className'])
    return [dict(grouped[key],source=SOURCE_NAME,nature='custo direto',projectionLabel=PROJECTION_LABEL,
                 personnelIdentityUse='EVIDENCIA_CONFIGURACAO_BASE_2026_NAO_PERMANENCIA_2027') for key in order]


def official_projection(classes):
    rows=[dict(sourceRow=number,person=person,shift=shift,className=class_name)
          for number,person,shift,class_name in OFFICIAL_ROSTER_2026]
    return projection_from_rows(rows,classes)
