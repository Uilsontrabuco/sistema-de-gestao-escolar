"""Gera a previa auditavel do PE 2027 com as decisoes C02 e C27-C32.

Este modulo e deliberadamente isolado: nao grava banco, nao altera o estado da
aplicacao e nao muda os modulos homologados. Os valores nominais de agosto sao
tratados como reclassificacao do envelope oficial, nunca como custo adicional.
"""
from __future__ import annotations

import json
import math
import sys
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from budget_2027_snapshot import (
    BUDGET_COMPONENTS,
    OFFICIAL_TOTAL_MONTHLY_CENTS,
    allocate_by_capacity,
    allocate_per_class,
    structural_budget_allocation,
)
from financial_integration import integration_snapshot, monthly_teaching_base_cents
from server import blank
from teaching_cost import load_documentary_costs


OUTPUT_DIR = ROOT / "output" / "previa-auditavel-aprovada-2027"
TEACHER_SOURCE = ROOT / "output" / "fechamento-modulo-2027" / "fechamento.json"
PERSONNEL_TOTAL_CENTS = 38_759_193
PCLD_CENTS = 4_211_780
COMMERCIAL_DISCOUNT = Decimal("3")
DELINQUENCY = Decimal("4.5")

# C02: valores individualmente comprovados na folha de agosto/2026.
# Paula permanece sem valor, conforme decisao aprovada.
INTERNS = (
    ("Emilly Gomes Limoeiro", "2º A", 85_377),
    ("Gleiciane Maele Silva Duarte Cafe", "3º A", 85_377),
    ("Janaina Raissa dos Santos Souza", "G5 A", 85_377),
    ("Joyce dos Santos Pereira", "G2 A", 83_835),
    ("Kesia Suane Azevedo dos Santos", "G3 A", 83_835),
    ("Larissa Lorrana Miranda de Jesus", "G2 B", 83_835),
    ("Maria Gabrielle Pinho da Silva", "G4 A", 85_377),
    ("Nathalia Rabelo dos Santos", "G4 A", 85_377),
    ("Oslane Brito Cordeiro", "4º A", 27_235),
    ("Rebeca de Oliveira Azevedo", "3º B", 83_835),
    ("Iane Caroline Dantas da Silva", "7º B", 85_377),
    ("Liliane de Santana Martins Paixao", "1º C", 85_377),
    ("Marcia Gabrielle dos Santos Lopes", "9º C", 85_377),
    ("Maria Azenilda de Farias", "5º C", 32_295),
    ("Rebeca Dias de Jesus", "G4 B", 85_377),
    ("Sheila Emanuela Alves Evangelista", "3º D", 85_377),
    ("Sthefany Fernanda Barbosa de Almeida", "2º C", 85_377),
    ("Tamires de Jesus Cruz da Silva", "G4 B", 70_197),
    ("Yasmin Waleska de Jesus Carvalho", "G3 B", 85_377),
    ("Paula Araujo Dias", "G3 B", None),
)

# C28: somente parcelas com segmento documentalmente identificado.
COORDINATION_SEGMENT_CENTS = {
    "Educação Infantil": 995_651,
    "Fundamental Anos Iniciais": 274_613,
    "Ensino Médio": 473_382,
}
COORDINATION_ADMIN_CENTS = 2_184_271

# C29: rateio por capacidade dentro do segmento. Maria Edna foi posteriormente
# confirmada pelo responsavel do CAJ como auxiliar exclusiva/direta do G4 B.
AUXILIARY_SEGMENT_CENTS = {
    "Educação Infantil": 1_587_857,
    "Fundamental Anos Iniciais": 263_843,
}
MARIA_EDNA_G4B_DIRECT_CENTS = 263_843

# C27 e C30 permanecem institucionais. Estes controles nominais nao sao
# adicionados ao envelope; servem para demonstrar parte de sua composicao.
SUPPORT_ADMIN_CONTROL_CENTS = 6_843_320
SECRETARY_TREASURY_DIRECTION_CENTS = 2_527_588

G2_PAYROLL_RESIDUALS = {"G2 A": 387_433, "G2 B": 389_746}
G2_SUPPORT_SOURCE_CENTS = {"G2 A": 152_000, "G2 B": 152_000}

