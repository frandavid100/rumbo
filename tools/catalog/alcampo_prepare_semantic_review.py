#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

REVIEW_VERSION = "alcampo-semantic-review-v1"


def load_reviewed(path: Path | None) -> set[str]:
    reviewed: set[str] = set()
    if not path or not path.exists():
        return reviewed
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        sku = row.get("sku")
        if sku is not None and row.get("decision") in {"ACCEPT", "REVIEW", "EXCLUDE"}:
            reviewed.add(str(sku))
    return reviewed


def list_values(con: sqlite3.Connection, table: str, pid: int, column: str) -> list[str]:
    return [str(r[0]) for r in con.execute(f"SELECT {column} FROM {table} WHERE product_id=? ORDER BY {column}", (pid,))]


def one_value(con: sqlite3.Connection, table: str, pid: int, column: str):
    row = con.execute(f"SELECT {column} FROM {table} WHERE product_id=?", (pid,)).fetchone()
    return row[0] if row else None


def open_reasons(con: sqlite3.Connection, pid: int) -> list[str]:
    return [str(r[0]) for r in con.execute("SELECT reason FROM review_queue WHERE product_id=? AND status='OPEN' ORDER BY reason", (pid,))]


def run(db_path: Path, reviews_path: Path | None, output: Path, limit: int, progress_path: Path | None):
    reviewed = load_reviewed(reviews_path)
    con = sqlite3.connect(db_path)
    rows = con.execute("""
        SELECT p.id,p.canonical_name,p.legal_name,p.ingredients,
               rl.retailer_sku,rl.brand,rl.pack_size,
               n.calories,n.protein_g,n.carbohydrate_g,n.fat_g,n.fiber_g,n.salt_g,
               e.nutritionally_usable,e.classified,e.menu_eligible,e.reason
        FROM products p
        JOIN retailer_listings rl ON rl.product_id=p.id AND rl.retailer='Alcampo'
        LEFT JOIN nutrition n ON n.product_id=p.id
        LEFT JOIN eligibility e ON e.product_id=p.id
        WHERE e.nutritionally_usable=1
        ORDER BY COALESCE(rl.retailer_sku,''),p.canonical_name
    """).fetchall()

    candidates=[]
    for pid,name,legal,ingredients,sku,brand,pack,kcal,protein,carbs,fat,fiber,salt,nut_ok,classified,menu_eligible,reason in rows:
        sku=str(sku or "")
        if not sku or sku in reviewed:
            continue
        candidate={
            "review_version":REVIEW_VERSION,
            "product_id":pid,
            "sku":sku,
            "name":name,
            "brand":brand,
            "pack_size":pack,
            "legal_name":legal,
            "ingredients":(ingredients[:1600] if isinstance(ingredients,str) else ingredients),
            "nutrition":{"kcal":kcal,"protein_g":protein,"carbohydrate_g":carbs,"fat_g":fat,"fiber_g":fiber,"salt_g":salt},
            "source_category":one_value(con,"source_taxonomy",pid,"retailer_category") if _table_exists(con,"source_taxonomy") else None,
            "proposal":{
                "culinary_type_internal":one_value(con,"culinary_types",pid,"culinary_type"),
                "nutritional_roles":list_values(con,"nutritional_role_assignments",pid,"role"),
                "culinary_roles":list_values(con,"culinary_role_assignments",pid,"role"),
                "food_family":one_value(con,"food_family_assignments",pid,"food_family") if _table_exists(con,"food_family_assignments") else None,
                "portion_basis_grams":one_value(con,"portion_basis",pid,"portion_basis_grams") if _table_exists(con,"portion_basis") else None,
                "open_review_reasons":open_reasons(con,pid),
                "automated_classified":bool(classified),
                "automated_menu_eligible":bool(menu_eligible),
                "eligibility_reason":reason,
            },
            "required_model_output":{
                "decision":"ACCEPT | REVIEW | EXCLUDE",
                "reason":"short semantic justification",
                "accepts_proposal":"boolean",
                "corrections":"optional structured corrections when proposal is not accepted",
            },
        }
        candidates.append(candidate)
        if limit and len(candidates)>=limit:
            break

    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8") as f:
        for row in candidates:
            f.write(json.dumps(row,ensure_ascii=False)+"\n")

    total_usable=len(rows)
    progress={
        "review_version":REVIEW_VERSION,
        "nutritionally_usable_products":total_usable,
        "semantically_reviewed_skus":sum(1 for r in rows if str(r[4] or "") in reviewed),
        "remaining_semantic_review":sum(1 for r in rows if str(r[4] or "") and str(r[4]) not in reviewed),
        "batch_size":len(candidates),
        "batch_path":str(output),
    }
    if progress_path:
        progress_path.parent.mkdir(parents=True,exist_ok=True)
        progress_path.write_text(json.dumps(progress,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(progress,ensure_ascii=False,indent=2))
    con.close()


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("database",type=Path)
    p.add_argument("--reviews",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--progress",type=Path)
    p.add_argument("--limit",type=int,default=300)
    a=p.parse_args()
    run(a.database,a.reviews,a.output,a.limit,a.progress)
