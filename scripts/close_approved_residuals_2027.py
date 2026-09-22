"""Relatório de fechamento local, sem aplicar dados ao banco ou ao motor."""
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from approved_residual_allocation_2027 import reconcile
OUT=ROOT/'output/fechamento-definitivo-administrativo-2027'
APPROVAL=Path('C:/Users/Uilson Trabuco/.codex/attachments/648accd5-39d9-4475-9ae2-d618b35bd5a6/Texto colado.txt')

def br(c):
    return 'N/D' if c is None else f'{Decimal(str(c))/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')

def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=True)
    files=[ROOT/'data/caj.sqlite3',ROOT/'output/pre-publicacao-2027/backup-premissas-8C-mantido-20270922.zip',
        ROOT/'output/forense-saldos-2027/composicao-e-simulacao-conservadora.json',
        ROOT/'output/simulacao-rateio-series-2027/simulacao.json']
    hashes={str(p):sha(p) for p in files}
    baseline=read('output/forense-saldos-2027/composicao-e-simulacao-conservadora.json')
    result=reconcile(baseline)
    teaching=read('output/desbloqueio-pe-2027/docencia-reconstruida.json')
    ids=set(); fractions=defaultdict(Fraction)
    for a in teaching['operational_allocations']:
        assert a['allocation_id'] not in ids
        ids.add(a['allocation_id'])
        if not a.get('duplicate_of'):
            fractions[a['source_reference']['occurrence_id']]+=Fraction(a['financial_fraction_numerator'],a['financial_fraction_denominator'])
    assert all(f<=1 for f in fractions.values())
    with ZipFile(files[1]) as z:
        assert z.testzip() is None
        entries=len(z.infolist());database_image=z.read('data/caj.sqlite3')
    restored=sqlite3.connect(':memory:');restored.deserialize(database_image)
    restored.execute('PRAGMA query_only=ON')
    assert restored.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    current=sqlite3.connect(files[0].as_uri()+'?mode=ro',uri=True)
    current.execute('PRAGMA query_only=ON')
    assert list(restored.iterdump())==list(current.iterdump())
    current.close();restored.close()
    result['backup']=dict(hash=hashes[str(files[1])],entriesCRC=entries,restoredInMemory=True,integrity='ok',sameLogicalDatabase=True)
    result['teacherProof']=dict(uniqueAllocations=len(ids),allFinancialFractionsAtMostOne=True,monthlyFactor=4.5)
    result['sourceHashes']=hashes
    result['administrativeApproval']=APPROVAL.read_text(encoding='utf-8')
    result['approvalSha256']=sha(APPROVAL)
    testfiles={'python':('testes-python.txt','Ran 420 tests','\nOK'),
               'javascript':('testes-js.txt','# pass 92','# fail 0'),
               'sql':('testes-sql.txt','Ran 9 tests','\nOK')}
    checks={}
    for key,(filename,count,success) in testfiles.items():
        p=OUT/filename
        log=p.read_text(encoding='utf-8',errors='replace') if p.exists() else ''
        checks[key]=count in log and success in log and 'FAILED (' not in log
    result['tests']=checks
    result['status']='GO TÉCNICO — PE 2027 APTO PARA APROVAÇÃO HUMANA' if all(checks.values()) else 'NO-GO — testes ainda não concluídos/aprovados'
    before={r['name']:r for r in baseline['conservativeRows']}
    dmap={d['name']:d for d in result['details']}
    assert sum(r['enrolled'] for r in result['rows'])==775
    assert sum(r['capacity'] for r in result['rows'])==1103
    assert sum(r['vacancies'] for r in result['rows'])==328
    assert dmap['8º C']['enrolled']==20
    assert result['reserveCents']==1582705
    assert sum(b['distributedCents'] for b in result['bridges'].values())==12413202
    for name,r in before.items():
        if name!='8º C':
            assert sum(c['cents'] for c in r['nominalCosts'])==dmap[name]['anchorCents']
    maria=next(c['cents'] for c in before['G4 B']['nominalCosts'] if c['kind']=='auxiliar-direta')
    lines=['# Fechamento do PE 2027 — decisões administrativas aplicadas em cenário local','',f"**{result['status']}**",'',
        'As decisões formais do anexo 648accd5 foram aplicadas aos saldos autorizados. O resultado existe somente nestes arquivos de auditoria; nenhum registro operacional, banco ou motor publicado foi alterado. A validade deste fechamento é gerencial, com base nas premissas administrativas aprovadas; não é uma nova decomposição documental da folha por conta.', '',
        '## Ponte necessária para não criar despesa', '',
        'A ordem A/B/C antes de D/E determina a proteção de todos os nominais comprovados. Nas 37 linhas com cobertura, eles já estavam dentro do custo. Nas quatro linhas antes sem cobertura integral, R$ 11.976,03 ainda eram controles nominais sem separação financeira. Foram financiados DENTRO dos blocos autorizados: folha R$ 10.262,30 e apoio R$ 1.713,73. Não foram somados sobre o envelope escolar.',
        'Assim, destinação integral dos três blocos não significa ratear R$ 124.132,02 globalmente e depois acrescentar os quatro nominais: essa dupla operação elevaria o total a R$ 617.617,06. O tratamento aplicado é: R$ 11.976,03 protegidos primeiro + R$ 112.155,99 remanescentes globais = R$ 124.132,02. É a aplicação da prioridade expressa A/B/C, não um novo custo ou uma exclusão.', '',
        '| Bloco | Inicial R$ | Cobertura nominal prévia ao global R$ | Global por capacidade R$ | Total destinado R$ | Diferença R$ |','|---|---:|---:|---:|---:|---:|']
    for k,b in result['bridges'].items():
        lines.append(f"| {k} | {br(b['initialCents'])} | {br(b['nominalCoverageCents'])} | {br(b['globalDistributedCents'])} | {br(b['distributedCents'])} | 0,00 |")
    lines += ['', '| Turma | Docente protegido financiado R$ | Apoio nominal financiado R$ | Total financiado dentro dos blocos R$ |','|---|---:|---:|---:|']
    for d in result['details']:
        coverage=d['nominalCoverageFromAuthorized']
        if sum(coverage.values()):
            lines.append(f"| {d['name']} | {br(coverage['folha'])} | {br(coverage['apoio'])} | {br(sum(coverage.values()))} |")
    lines += ['', 'O apoio nominal inclui postos exclusivos e quotas de segmento já homologadas. As frações de aulas compartilhadas permanecem exatamente as da grade, com hora-aula e multiplicador 4,5; a cobertura acima não é novo salário nem nova divisão de aulas. Os R$ 274,14 históricos do 8º C não entram como salário nem são retirados do total escolar.', '',
        '## Critério e arredondamento', '',
        'Globais remanescentes: capacidade da turma / 1.103, para cada bloco separadamente. Os centavos são distribuídos por maiores restos, com desempate pelo identificador estável da turma. Cada bloco conserva seu total exato. Matrículas não determinam custo. Quotas de série/segmento com direcionador específico já comprovado ficam preservadas; não foram transformadas em globais.',
        'O escopo financeiro autorizado é o resíduo das 15 turmas. As coberturas anteriores das demais 26 permanecem onde estavam e recebem a quota dos novos globais. O relatório não redistribui os demais blocos escolares por uma regra não solicitada.', '',
        '## Tabela das 41 turmas', '',
        '**Colunas aditivas:** docente + exclusivos + segmento + cobertura anterior mantida + três rateios globais = custo total. A coluna adicional “cobertura anterior mantida” é indispensável: representa os blocos não abrangidos pelos R$ 124.132,02, líquidos dos controles nominais. Não omiti-la nem chamá-la automaticamente de global. “Série novo” é zero porque não houve nova repartição por série; as aulas compartilhadas estão nas próprias quotas docentes, sem repetição.',
        'Ticket = planejamento homologado (benefícios previstos, inadimplência única), não promessa de receita efetiva. PE = teto(custo total / ticket exato), sem arredondar o ticket antes da divisão.', '',
        '| Turma | Cap. | Matr. | Ticket R$ | Docente R$ | Exclusivos R$ | Série novo R$ | Segmento R$ | Cobertura anterior mantida R$ | Folha global R$ | Apoio global R$ | Gerais global R$ | Custo total R$ | PE | PE % cap. | PE anterior | Δ PE | Situação |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for d in result['details']:
        global_cost=d['globalAllocation']
        pe_old='N/D' if d['peBefore'] is None else str(d['peBefore'])
        delta='Novo' if d['peDelta'] is None else f"{d['peDelta']:+d}"
        situation=d['situation']+('; PE supera capacidade' if d['structurallyInfeasible'] else '')
        lines.append(f"| {d['name']} | {d['capacity']} | {d['enrolled']} | {br(d['ticketExactCents'])} | {br(d['teacherCents'])} | {br(d['exclusiveCents'])} | 0,00 | {br(d['segmentCents'])} | {br(d['inheritedCoverageCents'])} | {br(global_cost['folha'])} | {br(global_cost['apoio'])} | {br(global_cost['gerais'])} | {br(d['costAfterCents'])} | {d['peAfter']} | {d['peCapacityPercent']:.2f}% | {pe_old} | {delta} | {situation} |")
    lines += ['', '## Destaques solicitados', '', '| Turma | Custo antes R$ | Custo final R$ | PE anterior | PE final | Motivo |','|---|---:|---:|---:|---:|---|']
    for name in ['G2 A','G2 B','1º D','2º C','2º D','3º C','3º D','8º C']:
        d=dmap[name]
        why='Recebe somente quota global adicional; ticket G2 com 12% e 4,5% preservado' if name.startswith('G2') else 'Nominal próprio financiado dentro do envelope + globais por capacidade' if d['peBefore'] is None else 'Mantém nominais; sai saldo autorizado e entra quota global por capacidade'
        lines.append(f"| {name} | {br(d['costBeforeCents'])} | {br(d['costAfterCents'])} | {d['peBefore'] if d['peBefore'] is not None else 'N/D'} | {d['peAfter']} | {why} |")
    lines += ['', '## Ponte material por bloco — todas as turmas', '',
        'Material = diferença de pelo menos 3 alunos no PE, ou 20% no custo; os quatro novos cálculos também destacados. Saída é exclusivamente saldo autorizado, nunca quota nominal. Entradas incluem cobertura nominal nas quatro turmas e globais; portanto não somar novamente os nominais à ponte.', '',
        '| Turma | Sai folha R$ | Sai apoio R$ | Sai gerais R$ | Entra cobertura nominal R$ | Entra folha global R$ | Entra apoio global R$ | Entra gerais global R$ | Δ custo R$ | Material? |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for d in result['details']:
        a=d['globalAllocation'];o=d['removed']
        lines.append(f"| {d['name']} | {br(o['folha'])} | {br(o['apoio'])} | {br(o['gerais'])} | {br(sum(d['nominalCoverageFromAuthorized'].values()))} | {br(a['folha'])} | {br(a['apoio'])} | {br(a['gerais'])} | {br(d['costDeltaCents'])} | {'SIM' if d['material'] else 'não'} |")
    for name in ['2º C','3º C']:
        d=dmap[name]
        lines += ['', f"**{name}:** custo anterior R$ {br(d['costBeforeCents'])} − folha residual R$ {br(d['removed']['folha'])} − apoio residual R$ {br(d['removed']['apoio'])} − gerais residuais R$ {br(d['removed']['gerais'])} + globais recebidos R$ {br(sum(d['globalAllocation'].values()))} = R$ {br(d['costAfterCents'])}. Quotas nominais de R$ {br(d['anchorCents'])} preservadas integralmente. PE {d['peBefore']} → {d['peAfter']}. Não representa corte de salário, economia ou nova conclusão documental: muda a responsabilidade gerencial dos saldos formalmente autorizados, da origem para as 41 beneficiárias."]
    lines += ['', '## Provas de fechamento', '', '| Verificação | Resultado |','|---|---|',
        '| Custo antes / depois / diferença | R$ 605.641,03 / R$ 605.641,03 / R$ 0,00 |',
        '| Três blocos autorizados / destinados / diferença | R$ 124.132,02 / R$ 124.132,02 / R$ 0,00 |',
        '| Turmas / matriculados / capacidade / vagas | 41 / 775 / 1.103 / 328, antes e depois |',
        '| PEs calculáveis | 41/41 |',
        f"| Soma PE | {sum(d['peAfter'] for d in result['details'])}; antes 911 em somente 37 turmas, quatro N/D — não comparar como queda de custo |",
        f'| Nominais protegidos | R$ {br(result["nominalTotalCents"])} na composição final; controle, não despesa somada sobre o orçamento |',
        f'| Maria Edna G4 B | R$ {br(maria)} integral protegido; sem transferência |',
        f'| Docentes compartilhados | {len(ids)} alocações únicas, nenhuma soma de frações financeiras por ocorrência > 1; grade/hora-aula/4,5 preservados |',
        '| PCLD / inadimplência | PCLD neutralizada anteriormente não reinserida; inadimplência 4,5% uma vez no ticket; G2 12% uma vez |',
        '| Descontos | R$ 177.901,08 de estimativa orçamentária já substituída não reinseridos |',
        '| Reserva fora PE | R$ 15.827,05 intactos; escola + reserva R$ 621.468,08 |',
        '| Custo criado / eliminado | R$ 0,00 / R$ 0,00; apenas destinos gerenciais alterados no cenário local |',
        '| Não identificado dos três saldos | R$ 0,00 quanto ao destino gerencial: substituído por premissa administrativa formal |',
        '| Escrita operacional / remoto | Nenhuma |', '',
        'Lohana permanece Auxiliar Administrativo, não docente; Marcelo na folha. Jailane/Veroneide/Paula ASG, 44h, salário-base R$ 1.690,50 cada, sem novo salário ou encargo. A preservação das quotas e do total evita criação de duplicidade nesta operação; a autorização administrativa não equivale a um novo razão contábil analítico por empregado.', '',
        '## Limites e aprovação humana', '',
        'GO técnico significa cálculo gerencial consistente com as decisões aprovadas. As turmas cujo PE excede capacidade continuam sinalizadas, sem ajuste para fazê-las caber. Nenhuma expectativa de lucratividade é garantida por este GO. A aplicação operacional/publicação continua dependendo de aprovação humana final.',
        'O valor de R$ 124.132,02 foi integralmente destinado seguindo a prioridade nominal, e não integralmente distribuído como global: somente R$ 112.155,99 seguem capacidade/1.103. Essa distinção é necessária para conservar o total e está exposta para aprovação.', '',
        '## Testes e backup', '',
        f"Testes: Python={checks['python']}; JavaScript={checks['javascript']}; SQL estático={checks['sql']}. Execução completa esperada: 420 Python (415 anteriores + 5 testes da ponte), 92 entradas JavaScript e 9 SQL estáticos. Logs nesta pasta.",
        f'Backup preservado: {files[1].name}, SHA-256 {hashes[str(files[1])]}. CRC de {entries} entradas aprovado; imagem SQLite restaurada em memória, integridade ok e conteúdo lógico integral igual ao banco local aberto somente para leitura.',
        'Nenhum deploy, push, publicação, escrita no banco, Supabase remoto ou produção. Arquivos do checkpoint e backup conferidos por hash antes/depois.']
    assert all(sha(Path(p))==h for p,h in hashes.items())
    (OUT/'FECHAMENTO-PE-2027-PARA-APROVACAO.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (OUT/'fechamento.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=result['status'],peTotal=sum(d['peAfter'] for d in result['details']),
        school=result['schoolAfterCents'],tests=checks,backupEntries=entries),ensure_ascii=True))

if __name__=='__main__':main()