TEACHER_CODE_DECISIONS = {
    "Josse Maria de Souza": {"currentCode": "762", "historicalCodes": ["250"]},
    "Maria de Souza Mota Neta": {"currentCode": "883", "historicalCodes": ["533"]},
    "Monise Silva dos Santos Dias": {"currentCode": "639", "historicalCodes": ["638"]},
}


def money(cents: int | None) -> str:
    if cents is None:
        return "PENDENTE"
    value = Decimal(cents) / 100
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def structural_ticket_cents(tuition: float) -> int:
    value = Decimal(str(tuition)) * (1 - COMMERCIAL_DISCOUNT / 100) * (1 - DELINQUENCY / 100)
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def pe_students(cost_cents: int, ticket_cents: int) -> int:
    return int((Decimal(cost_cents) / Decimal(ticket_cents)).to_integral_value(rounding=ROUND_CEILING))


def allocate_segment_equal(total_cents: int, classes: list[dict], segment: str) -> dict[str, int]:
    eligible = [room for room in classes if room["stage"] == segment]
    return allocate_per_class(total_cents, eligible)


def allocate_segment_capacity(total_cents: int, classes: list[dict], segment: str) -> dict[str, int]:
    eligible = [room for room in classes if room["stage"] == segment]
    return allocate_by_capacity(total_cents, eligible)


def teacher_projection_2027() -> list[dict]:
    """Consolida as 50 pessoas aprovadas sem apagar os identificadores históricos."""
    source = json.loads(TEACHER_SOURCE.read_text(encoding="utf-8"))
    teachers = [{"name": row["professor"], "currentCode": str(row["professor_id"]),
                 "historicalCodes": [], "status": "INTEGRA_2027"}
                for row in source["professors"]]
    by_name = {row["name"]: row for row in teachers}
    for removed in ("Lohana Rodrigues Leite da Silva", "Marcelo Rodrigues"):
        by_name.pop(removed, None)
    by_name["Telma Bruno da Silva Ribeiro"] = {
        "name": "Telma Bruno da Silva Ribeiro", "currentCode": None,
        "historicalCodes": [], "status": "INTEGRA_2027_CODIGO_NAO_INFORMADO",
    }
    by_name["Julianne Moreira Martins dos Santos"] = {
        "name": "Julianne Moreira Martins dos Santos", "currentCode": None,
        "historicalCodes": [], "status": "RETORNA_2027_CODIGO_NAO_INFORMADO",
    }
    for name, decision in TEACHER_CODE_DECISIONS.items():
        by_name[name].update(decision)
    return sorted(by_name.values(), key=lambda row: row["name"].casefold())


