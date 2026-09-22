"""Leitura do fechamento aprovado: sem motor de cálculo, banco ou rede."""
import hashlib
import json
from pathlib import Path

CHECKPOINT_ID = 'PE-2027-FECHAMENTO-TECNICO-APROVADO-2026-09-22'
SNAPSHOT_FILE = Path(__file__).with_name('approved_pe_2027_snapshot.json')
# Hash fixado ao copiar a fonte congelada; não aceitar outro conteúdo por config.
SNAPSHOT_SHA256 = 'a86183ae79d77b1b5ec1125b196e3c0b94ae2d7229e80fcd7c0a34928b0a198e'

class SnapshotIntegrityError(ValueError):
    pass

def load_approved_snapshot():
    raw=SNAPSHOT_FILE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SNAPSHOT_SHA256:
        raise SnapshotIntegrityError('Snapshot aprovado diverge do hash congelado')
    snapshot=json.loads(raw)
    rows=snapshot.get('rows',[])
    def require(condition,message):
        if not condition:raise SnapshotIntegrityError(message)
    require(snapshot.get('checkpointId')==CHECKPOINT_ID,'Checkpoint incorreto')
    require(len(rows)==41,'São necessárias exatamente 41 turmas')
    require(len({r['id'] for r in rows})==41 and len({r['turma'] for r in rows})==41,'Turmas duplicadas')
    require(all(type(r.get('peAlunos')) is int and r['peAlunos']>0 for r in rows),'PE ausente ou inválido')
    for field,total in [('capacidade',1103),('matriculados',775),('vagas',328),('custoTotalCentavos',60564103)]:
        require(sum(r[field] for r in rows)==total,'Total divergente: '+field)
    require(snapshot.get('reserveCents')==1582705 and snapshot.get('reserveIncludedInClassCost') is False,'Reserva incorreta')
    require(snapshot.get('costTotalCents')==60564103,'Custo escolar incorreto')
    require(next(r for r in rows if r['turma']=='8º C')['matriculados']==20,'8º C divergente')
    # Somente validação das parcelas armazenadas; jamais divide custo/ticket.
    parts=('docenteCentavos','diretosExclusivosCentavos','rateioSerieNovoCentavos','rateioSegmentoCentavos',
           'coberturaAnteriorMantidaCentavos','folhaGlobalCentavos','apoioGlobalCentavos','geraisGlobalCentavos')
    require(all(sum(r[k] for k in parts)==r['custoTotalCentavos'] for r in rows),'Composição de custo divergente')
    return snapshot
