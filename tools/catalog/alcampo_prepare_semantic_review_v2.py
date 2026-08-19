#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

REVIEW_VERSION = "alcampo-semantic-review-v1"


def load_reviewed(path: Path | None) -> set[str]:
    out: set[str] = set()
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
        if sku and str(row.get("decision") or "").upper() in {"ACCEPT", "REVIEW", "EXCLUDE"}:
            out.add(sku)
    return out


def load_observations(path: Path | None) -> dict[str, dict]:
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
        if sku:
            out[sku] = row
    return out


def table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def values(con: sqlite3.Connection, table: str, pid: int, column: str) -> list[str]:
    if not table_exists(con, table):
        return []
    return [str(r[0]) for r in con.execute(f"SELECT {column} FROM {table} WHERE product_id=? ORDER BY {column}", (pid,))]


def value(con: sqlite3.Connection, table: str, pid: int, column: str):
    if not table_exists(con, table):
        return None
    row = con.execute(f"SELECT {column} FROM {table} WHERE product_id=?", (pid,)).fetchone()
    return row[0] if row else None


def open_reasons(con: sqlite3.Connection, pid: int) -> list[str]:
    if not table_exists(con, "review_queue"):
        return []
    return [str(r[0]) for r in con.execute(
        "SELECT reason FROM review_queue WHERE product_id=? AND status='OPEN' ORDER BY reason", (pid,)
    )]


def run(db: Path, observations: Path | None, reviews: Path | None, output: Path, progress: Path | None, limit: int) -> None:
    reviewed = load_reviewed(reviews)
    obs = load_observations(observations)
    con = sqlite3.connect(db)
    rows = con.execute("""
      SELECT p.id,p.canonical_name,p.brand,p.legal_name,p.ingredients,
             rl.retailer_sku,
             n.calories,n.protein_g,n.carbohydrate_g,n.fat_g,n.fiber_g,n.salt_g,
             e.nutritionally_usable,e.classified,e.menu_eligible,e.reason
      FROM products p
      JOIN retailer_listings rl ON rl.product_id=p.id AND rl.retailer='Alcampo'
      LEFT JOIN nutrition n ON n.product_id=p.id
      JOIN eligibility e ON e.product_id=p.id
      WHERE e.nutritionally_usable=1
      ORDER BY COALESCE(rl.retailer_sku,''),p.canonical_name
    """).fetchall()

    candidates: list[dict] = []
    for pid,name,brand,legal,ingredients,sku,kcal,protein,carbs,fat,fiber,salt,nut_ok,classified,menu_eligible,reason in rows:
        sku = str(sku or "")
        if not sku or sku in reviewed:
            continue
        o = obs.get(sku, {})
        candidate = {
            "review_version": REVIEW_VERSION,
            "product_id": pid,
            "sku": sku,
            "name": name,
            "brand": brand,
            "pack_size": o.get("pack_size"),
            "legal_name": legal,
            "ingredients": ingredients[:2400] if isinstance(ingredients, str) else ingredients,
            "nutrition": {
                "kcal": kcal, "protein_g": protein, "carbohydrate_g": carbs,
                "fat_g": fat, "fiber_g": fiber, "salt_g": salt,
            },
            "source_category": value(con, "source_taxonomy", pid, "retailer_category"),
            "proposal": {
                "culinary_type_internal": value(con, "culinary_types", pid, "culinary_type"),
                "nutritional_roles": values(con, "nutritional_role_assignments", pid, "role"),
                "culinary_roles": values(con, "culinary_role_assignments", pid, "role"),
                "food_family": value(con, "food_family_assignments", pid, "food_family"),
                "portion_basis_grams": value(con, "portion_basis", pid, "portion_basis_grams"),
                "open_review_reasons": open_reasons(con, pid),
                "automatic_proposal_only": True,
            },
            "required_model_output": {
                "decision": "ACCEPT | REVIEW | EXCLUDE",
                "reason": "short semantic justification",
                "accepts_proposal": "boolean",
                "corrections": "optional structured corrections",
            },
        }
        candidates.append(candidate)
        if limit and len(candidates) >= limit:
            break

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for row in candidates:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    usable_skus = [str(r[5] or "") for r in rows if str(r[5] or "")]
    report = {
        "review_version": REVIEW_VERSION,
        "nutritionally_usable_products": len(rows),
        "semantically_reviewed_skus": sum(s in reviewed for s in usable_skus),
        "remaining_semantic_review": sum(s not in reviewed for s in usable_skus),
        "batch_size": len(candidates),
        "batch_path": str(output),
        "automatic_proposals_are_not_classified": True,
    }
    if progress:
        progress.parent.mkdir(parents=True, exist_ok=True)
        progress.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    con.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("database", type=Path)
    p.add_argument("--observations", type=Path)
    p.add_argument("--reviews", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--progress", type=Path)
    p.add_argument("--limit", type=int, default=500)
    a = p.parse_args()
    run(a.database, a.observations, a.reviews, a.output, a.progress, a.limit)