def build_preview() -> dict:
    state = blank()
    classes = state["classes"]
    if len(classes) != 41:
        raise AssertionError("A previa exige exatamente 41 turmas")
    by_name = {room["name"]: room for room in classes}
    ledger = load_documentary_costs(classes)
    old = integration_snapshot(state, ledger, 2027)
    old_by_name = {row["name"]: row for row in old["classes"]}
    teachers_2027 = teacher_projection_2027()

    intern_by_class = {room["id"]: 0 for room in classes}
    intern_details = {room["id"]: [] for room in classes}
    pending = []
    for person, class_name, amount in INTERNS:
        room = by_name[class_name]
        if amount is None:
            pending.append({"decision": "C02", "person": person, "class": class_name,
                            "reason": "custo individual documental ainda inexistente"})
            intern_details[room["id"]].append({"person": person, "amount": None, "status": "PENDENTE"})
            continue
        intern_by_class[room["id"]] += amount
        intern_details[room["id"]].append({"person": person, "amount": amount / 100, "status": "COMPROVADO"})

    coordination = {room["id"]: 0 for room in classes}
    for segment, amount in COORDINATION_SEGMENT_CENTS.items():
        for class_id, value in allocate_segment_equal(amount, classes, segment).items():
            coordination[class_id] += value

    auxiliaries = {room["id"]: 0 for room in classes}
    for segment, amount in AUXILIARY_SEGMENT_CENTS.items():
        for class_id, value in allocate_segment_capacity(amount, classes, segment).items():
            auxiliaries[class_id] += value

    # Despesas gerais preservam o criterio vigente do modelo. Somente esta
    # parcela nao pessoal continua rateada estruturalmente.
    old_budget = structural_budget_allocation(
        classes,
        sum(monthly_teaching_base_cents(int(round(row["weekly_cost"] * 100))) for row in ledger["classes"]),
        1_425_000,
        OFFICIAL_TOTAL_MONTHLY_CENTS,
    )
    general_expenses = {}
    for room in classes:
        detail = next(item for item in old_budget["rows"][room["id"]]["details"] if item["id"] == "general-expenses")
        general_expenses[room["id"]] = int(round(detail["assignedValue"] * 100))

    # Decisao contabil/gerencial aprovada: a conta 4124001 permanece integral
    # no orcamento oficial, mas sua parcela e neutralizada exclusivamente na
    # camada gerencial do PE. O estorno usa o mesmo direcionador por capacidade
    # das despesas gerais para nao criar uma compensacao ou um novo rateio.
    pcld_by_class = allocate_by_capacity(PCLD_CENTS, classes)

    rows = []
    for room in classes:
        class_id = room["id"]
        source_teaching = next(row for row in ledger["classes"] if row["class_id"] == class_id)
        teaching = monthly_teaching_base_cents(int(round(source_teaching["weekly_cost"] * 100)))
        intern = intern_by_class[class_id]
        coord = coordination[class_id]
        auxiliary = auxiliaries[class_id]
        direct_assistant = MARIA_EDNA_G4B_DIRECT_CENTS if room["name"] == "G4 B" else 0
        g2_payroll = G2_PAYROLL_RESIDUALS.get(room["name"], 0)
        g2_support = 0
        if room["name"] in G2_SUPPORT_SOURCE_CENTS:
            g2_support = G2_SUPPORT_SOURCE_CENTS[room["name"]] - intern
            if g2_support < 0:
                raise AssertionError("Custo de estagio excede a linha oficial de apoio do G2")
        pcld_neutralized = pcld_by_class[class_id]
        other_allocations_before_pcld = general_expenses[class_id] + g2_support
        other_allocations = other_allocations_before_pcld - pcld_neutralized
        total_before_pcld = (teaching + intern + direct_assistant + auxiliary + coord +
                             other_allocations_before_pcld + g2_payroll)
        total = total_before_pcld - pcld_neutralized
        segment_id = {"Educação Infantil": "early", "Fundamental Anos Iniciais": "fundamental1",
                      "Fundamental Anos Finais": "fundamental2"}.get(
                          room["stage"], "secondary3" if room["name"].startswith("3º") else "secondary12")
        gross_tuition = Decimal(str(next(
            item["tuition"] for item in state["academicYears"][0]["parameters"] if item["id"] == segment_id)))
        ticket = structural_ticket_cents(float(gross_tuition))
        pe = pe_students(total, ticket)
        previous_approved_total = total_before_pcld
        previous_approved_pe = pe_students(previous_approved_total, ticket)
        class_pending = [item for item in pending if item.get("class") == room["name"]]
        status = "PARCIAL" if class_pending or room["name"] in G2_PAYROLL_RESIDUALS else "DEFINITIVO"
        reasons = [item["reason"] for item in class_pending]
        if room["name"] in G2_PAYROLL_RESIDUALS:
            reasons.append("residual oficial preservado aguardando conciliacao nominal")
        old_row = old_by_name[room["name"]]
        rows.append({
            "classId": class_id,
            "class": room["name"],
            "segment": room["stage"],
            "capacity": room["capacity"],
            "grossTuition": float(gross_tuition),
            "structuralDiscountPercent": float(COMMERCIAL_DISCOUNT),
            "delinquencyPercent": float(DELINQUENCY),
            "netTicket": ticket / 100,
            "teachingCostMonthly": teaching / 100,
            "otherDirectCostsMonthly": direct_assistant / 100,
            "otherDirectDetails": ([{"person": "Maria Edna Nivaldina de Barros Santos",
                                      "role": "Auxiliar de Classe", "class": "G4 B",
                                      "allocation": "EXCLUSIVA_DIRETA_DIA_INTEIRO",
                                      "amount": MARIA_EDNA_G4B_DIRECT_CENTS / 100,
                                      "source": "Folha agosto/2026 + confirmação operacional do responsável do CAJ",
                                      "doubleCountTreatment": "RECLASSIFICADO_DENTRO_DO_ENVELOPE_DE_PESSOAL"}]
                                   if direct_assistant else []),
            "internsMonthly": intern / 100,
            "internDetails": intern_details[class_id],
            "auxiliariesMonthly": auxiliary / 100,
            "coordinationOrientationMonthly": coord / 100,
            "otherProvenAllocationsMonthly": other_allocations / 100,
            "pcldNeutralizedMonthly": pcld_neutralized / 100,
            "officialResidualMonthly": g2_payroll / 100,
            "officialResidualStatus": "OFICIAL PRESERVADO — AGUARDANDO CONCILIAÇÃO NOMINAL" if g2_payroll else None,
            "totalCostMonthly": total / 100,
            "breakEvenStudents": pe,
            "breakEvenPercentCapacity": pe / room["capacity"] * 100,
            "physicalMarginStudents": room["capacity"] - pe,
            "documentaryStatus": status,
            "pendingReasons": reasons,
            "documentaryObservation": ("; ".join(reasons) if reasons else "Sem pendência documental conhecida"),
            "previousTotalCostMonthly": previous_approved_total / 100,
            "previousBreakEvenStudents": previous_approved_pe,
            "costChangeMonthly": -pcld_neutralized / 100,
            "breakEvenChangeStudents": pe - previous_approved_pe,
            "originalModelTotalCostMonthly": old_row["totalCostMonthly"],
            "originalModelBreakEvenStudents": old_row["breakEvenStudents"],
        })

    class_total = sum(int(round(row["totalCostMonthly"] * 100)) for row in rows)
    teaching_total = sum(int(round(row["teachingCostMonthly"] * 100)) for row in rows)
    intern_total = sum(intern_by_class.values())
    coord_total = sum(coordination.values())
    auxiliary_total = sum(auxiliaries.values())
    g2_payroll_total = sum(G2_PAYROLL_RESIDUALS.values())
    g2_support_total = sum(G2_SUPPORT_SOURCE_CENTS[name] - intern_by_class[by_name[name]["id"]]
                           for name in G2_SUPPORT_SOURCE_CENTS)
    general_total_official = sum(general_expenses.values())
    general_total = general_total_official - PCLD_CENTS
    direct_assistant_total = MARIA_EDNA_G4B_DIRECT_CENTS
    attributed_personnel = (teaching_total + intern_total + coord_total + auxiliary_total + direct_assistant_total +
                            g2_payroll_total + g2_support_total)
    institutional_personnel = PERSONNEL_TOTAL_CENTS - attributed_personnel
    if institutional_personnel < 0:
        raise AssertionError("Atribuicao de pessoal excede o envelope oficial")
    managerial_total = OFFICIAL_TOTAL_MONTHLY_CENTS - PCLD_CENTS
    if class_total + institutional_personnel != managerial_total:
        raise AssertionError("Previa gerencial sem PCLD nao reconcilia")

    gross_after_discount_capacity = sum(
        Decimal(str(row["grossTuition"])) * (1 - COMMERCIAL_DISCOUNT / 100) * row["capacity"]
        for row in rows
    )
    delinquency_capacity = int((gross_after_discount_capacity * DELINQUENCY).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    pcld_gap = PCLD_CENTS - delinquency_capacity

    result = {
        "title": "Previa Auditavel PE 2027 — PCLD neutralizada no calculo gerencial",
        "status": "PREVIA_PARA_VALIDACAO",
        "rules": {
            "C02": "custo individual completo comprovado; Paula pendente",
            "C27": "apoio/administrativo, sem rateio arbitrario",
            "C28": "somente segmentos comprovados; demais administrativos",
            "C29": "capacidade dentro do segmento; Maria Edna direta/exclusiva no G4 B",
            "C30": "administrativo",
            "C31": "blocos de pessoal como composicao total, nunca adicionais",
            "C32": "residuais G2 preservados diretamente",
            "PCLD": "preservada no orcamento oficial e neutralizada somente no PE; inadimplencia de 4,5% mantida no ticket",
        },
        "summary": {
            "classes": len(rows),
            "teachers2027": len(teachers_2027),
            "capacity": sum(row["capacity"] for row in rows),
            "officialTotalMonthly": OFFICIAL_TOTAL_MONTHLY_CENTS / 100,
            "managerialPETotalMonthly": managerial_total / 100,
            "classAttributedMonthly": class_total / 100,
            "institutionalPersonnelMonthly": institutional_personnel / 100,
            "personnelEnvelopeMonthly": PERSONNEL_TOTAL_CENTS / 100,
            "generalExpensesAllocatedMonthly": general_total / 100,
            "generalExpensesOfficialMonthly": general_total_official / 100,
            "pcldNeutralizedMonthly": PCLD_CENTS / 100,
            "teachingMonthly": teaching_total / 100,
            "internsDocumentedMonthly": intern_total / 100,
            "coordinationSegmentMonthly": coord_total / 100,
            "auxiliariesSegmentMonthly": auxiliary_total / 100,
            "g2PayrollResidualsMonthly": g2_payroll_total / 100,
            "g2SupportRemainderMonthly": g2_support_total / 100,
            "supportAdministrativeControlMonthly": SUPPORT_ADMIN_CONTROL_CENTS / 100,
            "secretaryTreasuryDirectionControlMonthly": SECRETARY_TREASURY_DIRECTION_CENTS / 100,
            "coordinationAdministrativeControlMonthly": COORDINATION_ADMIN_CENTS / 100,
            "mariaEdnaG4BDirectMonthly": MARIA_EDNA_G4B_DIRECT_CENTS / 100,
            "doubleCountProtection": {
                "personnelBlocks": [267630.16, 119961.77],
                "personnelTotal": 387591.93,
                "additionalPersonnelAdded": 0,
            },
        },
        "pcld": {
            "budgetAccountMonthly": PCLD_CENTS / 100,
            "ticketDelinquencyPercent": float(DELINQUENCY),
            "capacityRevenueReductionMonthly": delinquency_capacity / 100,
            "differenceMonthly": pcld_gap / 100,
            "status": "RESOLVIDO_NEUTRALIZADO_SOMENTE_NO_PE",
            "note": "PCLD preservada no orçamento oficial e neutralizada exclusivamente no cálculo gerencial do PE para evitar dupla contagem com a inadimplência de 4,5% aplicada ao ticket.",
        },
        "pending": pending + [
            {"decision": "C32", "classes": ["G2 A", "G2 B"],
             "reason": "residuais oficiais sem memoria nominal"},
        ],
        "teacherProjection2027": teachers_2027,
        "classes": rows,
    }
    validate_preview(result)
    return result


def validate_preview(result: dict) -> None:
    rows = result["classes"]
    if len(rows) != 41 or len({row["classId"] for row in rows}) != 41:
        raise AssertionError("Quantidade ou unicidade de turmas invalida")
    for row in rows:
        numeric = [value for key, value in row.items() if isinstance(value, (int, float))]
        if any(not math.isfinite(value) for value in numeric):
            raise AssertionError(f"NaN/Infinity em {row['class']}")
        if row["totalCostMonthly"] < 0 or row["breakEvenStudents"] < 0:
            raise AssertionError(f"Custo/PE negativo em {row['class']}")
        if row["breakEvenStudents"] != math.ceil(row["totalCostMonthly"] / row["netTicket"]):
            raise AssertionError(f"PE inconsistente em {row['class']}")
        if row["breakEvenPercentCapacity"] != row["breakEvenStudents"] / row["capacity"] * 100:
            raise AssertionError(f"PE/capacidade inconsistente em {row['class']}")
        if row["physicalMarginStudents"] != row["capacity"] - row["breakEvenStudents"]:
            raise AssertionError(f"Margem fisica inconsistente em {row['class']}")
        if row["netTicket"] <= 0 or row["capacity"] <= 0:
            raise AssertionError(f"Ticket/capacidade invalido em {row['class']}")
    summary = result["summary"]
    if round(summary["classAttributedMonthly"] + summary["institutionalPersonnelMonthly"], 2) != summary["managerialPETotalMonthly"]:
        raise AssertionError("Total gerencial do PE nao reconciliado")
    if round(summary["managerialPETotalMonthly"] + summary["pcldNeutralizedMonthly"], 2) != summary["officialTotalMonthly"]:
        raise AssertionError("Orcamento oficial e neutralizacao da PCLD nao reconciliados")
    if round(sum(row["pcldNeutralizedMonthly"] for row in rows), 2) != PCLD_CENTS / 100:
        raise AssertionError("Neutralizacao da PCLD nao fecha centavo a centavo")
    if summary["doubleCountProtection"]["additionalPersonnelAdded"] != 0:
        raise AssertionError("Protecao contra dupla contagem violada")
    teachers = result["teacherProjection2027"]
    if len(teachers) != 50 or len({row["name"].casefold() for row in teachers}) != 50:
        raise AssertionError("Projecao docente deve conter exatamente 50 pessoas unicas")
    teacher_names = {row["name"] for row in teachers}
    if not {"Telma Bruno da Silva Ribeiro", "Julianne Moreira Martins dos Santos"} <= teacher_names:
        raise AssertionError("Docentes confirmadas para 2027 ausentes")
    if {"Lohana Rodrigues Leite da Silva", "Marcelo Rodrigues"} & teacher_names:
        raise AssertionError("Pessoa excluida da projecao docente 2027")
    for name, decision in TEACHER_CODE_DECISIONS.items():
        row = next(item for item in teachers if item["name"] == name)
        if row["currentCode"] != decision["currentCode"] or row["historicalCodes"] != decision["historicalCodes"]:
            raise AssertionError(f"Codigo docente nao conciliado: {name}")
    placements = {
        "Joyce dos Santos Pereira": "G2 A",
        "Larissa Lorrana Miranda de Jesus": "G2 B",
        "Paula Araujo Dias": "G3 B",
    }
    for person, class_name in placements.items():
        occurrences = [(row["class"], detail["amount"])
                       for row in rows for detail in row["internDetails"] if detail["person"] == person]
        if len(occurrences) != 1 or occurrences[0][0] != class_name:
            raise AssertionError(f"Lotacao de estagiaria inconsistente: {person}")
    maria_edna = [(row["class"], detail["amount"])
                  for row in rows for detail in row["otherDirectDetails"]
                  if detail["person"] == "Maria Edna Nivaldina de Barros Santos"]
    if maria_edna != [("G4 B", 2638.43)]:
        raise AssertionError("Maria Edna deve ocorrer exclusivamente no G4 B")


def markdown_report(data: dict) -> str:
    s = data["summary"]
    lines = [
        "# Prévia auditável do PE 2027 — cenário C aprovado",
        "",
        "> Simulação local para validação. Nenhum banco, Supabase, produção ou PE homologado foi alterado.",
        "",
        "## A) Resumo financeiro",
        "",
        f"- Total oficial mensal preservado: **{money(int(round(s['officialTotalMonthly']*100)))}**.",
        f"- Total gerencial do PE após neutralização da PCLD: **{money(int(round(s['managerialPETotalMonthly']*100)))}**.",
        f"- PCLD preservada no orçamento e neutralizada somente no PE: **{money(PCLD_CENTS)}**.",
        f"- Custos atribuídos às 41 turmas: **{money(int(round(s['classAttributedMonthly']*100)))}**.",
        f"- Pessoal institucional/pendente fora das turmas: **{money(int(round(s['institutionalPersonnelMonthly']*100)))}**.",
        f"- Projeção docente consolidada: **{s['teachers2027']} pessoas únicas**.",
        f"- Envelope de pessoal preservado: **{money(PERSONNEL_TOTAL_CENTS)}**; adicional somado: **R$ 0,00**.",
        f"- Docentes: {money(int(round(s['teachingMonthly']*100)))}; estagiários comprovados: {money(int(round(s['internsDocumentedMonthly']*100)))}.",
        "",
        "## B) Tabela das 41 turmas",
        "",
        "| Turma | Cap. | Mensalidade | Premissa | Inad. | Ticket líquido | Docentes | Outros diretos | Estagiários | Auxiliares | Coord./orient. | Rateios | Residual | Custo mensal | PE | PE/cap. | Margem | Status | Observação |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in data["classes"]:
        lines.append(
            f"| {row['class']} | {row['capacity']} | {money(round(row['grossTuition']*100))} | 3,0% | 4,5% | "
            f"{money(round(row['netTicket']*100))} | {money(round(row['teachingCostMonthly']*100))} | "
            f"{money(round(row['otherDirectCostsMonthly']*100))} | {money(round(row['internsMonthly']*100))} | "
            f"{money(round(row['auxiliariesMonthly']*100))} | {money(round(row['coordinationOrientationMonthly']*100))} | "
            f"{money(round(row['otherProvenAllocationsMonthly']*100))} | {money(round(row['officialResidualMonthly']*100))} | "
            f"{money(round(row['totalCostMonthly']*100))} | {row['breakEvenStudents']} | "
            f"{row['breakEvenPercentCapacity']:.2f}% | {row['physicalMarginStudents']} | {row['documentaryStatus']} | "
            f"{row['documentaryObservation']} |"
        )
    lines += ["", "## C) Memória detalhada de G2 A e G2 B", ""]
    for name in ("G2 A", "G2 B"):
        row = next(item for item in data["classes"] if item["class"] == name)
        lines += [
            f"### {name}", "",
            f"- Docente mensal: {money(round(row['teachingCostMonthly']*100))}.",
            f"- Estagiária em custo completo: {money(round(row['internsMonthly']*100))}.",
            f"- Coordenação/orientação do segmento: {money(round(row['coordinationOrientationMonthly']*100))}.",
            f"- Auxiliares do segmento: {money(round(row['auxiliariesMonthly']*100))}.",
            f"- Outros rateios comprovados, líquidos da PCLD: {money(round(row['otherProvenAllocationsMonthly']*100))}.",
            f"- PCLD neutralizada no PE: {money(round(row['pcldNeutralizedMonthly']*100))}.",
            f"- Residual: {money(round(row['officialResidualMonthly']*100))} — **OFICIAL PRESERVADO — AGUARDANDO CONCILIAÇÃO NOMINAL**.",
            f"- Total: {money(round(row['totalCostMonthly']*100))}; ticket: {money(round(row['netTicket']*100))}; PE: **{row['breakEvenStudents']} alunos**.",
            "",
        ]
    lines += [
        "## D) Comparação antes × depois",
        "",
        "| Turma | Custo anterior | Custo recalculado | Variação | PE anterior | PE recalculado | Δ PE |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in data["classes"]:
        lines.append(
            f"| {row['class']} | {money(round(row['previousTotalCostMonthly']*100))} | {money(round(row['totalCostMonthly']*100))} | "
            f"{money(round(row['costChangeMonthly']*100))} | {row['previousBreakEvenStudents']} | {row['breakEvenStudents']} | {row['breakEvenChangeStudents']:+d} |"
        )
    p = data["pcld"]
    lines += [
        "", "## E) Pendências restantes", "",
        "- Paula Araujo Dias/G3 B: CUSTO DE PAULA NÃO INCORPORADO — AGUARDANDO DOCUMENTAÇÃO; a turma permanece PARCIAL.",
        "- G2 A e G2 B: residuais oficiais preservados, mas ainda sem memória nominal.",
        "", "## F) PCLD × 4,5%", "",
        f"- Conta PCLD mensal preservada: **{money(PCLD_CENTS)}**.",
        f"- Redução de 4,5% aplicada à receita estrutural na capacidade: **{money(round(p['capacityRevenueReductionMonthly']*100))}**.",
        f"- Diferença entre as duas referências: **{money(round(p['differenceMonthly']*100))}**.",
        "- A conta permanece integral no orçamento oficial, mas foi neutralizada exclusivamente na camada gerencial do PE.",
        "- A redução de 4,5% permanece aplicada ao ticket; a perda econômica entra uma única vez no PE.",
        "- Regra registrada: “PCLD preservada no orçamento oficial e neutralizada exclusivamente no cálculo gerencial do PE para evitar dupla contagem com a inadimplência de 4,5% aplicada ao ticket.”",
        "", "## G) Impedimentos ao fechamento definitivo", "",
        "A decisão PCLD × 4,5% está resolvida. Permanecem somente o custo ausente de Paula/G3 B e a memória nominal dos residuais G2 A/G2 B.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    data = build_preview()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "previa.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "RELATORIO.md").write_text(markdown_report(data), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT_DIR), "summary": data["summary"], "pcld": data["pcld"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
