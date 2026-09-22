"""Reavalia as premissas aprovadas sem aplicar alteração a motor ou banco."""
import copy
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
from fractions import Fraction
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from administrative_pe_2027 import exact_ticket

OUT = ROOT / 'output/fechamento-regras-administrativas-2027'
APPROVAL = Path('C:/Users/Uilson Trabuco/.codex/attachments/06507109-8150-4ed0-a4e8-77a562df90f2/Texto colado.txt')

def read(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))

def br(c):
    return 'N/D' if c is None else f'{Decimal(str(c))/100:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=True)
    protected_paths = [ROOT/'data/caj.sqlite3',
        ROOT/'output/pre-publicacao-2027/backup-premissas-8C-mantido-20270922.zip',
        ROOT/'output/forense-saldos-2027/composicao-e-simulacao-conservadora.json',
        ROOT/'output/mapa-pendencias-financeiras-2027/mapa-pendencias.json',
        ROOT/'output/simulacao-rateio-series-2027/simulacao.json']
    hashes = {str(p): digest(p) for p in protected_paths}
    checkpoint = read('output/forense-saldos-2027/composicao-e-simulacao-conservadora.json')
    teaching = read('output/desbloqueio-pe-2027/docencia-reconstruida.json')
    ledger = read('output/pe-real-2027/reconciliacao-custos.json')
    source_rows = checkpoint['conservativeRows']
    preserved_rows = copy.deepcopy(source_rows)
    # Natureza administrativa agora comprovada; não cria valor conta x turma.
    global_codes = set(('4119010 4121001 4121008 4121017 4121021 4121028 4121040 '
        '4121042 4121048 4121051 4121074 4121076 4121085 4121089 4121550 4121555 '
        '4121585 4122005 4122020 4122030 4122035 4122025 4123005 4123015 4123020 '
        '4123010 4124010 4125001 4125010 4129101 4129102 4129103 4129121 '
        '4141062 4191005 4193250').split())
    classifications = []
    for a in checkpoint['accountCatalogue']:
        if a['excludedFromEconomicCost']:
            continue
        global_service = a['code'] in global_codes
        classifications.append(dict(code=a['code'], description=a['description'],
            classification='D' if global_service else 'E', schoolReferenceCents=a['monthlyCents'],
            centsInsidePending=None, beneficiary='Escola, salvo vínculo exclusivo explícito' if global_service else 'Conta agregada com beneficiários não individualizados',
            reason='Serviço administrativo/estrutural abrangido pela regra 4 aprovada; conservar eventuais exceções exclusivas' if global_service else
                   'A conta agrega postos/atividades de naturezas distintas; a regra não transforma todos os beneficiários em globais',
            documentarySource=f"Orçamento oficial p.{a['sourcePage']}", monetaryBridgeProven=False,
            action='Nenhum valor transferido: falta conciliar a parcela desta conta no saldo p.4'))
    # Prova sobre o registro completo da grade, sem executar novo rateio.
    allocations = teaching['operational_allocations']
    sums = defaultdict(Fraction)
    ids = []
    for a in allocations:
        ids.append(a['allocation_id'])
        if a.get('duplicate_of'):
            continue
        occurrence = a['source_reference']['occurrence_id']
        sums[occurrence] += Fraction(a['financial_fraction_numerator'], a['financial_fraction_denominator'])
    assert len(ids) == len(set(ids))
    assert all(value <= 1 for value in sums.values())
    comparisons, mismatches = [], []
    for r in source_rows:
        ticket = exact_ticket(r)
        cost = r['consideredCostCents']
        checked_pe = int((Decimal(cost)/ticket).to_integral_value(rounding=ROUND_CEILING)) if cost is not None and ticket and ticket > 0 else None
        if checked_pe != r['pe']:
            mismatches.append(dict(name=r['name'], before=r['pe'], checked=checked_pe))
        direct = sum(c['cents'] for c in r['nominalCosts'] if c['kind'] in ('estagiarias','auxiliar-direta'))
        segment = sum(c['cents'] for c in r['nominalCosts'] if c['kind'] in ('auxiliares-segmento','coordenacao-segmento'))
        teacher = r['teacherCents'] - (27414 if r['name']=='8º C' else 0)
        # Não classificar o saldo financeiro por mera diferença como global.
        residue = cost - teacher - direct - segment if cost is not None else None
        comparisons.append(dict(name=r['name'], capacity=r['capacity'], enrolled=r['enrolled'],
            ticketCents=str(ticket) if ticket is not None else None, teacherNominalCents=teacher,
            directNominalCents=direct, segmentQuotaCents=segment, seriesFinancialCents=None,
            globalFinancialCents=None, inheritedResidualCents=residue, costBeforeCents=cost,
            costAfterCents=cost, peBefore=r['pe'], checkedPE=checked_pe, definitivePE=None,
            peDifference=0 if r['pe'] is not None else None,
            peCapacityPercent=checked_pe/r['capacity']*100 if checked_pe is not None else None,
            situation='PE integral pendente' if checked_pe is None else 'Abaixo do PE' if r['enrolled']<checked_pe else 'No PE' if r['enrolled']==checked_pe else 'Acima do PE',
            materialChange=False))
    assert preserved_rows == source_rows
    assert len(comparisons)==41 and sum(r['enrolled'] for r in source_rows)==775
    assert sum(r['capacity'] for r in source_rows)==1103
    assert sum(r['capacity']-r['enrolled'] for r in source_rows)==328
    assert sum(r['consideredCostCents'] or 0 for r in source_rows)==60564103
    assert next(r for r in source_rows if r['name']=='8º C')['enrolled']==20
    assert next(r for r in source_rows if r['name']=='2º C')['pe']==33
    assert next(r for r in source_rows if r['name']=='3º C')['pe']==55
    assert checkpoint['partition']['reserveCents']==1582705
    maria = next(c for r in source_rows if r['name']=='G4 B' for c in r['nominalCosts'] if c['kind']=='auxiliar-direta')
    # Restauração em memória da imagem do banco do backup; nenhuma escrita SQL/disco.
    with ZipFile(protected_paths[1]) as archive:
        assert archive.testzip() is None
        backup_db = archive.read('data/caj.sqlite3')
        archive_entries = len(archive.infolist())
    restored = sqlite3.connect(':memory:')
    restored.deserialize(backup_db)
    restored.execute('PRAGMA query_only=ON')
    integrity = restored.execute('PRAGMA integrity_check').fetchone()[0]
    current = sqlite3.connect(protected_paths[0].as_uri()+'?mode=ro', uri=True)
    current.execute('PRAGMA query_only=ON')
    same_dump = list(restored.iterdump()) == list(current.iterdump())
    restored.close()
    current.close()
    assert integrity=='ok' and same_dump
    result = dict(status='NO-GO', approvalText=APPROVAL.read_text(encoding='utf-8'),
        approvalSha256=digest(APPROVAL), classifications=classifications, rows=comparisons,
        schoolBeforeCents=60564103, schoolAfterCents=60564103, reserveCents=1582705,
        differenceCents=0, pendingAffectedCents=12413202, amountOutsideThisPendingCents=48150901,
        quantifiableNewPendingClasses=dict(A=0,B=0,C=0,D=0,E=12413202),
        classificationNote='Zeros A-D são valores do resíduo que puderam ser quantificados por conta/beneficiário; não significam inexistência desses custos na escola.',
        knownPEs=sum(r['checkedPE'] is not None for r in comparisons), definitivePEs=0,
        knownPESum=sum(r['checkedPE'] or 0 for r in comparisons), mathematicalMismatches=mismatches,
        teacherCheck=dict(allocationCount=len(ids), uniqueIds=True, occurrenceFractionsAtMostOne=True),
        backup=dict(sha256=hashes[str(protected_paths[1])], entriesCRCChecked=archive_entries,
            restoredInMemory=True, sqliteIntegrity=integrity, sameLogicalDatabase=same_dump),
        sourceHashes=hashes, mariaEdnaProtectedCents=maria['cents'])
    lines = ['# Auditoria final após regras administrativas — PE 2027', '', '**NO-GO para fechamento integral.**', '',
        'A autorização administrativa foi aceita: turmas D normais; estrutura docente compartilhada conforme grade; 8º C existente com 20 alunos; setores administrativos/estruturais globais salvo exclusividade; custos exclusivos protegidos. Não se exige reconfirmar essas decisões.', '',
        'A nova classificação da NATUREZA resolve parte da pendência: contas de serviços administrativos/estruturais abaixo passam a D por autorização expressa. O impedimento que resta é QUANTITATIVO: não existe a ponte que identifica quanto de cada conta compõe os R$ 37.754,06 de folha, R$ 24.760,30 de apoio e R$ 61.617,66 de gerais das origens. Esses blocos contêm também naturezas não abrangidas automaticamente pela regra global. Classificar uma conta não quantifica sua presença no saldo de uma turma.', '',
        'Por isso não foi reexecutada a simulação anterior, nem usado o saldo como se fosse integralmente global. Nenhuma transferência efetuada. Os PEs vigentes foram conferidos, não substituídos por novos PEs definitivos.', '',
        '## Regras aceitas e tratamento', '',
        '| Regra | Tratamento nesta auditoria |','|---|---|',
        '| A — exclusivo | Quotas e postos comprovados preservados; Maria Edna G4 B integral, sem movimentação. |',
        '| B — série | Benefício às paralelas autorizado; somente frações de aulas demonstradas pela grade, já contabilizadas, preservadas. Não copiar salário integral. |',
        '| C — segmento | Quotas C28/C29 com vínculo FI já comprovado preservadas. A autorização global tem exceção explícita para vínculos de segmento comprovados. |',
        '| D — global | Abrangência administrativa aprovada; contas globais identificadas abaixo. Não se identifica sua parcela nos saldos apenas pelo total escolar da conta. |',
        '| E — não identificado | Saldo misto sem quantia por beneficiário; não significa que a existência dos setores esteja em dúvida. |', '',
        'Lohana = Auxiliar Administrativo, não docente; Marcelo na folha; Jailane, Veroneide e Paula ASG, 44h, R$ 1.690,50 por pessoa. Nenhuma estimativa de encargos ou novo salário. Os R$ 274,14 históricos do 8º C continuam não aditivos.', '',
        '## Classificação das contas — natureza versus valor disponível no saldo', '',
        '| Conta | Descrição | Classe após autorização | Mensal escola R$ (referência, não somar) | Parcela nos saldos | Origem / motivo |','|---|---|---|---:|---|---|']
    for a in classifications:
        lines.append(f"| {a['code']} | {a['description']} | {a['classification']} | {br(a['schoolReferenceCents'])} | N/D | {a['documentarySource']}; {a['reason']} |")
    lines += ['', 'O valor escolar de uma conta pode conter custos já cobertos em outras 26 turmas, quotas nominais protegidas e a reserva. Não usar o total da conta para recompor os saldos das 15 turmas por proporcionalidade: isso criaria uma ligação contábil não demonstrada. Contas 411 de salários/encargos misturam docentes, auxiliares exclusivos e administrativos; não são todas D.', '',
        '## Conferência das 41 turmas — diagnóstico, não tabela definitiva de fechamento', '',
        'Docente, auxiliares/diretos e segmento são controles nominais já existentes dentro do orçamento, não acréscimos. Série/global N/D não é zero: não há decomposição financeira completa nesses níveis. O custo total conserva a cobertura vigente e não resulta da soma apenas dos controles nominais. O ticket é o ticket de planejamento homologado, não um novo ticket real de caixa.', '',
        '| Turma | Capacidade | Matriculados | Ticket líquido R$ | Docente nominal R$ | Auxiliares/diretos R$ | Série R$ | Segmento quota R$ | Global R$ | Custo mensal vigente R$ | PE conferido | PE % capacidade | Situação |',
        '|---|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---|']
    for r in comparisons:
        pe='N/D' if r['checkedPE'] is None else str(r['checkedPE'])
        percent='N/D' if r['peCapacityPercent'] is None else f"{r['peCapacityPercent']:.2f}%".replace('.',',')
        lines.append(f"| {r['name']} | {r['capacity']} | {r['enrolled']} | {br(r['ticketCents'])} | {br(r['teacherNominalCents'])} | {br(r['directNominalCents'])} | N/D | {br(r['segmentQuotaCents'])} | N/D | {br(r['costAfterCents'])} | {pe} | {percent} | {r['situation']} |")
    lines += ['', '## PE anterior × após conferência × diferença', '',
        '| Turma | PE anterior | PE após conferência (não definitivo) | Diferença | Alteração material |','|---|---:|---:|---:|---|']
    for r in comparisons:
        lines.append(f"| {r['name']} | {r['peBefore'] if r['peBefore'] is not None else 'N/D'} | {r['checkedPE'] if r['checkedPE'] is not None else 'N/D'} | {r['peDifference'] if r['peDifference'] is not None else 'N/D'} | Nenhuma |")
    lines += ['', '2º C permanece PE 33, custo R$ 19.765,63. 3º C permanece PE 55, custo R$ 21.286,06. A regra global não comprova que as antigas retiradas de R$ 9.490,37 e R$ 11.120,96 correspondam a serviços globais. Não foram repetidas as reduções 33→17 e 55→26.', '',
        '## Quatro turmas sem cobertura integral', '', '| Turma | Nominal rastreado R$ (não aditivo) | Custo integral | PE | Bloqueio quantitativo |','|---|---:|---|---|---|']
    for name, cents in [('1º D',311329),('2º D',256880),('3º D',341529),('8º C',287865)]:
        lines.append(f'| {name} | {br(cents)} | N/D | N/D | Quanto dos saldos atuais corresponde a serviços beneficiando esta turma, separado dos postos exclusivos e da cobertura já contabilizada |')
    lines += ['', '## Dez provas de fechamento', '', '| Prova | Resultado |','|---|---|',
        '| 1. Total antes/depois | R$ 605.641,03 = R$ 605.641,03; diferença R$ 0,00. |',
        '| 2. Soma das 41 linhas | R$ 605.641,03 atribuídos em 37 linhas; quatro custos integrais N/D. A soma não prova que as 41 tenham cobertura integral. |',
        f'| 3. Exclusivos protegidos | Todas as linhas/quotas preservadas. Maria Edna no G4 B: R$ {br(maria["cents"])}. |',
        f'| 4. Docentes compartilhados | {len(ids)} IDs de alocação distintos; nenhuma soma de frações financeiras por ocorrência maior que 1. Multiplicador 4,5 preservado. |',
        '| 5. Série/segmento/global | Autorizações reconhecidas; classificação monetária completa ainda não demonstrada. Bloqueante. |',
        '| 6. PCLD/inadimplência | PCLD R$ 42.117,80 e descontos orçados R$ 177.901,08 continuam neutralizados; não reinseridos. Ticket homologado preserva inadimplência única. |',
        '| 7. Reserva | R$ 15.827,05 separada. Envelope incluindo reserva R$ 621.468,08. |',
        '| 8. Nenhuma despesa criada para atingir PE | Nenhuma criação de custo ou alteração de linha. |',
        '| 9. Nenhum custo eliminado para reduzir PE | Nenhuma exclusão ou retirada aplicada. |',
        '| 10. Pessoal sem duplicidade | Nenhum novo lançamento nominal; grade sem repetição financeira de ocorrência. Não é possível certificar a composição interna dos saldos desconhecidos por empregado. |', '',
        '## Totais por classificação — limite explícito', '',
        '| Dentro dos R$ 124.132,02 em análise | Valor quantitativamente vinculável R$ |','|---|---:|',
        '| A — exclusivo | 0,00 identificado dentro do resíduo; quotas conhecidas estão fora dele |',
        '| B — série | 0,00 quantificável do resíduo |',
        '| C — segmento | 0,00 adicional quantificável do resíduo |',
        '| D — global | 0,00 quantificável do resíduo; contas globais reconhecidas, parcela não determinada |',
        '| E — sem ligação quantitativa por conta/beneficiário | 124.132,02 |',
        '| Valor fora desta pendência, preservado sem reclassificação presumida | 481.509,01 |',
        '| Total reconciliado da escola | 605.641,03 |',
        '| Diferença antes/depois | 0,00 |', '',
        'Os zeros acima não significam ausência de custos exclusivos, de série, segmento ou globais na escola. O total escolar por essas cinco categorias permanece NÃO DETERMINADO: atribuir os R$ 481.509,01 preservados a alguma delas sem decomposição seria outra classificação presumida. A nova regra classifica natureza; não permite transformar totais escolares de referência em parcelas residuais. A pendência de R$ 124.132,02 é material e não foi descartada para obter GO.', '',
        '## Decisões objetivas que ainda faltam', '',
        'Não falta aprovar novamente beneficiários dos setores globais. Falta fornecer a ligação monetária, no formato: turma de origem / bloco / conta / posto ou serviço / valor mensal já incluído / abrangência ou exceção exclusiva. As 33 origens e 64 contas estão no mapa aprovado em output/mapa-pendencias-financeiras-2027/MAPA-PARA-DECISAO-HUMANA.md.', '',
        '1. FOLHA — dos R$ 37.754,06 residuais, quanto corresponde a salários/encargos/provisões de docentes ou postos exclusivos e quanto a setores globais aprovados? Indique conta e valor por cada origem do mapa, descontadas as quotas nominais já protegidas.',
        '2. APOIO — dos R$ 24.760,30 residuais, quais parcelas são estágio/auxiliar exclusivo e quais são serviços administrativos globais ou de segmento? Indique posto/serviço, conta e valor por origem, separado da cobertura C28/C29 e dos estágios já protegidos.',
        '3. GERAIS — dos R$ 61.617,66 residuais, qual valor por origem corresponde às contas D identificadas nesta tabela, e quais parcelas, se houver, correspondem a atividade/bem/serviço exclusivo ou de série/segmento? Informe os valores e as exceções; não é necessário reconfirmar que os setores administrativos comuns são globais.', '',
        '## Backup e preservação', '',
        f'Backup {protected_paths[1].name}: SHA-256 {hashes[str(protected_paths[1])]}. CRC de {archive_entries} entradas verificado. Imagem SQLite restaurada exclusivamente em memória, integrity_check=ok; conteúdo lógico integral igual ao banco local aberto em modo somente leitura. Nenhuma restauração sobre o banco operacional.',
        'O arquivo da autorização foi preservado textualmente no JSON desta auditoria. Nenhum deploy, push, publicação, escrita no banco, Supabase remoto ou produção. Nenhuma alteração da grade, dos dados atuais, dos PEs ou da reserva.']
    logs=[('testes-python.txt','Ran 415 tests'),('testes-js-verificado.txt','# pass 92'),('testes-sql-verificado.txt','Ran 9 tests')]
    passed=all((OUT/p).exists() and marker in (OUT/p).read_text(encoding='utf-8',errors='replace') for p,marker in logs)
    result['localTestsCompleted']=passed
    lines += ['', '## Testes locais', '', '415 testes Python, 92 entradas do executor JavaScript e 9 testes SQL estáticos aprovados; logs nesta pasta.' if passed else 'Execução dos testes em andamento; relatório será atualizado após conclusão.']
    assert not mismatches, mismatches
    assert all(digest(Path(p))==h for p,h in hashes.items())
    (OUT/'AUDITORIA-FINAL-NO-GO.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (OUT/'auditoria-final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=result['status'],classifiedGlobalAccounts=sum(a['classification']=='D' for a in classifications),
        peKnown=result['knownPEs'],peSum=result['knownPESum'],backup=result['backup'],tests=passed),ensure_ascii=True))

if __name__=='__main__':
    main()
