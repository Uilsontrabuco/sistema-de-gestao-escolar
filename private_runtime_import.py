"""Admin-only, hash-pinned provisioning with atomic rollback preservation."""
from copy import deepcopy
import hashlib
import json

from benefits_2027 import is_planned, nominal_enrollments, sync_benefits, summarize
from private_artifact_manifest import ARTIFACT_SHA256

ROLLBACK_ID = "rollback/benefits-private-runtime-20260922"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def checked_artifacts(body):
    supplied = body.get("artifacts", {})
    if not isinstance(supplied, dict) or set(supplied) != set(ARTIFACT_SHA256):
        raise ValueError("Pacote privado incompleto ou não homologado.")
    result = {}
    for name, expected in ARTIFACT_SHA256.items():
        if not isinstance(supplied[name], str):
            raise ValueError("Formato de artefato inválido.")
        raw = supplied[name].encode("utf-8")
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Integridade do pacote privado divergente.")
        result[name] = raw
    return result


def academic_guard(state):
    classes = state["classes"]
    actual = (len(classes), len({c["id"] for c in classes}), sum(c["capacity"] for c in classes),
              sum(c["students"] for c in classes), state["enrollments"]["new"], state["enrollments"]["re"])
    if actual != (41, 41, 1103, 775, 37, 738):
        raise ValueError("Base acadêmica divergiu da revisão; nenhuma alteração aplicada.")


def propose(state, source):
    academic_guard(state)
    if not isinstance(source, list) or any(not is_planned(b) for b in source):
        raise ValueError("Fonte de benefícios inválida.")
    if len({b["id"] for b in source}) != len(source):
        raise ValueError("Identidades duplicadas na fonte.")
    updated = deepcopy(state)
    by_id = {b["id"]: b for b in updated["benefits"]}
    fields = ("studentKey", "studentId", "classId", "sourceClass", "rate", "grossCents", "discountCents", "postDiscountCents")
    for record in source:
        old = by_id.get(record["id"])
        if old:
            if any(old.get(k) != record.get(k) for k in fields):
                raise ValueError("Benefício existente divergente; conciliação manual necessária.")
            continue
        candidate = deepcopy(record)
        candidate.update(active=False, state="PREVISTO", enrollmentId=None, history=[],
                         linkStatus="AGUARDANDO_MATRICULA" if candidate.get("classId") else "TURMA_INVALIDA")
        updated["benefits"].append(candidate)
        by_id[candidate["id"]] = candidate
    sync_benefits(updated)
    if len({b["id"] for b in updated["benefits"]}) != len(updated["benefits"]):
        raise ValueError("Duplicidade de benefícios bloqueada.")
    protected = lambda value: {k: v for k, v in value.items() if k != "benefits"}
    if protected(state) != protected(updated):
        raise ValueError("Alteração fora do escopo bloqueada.")
    summary = summarize(updated)
    report = {k: summary[k] for k in ("total", "active", "waiting", "pending")}
    report.update(source=len(source), existing=len(state["benefits"]), inserted=len(updated["benefits"]) - len(state["benefits"]),
                  nominalEnrollments=len(nominal_enrollments(state)), duplicateBenefits=0,
                  ambiguous=sum(b.get("linkStatus") == "IDENTIDADE_AMBIGUA" for b in updated["benefits"]),
                  invalidClass=sum(b.get("linkStatus") == "TURMA_INVALIDA" for b in updated["benefits"]),
                  academicDataPreserved=True, approvedPEPreserved=True)
    return updated, report


def process_import(store, body, actor, confirm=False):
    if not actor or not actor.get("isAdmin") or not actor.get("active"):
        raise PermissionError("Somente administrador ativo.")
    artifacts = checked_artifacts(body)
    source = json.loads(artifacts["benefits-source.json"])
    with store.db() as db:
        row = db.execute("SELECT version,payload FROM state WHERE id=1" + (" FOR UPDATE" if confirm else "")).fetchone()
        state = json.loads(row["payload"])
        updated, report = propose(state, source)
        report.update(version=row["version"], runtimeArtifacts=len(artifacts), applied=False)
        if not confirm:
            return report
        if body.get("expectedVersion") != row["version"]:
            raise ValueError("A base mudou após a prévia. Analise novamente.")
        originals = {}
        for name, raw in artifacts.items():
            old = db.execute("SELECT content FROM assets WHERE id=? FOR UPDATE", ("private-runtime/" + name,)).fetchone()
            if old and bytes(old["content"]) != raw:
                raise ValueError("Artefato privado existente diverge; operação bloqueada.")
            originals[name] = old is not None
        if not db.execute("SELECT id FROM assets WHERE id=?", (ROLLBACK_ID,)).fetchone():
            backup = dict(version=row["version"], benefits=state["benefits"], protectedHash=digest({k:v for k,v in state.items() if k != "benefits"}),
                          sourceHash=ARTIFACT_SHA256["benefits-source.json"], existingArtifacts=originals)
            db.execute("INSERT INTO assets(id,content) VALUES(?,?)", (ROLLBACK_ID, json.dumps(backup, ensure_ascii=False).encode()))
        for name, raw in artifacts.items():
            if not originals[name]:
                db.execute("INSERT INTO assets(id,content) VALUES(?,?)", ("private-runtime/" + name, raw))
        if updated != state:
            db.execute("UPDATE state SET version=?,payload=? WHERE id=1 AND version=?", (row["version"] + 1, json.dumps(updated, ensure_ascii=False), row["version"]))
            db.execute("INSERT INTO audit(payload) VALUES(?)", (json.dumps(dict(module="benefits", action="private-source-sync", date="2026-09-22", sourceCount=len(source), inserted=report["inserted"], activated=report["active"], protectedDataPreserved=True)),))
            report["version"] += 1
        report.update(applied=True, rollbackPreserved=True)
    return report
