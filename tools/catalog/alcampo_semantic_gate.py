#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REVIEW_VERSION = "alcampo-semantic-review-v1"
PROPOSAL_POLICY = "alcampo-automatic-proposal-2026-08-20.v1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS semantic_model_reviews(
  product_id INTEGER PRIMARY KEY,
  sku TEXT NOT NULL,
  decision TEXT NOT NULL,
  accepts_proposal INTEGER NOT NULL,
  reason TEXT NOT NULL,
  corrections_json TEXT,
  review_version TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  raw_review_json TEXT NOT NULL
);
"""

VALID_NUTRITIONAL_ROLES = {
    "PRIMARY_PROTEIN", "COMPLEMENTARY_PROTEIN",
    "PRIMARY_CARBOHYDRATE", "COMPLEMENTARY_CARBOHYDRATE",
    "CONCENTRATED_FAT", "COMPLEMENTARY_FAT", "VEGETABLE", "FRUIT",
}


def load_reviews(path: Path | None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not path or not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        sku = str(row.get("sku") or "").strip()
        decision = str(row.get("decision") or "").upper().strip()
        if sku and decision in {"ACCEPT", "REVIEW", "EXCLUDE"}:
            out[sku] = row
    return out


def table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def table_columns(con: sqlite3.Connection, name: str) -> set[str]:
    if not table_exists(con, name):
        return set()
    return {str(r[1]) for r in con.execute(f"PRAGMA table_info({name})")}


def set_origin(con: sqlite3.Connection, table: str, pid: int, origin: str) -> None:
    if "origin" in table_columns(con, table):
        con.execute(f"UPDATE {table} SET origin=? WHERE product_id=?", (origin, pid))


def normalize_proposal_provenance(con: sqlite3.Connection) -> None:
    # Deterministic classifier/type policies are proposals, not manual/model review.
    for table in (
        "culinary_types", "nutritional_role_assignments", "culinary_role_assignments",
        "food_family_assignments", "portion_basis",
    ):
        cols = table_columns(con, table)
        if not cols:
            continue
        if "policy_version" in cols:
            con.execute(
                f"UPDATE {table} SET policy_version=? WHERE policy_version LIKE 'alcampo-manual-policy-%'",
                (PROPOSAL_POLICY,),
            )
        if "origin" in cols:
            con.execute(
                f"UPDATE {table} SET origin='AUTOMATIC_PROPOSAL' "
                "WHERE origin IN ('AUTOMATIC','MANUAL_POLICY')"
            )
    if table_exists(con, "manual_classification_audit"):
        # Historical deterministic-policy entries are not manual reviews. The real model
        # decisions live in semantic_model_reviews with their full evidence and rationale.
        con.execute("DELETE FROM manual_classification_audit")


def _correction_evidence(sku: str, reason: str, review_version: str) -> str:
    return json.dumps({
        "sku": sku,
        "semantic_reason": reason,
        "review_version": review_version,
        "source": "MODEL_SEMANTIC_REVIEW",
    }, ensure_ascii=False)


def apply_corrections(con: sqlite3.Connection, pid: int, sku: str, corrections: dict, reason: str, review_version: str, reviewed_at: str) -> list[str]:
    """Apply only explicitly supplied, schema-safe semantic corrections.

    Missing keys mean "keep the automatic proposal". A present empty role list means
    "this product has no role of that dimension". Invalid correction values are ignored
    and leave the product gated for REVIEW by the caller.
    """
    applied: list[str] = []
    evidence = _correction_evidence(sku, reason, review_version)

    if "nutritional_roles" in corrections and table_exists(con, "nutritional_role_assignments"):
        raw = corrections.get("nutritional_roles")
        if isinstance(raw, list):
            roles = [str(x).strip().upper() for x in raw if str(x).strip()]
            if all(r in VALID_NUTRITIONAL_ROLES for r in roles):
                con.execute("DELETE FROM nutritional_role_assignments WHERE product_id=?", (pid,))
                for role in dict.fromkeys(roles):
                    con.execute(
                        "INSERT INTO nutritional_role_assignments(product_id,role,confidence,rule_id,evidence_json,classifier_version,origin) VALUES(?,?,?,?,?,?,?)",
                        (pid, role, 1.0, "model.semantic.correction", evidence, review_version, "MODEL_SEMANTIC_REVIEW"),
                    )
                applied.append("nutritional_roles")

    if "culinary_roles" in corrections and table_exists(con, "culinary_role_assignments"):
        raw = corrections.get("culinary_roles")
        if isinstance(raw, list):
            roles = [str(x).strip().upper() for x in raw if str(x).strip()]
            # Culinary-role vocabulary evolves in Rumbo; semantic correction may use
            # any non-empty canonical token already reviewed by the model.
            if all(role.replace("_", "").isalnum() for role in roles):
                con.execute("DELETE FROM culinary_role_assignments WHERE product_id=?", (pid,))
                for role in dict.fromkeys(roles):
                    con.execute(
                        "INSERT INTO culinary_role_assignments(product_id,role,confidence,rule_id,evidence_json,classifier_version,origin) VALUES(?,?,?,?,?,?,?)",
                        (pid, role, 1.0, "model.semantic.correction", evidence, review_version, "MODEL_SEMANTIC_REVIEW"),
                    )
                applied.append("culinary_roles")

    if "food_family" in corrections and table_exists(con, "food_family_assignments"):
        raw = corrections.get("food_family")
        con.execute("DELETE FROM food_family_assignments WHERE product_id=?", (pid,))
        if raw is None or str(raw).strip() == "":
            applied.append("food_family")
        else:
            family = str(raw).strip().upper()
            if family.replace("_", "").isalnum():
                con.execute(
                    "INSERT INTO food_family_assignments(product_id,food_family,confidence,rule_id,evidence_json,policy_version,origin,reviewed_at) VALUES(?,?,?,?,?,?,?,?)",
                    (pid, family, 1.0, "model.semantic.correction", evidence, review_version, "MODEL_SEMANTIC_REVIEW", reviewed_at),
                )
                applied.append("food_family")

    if "portion_basis_grams" in corrections and table_exists(con, "portion_basis"):
        try:
            grams = float(corrections.get("portion_basis_grams"))
        except (TypeError, ValueError):
            grams = 0.0
        if 0 < grams <= 5000:
            state = str(corrections.get("material_state") or "AS_SOLD").strip().upper()
            if not state.replace("_", "").isalnum():
                state = "AS_SOLD"
            con.execute("DELETE FROM portion_basis WHERE product_id=?", (pid,))
            con.execute(
                "INSERT INTO portion_basis(product_id,portion_basis_grams,material_state,confidence,rule_id,evidence_json,policy_version,origin,reviewed_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (pid, grams, state, 1.0, "model.semantic.correction", evidence, review_version, "MODEL_SEMANTIC_REVIEW", reviewed_at),
            )
            applied.append("portion_basis_grams")

    # culinary_type is retained only as an internal migration implementation detail,
    # never as the canonical Rumbo semantic model. Accept it only when explicitly
    # supplied to repair an existing classifier proposal.
    if "culinary_type_internal" in corrections and table_exists(con, "culinary_types"):
        ctype = str(corrections.get("culinary_type_internal") or "").strip().upper()
        if ctype and ctype.replace("_", "").isalnum():
            con.execute("DELETE FROM culinary_types WHERE product_id=?", (pid,))
            con.execute(
                "INSERT INTO culinary_types(product_id,culinary_type,confidence,rule_id,evidence_json,classifier_version,origin) VALUES(?,?,?,?,?,?,?)",
                (pid, ctype, 1.0, "model.semantic.correction", evidence, review_version, "MODEL_SEMANTIC_REVIEW"),
            )
            applied.append("culinary_type_internal")

    return applied


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("database", type=Path)
    p.add_argument("--reviews", type=Path)
    a = p.parse_args()

    reviews = load_reviews(a.reviews)
    con = sqlite3.connect(a.database)
    con.executescript(SCHEMA)
    con.execute("DELETE FROM semantic_model_reviews")
    normalize_proposal_provenance(con)

    # Automatic classification is a proposal only. Nothing becomes CLASSIFIED or
    # MENU_ELIGIBLE until a persisted semantic model review accepts it or explicitly
    # accepts a corrected semantic assignment.
    con.execute(
        "UPDATE eligibility SET classified=0,menu_eligible=0,reason="
        "CASE WHEN nutritionally_usable=1 THEN 'Pendiente de revisión semántica por el modelo' ELSE reason END"
    )

    now = datetime.now(timezone.utc).isoformat()
    accepted = review = excluded = stale = corrected = 0
    listing_rows = con.execute(
        "SELECT rl.retailer_sku,rl.product_id,e.nutritionally_usable "
        "FROM retailer_listings rl JOIN eligibility e ON e.product_id=rl.product_id "
        "WHERE rl.retailer='Alcampo'"
    ).fetchall()
    by_sku = {str(sku): (int(pid), bool(nut_ok)) for sku, pid, nut_ok in listing_rows}

    for sku, row in reviews.items():
        target = by_sku.get(sku)
        if not target:
            stale += 1
            continue
        pid, nutrition_ok = target
        decision = str(row.get("decision") or "").upper().strip()
        accepts = bool(row.get("accepts_proposal"))
        reason = str(row.get("reason") or "").strip() or "Sin justificación registrada"
        corrections = row.get("corrections")
        review_version = str(row.get("review_version") or REVIEW_VERSION)
        reviewed_at = str(row.get("reviewed_at") or now)
        applied: list[str] = []
        if decision == "ACCEPT" and isinstance(corrections, dict) and corrections:
            applied = apply_corrections(con, pid, sku, corrections, reason, review_version, reviewed_at)
            corrected += int(bool(applied))

        con.execute(
            "INSERT OR REPLACE INTO semantic_model_reviews VALUES(?,?,?,?,?,?,?,?,?)",
            (pid, sku, decision, int(accepts), reason,
             json.dumps(corrections, ensure_ascii=False) if corrections is not None else None,
             review_version, reviewed_at, json.dumps(row, ensure_ascii=False)),
        )

        semantically_accepted = decision == "ACCEPT" and (accepts or bool(applied))
        if semantically_accepted and nutrition_ok:
            con.execute(
                "UPDATE eligibility SET classified=1,menu_eligible=1,reason=NULL WHERE product_id=?",
                (pid,),
            )
            for table in (
                "culinary_types", "nutritional_role_assignments", "culinary_role_assignments",
                "food_family_assignments", "portion_basis",
            ):
                set_origin(con, table, pid, "MODEL_SEMANTIC_REVIEW")
            if table_exists(con, "review_queue"):
                status = "MODEL_CORRECTED" if applied else "MODEL_ACCEPTED"
                con.execute("UPDATE review_queue SET status=? WHERE product_id=? AND status='OPEN'", (status, pid))
            accepted += 1
        elif decision == "EXCLUDE":
            con.execute(
                "UPDATE eligibility SET classified=0,menu_eligible=0,reason=? WHERE product_id=?",
                (f"Excluido tras revisión semántica: {reason}", pid),
            )
            excluded += 1
        else:
            detail = ""
            if decision == "ACCEPT" and not nutrition_ok:
                detail = " (clasificación aceptada, pero falta nutrición válida)"
            elif decision == "ACCEPT" and corrections and not applied and not accepts:
                detail = " (correcciones no válidas o insuficientes)"
            con.execute(
                "UPDATE eligibility SET classified=0,menu_eligible=0,reason=? WHERE product_id=?",
                (f"Revisión semántica pendiente: {reason}{detail}", pid),
            )
            review += 1

    for key, value in {
        "classification_policy_version": PROPOSAL_POLICY + "+" + REVIEW_VERSION,
        "automatic_proposal_policy": PROPOSAL_POLICY,
        "semantic_review_policy": REVIEW_VERSION,
        "semantic_reviews_loaded": str(len(reviews)),
        "semantic_reviews_accepted": str(accepted),
        "semantic_reviews_corrected": str(corrected),
        "classification_claim_policy": "AUTOMATIC_PROPOSAL_IS_NOT_CLASSIFIED_UNTIL_MODEL_SEMANTIC_REVIEW",
    }.items():
        con.execute("INSERT OR REPLACE INTO catalog_metadata(key,value) VALUES(?,?)", (key, value))
    con.commit()

    report = {
        "reviews_loaded": len(reviews),
        "accepted_menu_eligible": accepted,
        "accepted_with_corrections": corrected,
        "review": review,
        "excluded": excluded,
        "stale_reviews": stale,
        "nutritionally_usable": con.execute("SELECT count(*) FROM eligibility WHERE nutritionally_usable=1").fetchone()[0],
        "classified_after_semantic_gate": con.execute("SELECT count(*) FROM eligibility WHERE classified=1").fetchone()[0],
        "menu_eligible_after_semantic_gate": con.execute("SELECT count(*) FROM eligibility WHERE menu_eligible=1").fetchone()[0],
        "semantic_review_required": True,
        "automatic_proposals_are_not_manual": True,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
