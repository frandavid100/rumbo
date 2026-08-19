from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("database", type=Path)
    p.add_argument("--jsonl", type=Path, required=True)
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--detail-summary", type=Path)
    p.add_argument("--enumeration-report", type=Path)
    a = p.parse_args()

    con = sqlite3.connect(a.database)
    rows = con.execute("""
      SELECT p.id,p.gtin,p.canonical_name,p.brand,p.legal_name,p.ingredients,
             rl.retailer_sku,rl.url,rl.availability,
             n.basis,n.calories,n.protein_g,n.carbohydrate_g,n.fat_g,n.fiber_g,n.salt_g,n.evidence_level,
             e.discoverable,e.identified,e.nutritionally_usable,e.classified,e.menu_eligible,e.reason,
             ct.culinary_type,ct.confidence,
             ff.food_family,pb.portion_basis_grams,pb.material_state
      FROM products p
      JOIN retailer_listings rl ON rl.product_id=p.id AND rl.retailer='Alcampo'
      LEFT JOIN nutrition n ON n.product_id=p.id
      JOIN eligibility e ON e.product_id=p.id
      LEFT JOIN culinary_types ct ON ct.product_id=p.id
      LEFT JOIN food_family_assignments ff ON ff.product_id=p.id
      LEFT JOIN portion_basis pb ON pb.product_id=p.id
      ORDER BY rl.retailer_sku
    """).fetchall()
    columns = [d[0] for d in con.execute("SELECT p.id,p.gtin,p.canonical_name,p.brand,p.legal_name,p.ingredients,rl.retailer_sku,rl.url,rl.availability,n.basis,n.calories,n.protein_g,n.carbohydrate_g,n.fat_g,n.fiber_g,n.salt_g,n.evidence_level,e.discoverable,e.identified,e.nutritionally_usable,e.classified,e.menu_eligible,e.reason,ct.culinary_type,ct.confidence,ff.food_family,pb.portion_basis_grams,pb.material_state FROM products p JOIN retailer_listings rl ON rl.product_id=p.id LEFT JOIN nutrition n ON n.product_id=p.id JOIN eligibility e ON e.product_id=p.id LEFT JOIN culinary_types ct ON ct.product_id=p.id LEFT JOIN food_family_assignments ff ON ff.product_id=p.id LEFT JOIN portion_basis pb ON pb.product_id=p.id LIMIT 0").description]

    role_rows = con.execute("SELECT product_id,role FROM nutritional_role_assignments ORDER BY product_id,role").fetchall()
    crole_rows = con.execute("SELECT product_id,role FROM culinary_role_assignments ORDER BY product_id,role").fetchall()
    nroles: dict[int,list[str]] = {}
    croles: dict[int,list[str]] = {}
    for pid, role in role_rows: nroles.setdefault(pid, []).append(role)
    for pid, role in crole_rows: croles.setdefault(pid, []).append(role)

    a.jsonl.parent.mkdir(parents=True, exist_ok=True)
    with a.jsonl.open("w", encoding="utf-8") as f:
        for vals in rows:
            row = dict(zip(columns, vals))
            pid = row.pop("id")
            row["nutritional_roles"] = nroles.get(pid, [])
            row["culinary_roles"] = croles.get(pid, [])
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    products = len(rows)
    counts = {
        "products_discovered": products,
        "identified": con.execute("SELECT count(*) FROM eligibility WHERE identified=1").fetchone()[0],
        "nutrition_valid": con.execute("SELECT count(*) FROM eligibility WHERE nutritionally_usable=1").fetchone()[0],
        "classified": con.execute("SELECT count(*) FROM eligibility WHERE classified=1").fetchone()[0],
        "menu_eligible": con.execute("SELECT count(*) FROM eligibility WHERE menu_eligible=1").fetchone()[0],
        "review_open": con.execute("SELECT count(DISTINCT product_id) FROM review_queue WHERE status='OPEN'").fetchone()[0],
        "review_reasons": con.execute("SELECT count(*) FROM review_queue WHERE status='OPEN'").fetchone()[0],
        "food_family_assigned": con.execute("SELECT count(*) FROM food_family_assignments").fetchone()[0],
        "portion_basis_assigned": con.execute("SELECT count(*) FROM portion_basis").fetchone()[0],
        "nutritional_role_assignments": con.execute("SELECT count(*) FROM nutritional_role_assignments").fetchone()[0],
        "culinary_role_assignments": con.execute("SELECT count(*) FROM culinary_role_assignments").fetchone()[0],
    }
    reason_counts = Counter(r[0] or "OK" for r in con.execute("SELECT reason FROM eligibility"))
    review_counts = Counter(r[0] for r in con.execute("SELECT reason FROM review_queue WHERE status='OPEN'"))
    metadata = dict(con.execute("SELECT key,value FROM catalog_metadata"))
    summary = {
        "retailer": "ALCAMPO",
        "source_policy": "FIRST_PARTY_ALCAMPO_ONLY",
        "counts": counts,
        "eligibility_reasons": dict(reason_counts.most_common()),
        "review_queue_reasons": dict(review_counts.most_common()),
        "metadata": metadata,
    }
    if a.detail_summary and a.detail_summary.exists():
        summary["detail_enrichment"] = json.loads(a.detail_summary.read_text(encoding="utf-8"))
    if a.enumeration_report and a.enumeration_report.exists():
        er = json.loads(a.enumeration_report.read_text(encoding="utf-8"))
        summary["enumeration"] = {
            "complete_enumeration": er.get("complete_enumeration"),
            "recursive_category_nodes_visited": er.get("recursive_category_nodes_visited"),
            "api_error_categories": er.get("api_error_categories"),
            "children_without_retailer_category_id": er.get("children_without_retailer_category_id"),
            "unique_products_after_dedup": er.get("unique_products_after_dedup"),
            "completeness_basis": er.get("completeness_basis"),
        }
    a.summary.parent.mkdir(parents=True, exist_ok=True)
    a.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
