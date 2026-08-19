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


def set_origin(con: sqlite3.Connection, table: str, pid: int, origin: str) -> None:
    if not table_exists(con, table):
        return
    cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    if "origin" in cols:
        con.execute(f"UPDATE {table} SET origin=? WHERE product_id=?", (origin, pid))


def normalize_proposal_provenance(con: sqlite3.Connection) -> None:
    # The deterministic classifier and type policies are useful proposals, but they are
    # not manual/model review. Remove historical naming that could overstate provenance.
    for table in (
        "culinary_types", "nutritional_role_assignments", "culinary_role_assignments",
        "food_family_assignments", "portion_basis",
    ):
        if not table_exists(con, table):
            continue
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if "origin" in cols:
            con.execute(
                f"UPDATE {table} SET origin='AUTOMATIC_PROPOSAL' "
                "WHERE origin IN ('AUTOMATIC','MANUAL_POLICY')"
            )
    if table_exists(con, "manual_classification_audit"):
        # Entries produced by deterministic rules are not manual reviews. Semantic review
        # is recorded separately in semantic_model_reviews with the full model decision.
        con.execute("DELETE FROM manual_classification_audit")


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
    # MENU_ELIGIBLE until a persisted semantic model review accepts that proposal.
    con.execute(
        "UPDATE eligibility SET classified=0,menu_eligible=0,reason="
        "CASE WHEN nutritionally_usable=1 THEN 'Pendiente de revisión semántica por el modelo' ELSE reason END"
    )

    now = datetime.now(timezone.utc).isoformat()
    accepted = review = excluded = stale = 0
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
        con.execute(
            "INSERT OR REPLACE INTO semantic_model_reviews VALUES(?,?,?,?,?,?,?,?,?)",
            (pid, sku, decision, int(accepts), reason,
             json.dumps(corrections, ensure_ascii=False) if corrections is not None else None,
             review_version, reviewed_at, json.dumps(row, ensure_ascii=False)),
        )

        if decision == "ACCEPT" and accepts and nutrition_ok:
            # Corrections require an explicit structured applier. ACCEPT is therefore
            # eligibility-bearing only when the persisted decision accepts the proposal.
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
                con.execute("UPDATE review_queue SET status='MODEL_ACCEPTED' WHERE product_id=? AND status='OPEN'", (pid,))
            accepted += 1
        elif decision == "EXCLUDE":
            con.execute(
                "UPDATE eligibility SET classified=0,menu_eligible=0,reason=? WHERE product_id=?",
                (f"Excluido tras revisión semántica: {reason}", pid),
            )
            excluded += 1
        else:
            con.execute(
                "UPDATE eligibility SET classified=0,menu_eligible=0,reason=? WHERE product_id=?",
                (f"Revisión semántica pendiente: {reason}", pid),
            )
            review += 1

    for key, value in {
        "classification_policy_version": PROPOSAL_POLICY + "+" + REVIEW_VERSION,
        "automatic_proposal_policy": PROPOSAL_POLICY,
        "semantic_review_policy": REVIEW_VERSION,
        "semantic_reviews_loaded": str(len(reviews)),
        "semantic_reviews_accepted": str(accepted),
        "classification_claim_policy": "AUTOMATIC_PROPOSAL_IS_NOT_CLASSIFIED_UNTIL_MODEL_SEMANTIC_REVIEW",
    }.items():
        con.execute("INSERT OR REPLACE INTO catalog_metadata(key,value) VALUES(?,?)", (key, value))
    con.commit()

    report = {
        "reviews_loaded": len(reviews),
        "accepted_menu_eligible": accepted,
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
