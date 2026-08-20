#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


NUTRITIONAL = {
    "PRIMARY_PROTEIN", "COMPLEMENTARY_PROTEIN", "PRIMARY_CARBOHYDRATE",
    "COMPLEMENTARY_CARBOHYDRATE", "CONCENTRATED_FAT", "COMPLEMENTARY_FAT",
    "VEGETABLE", "FRUIT",
}
CULINARY = {
    "PLATE_CENTER", "PLATE_BASE", "SIDE", "TOPPING", "SAUCE_DRESSING",
    "CEREAL_BASE", "CEREAL_MIX_IN", "POWDER_BASE", "POWDER_MIX_IN",
    "SANDWICH_BASE", "SANDWICH_FILLING", "SPREAD", "COOKING_MEDIUM",
    "BINDER", "COATING", "SEASONING", "STANDALONE", "BEVERAGE", "DESSERT",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    db = sqlite3.connect(f"file:{args.catalog}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    failures: list[str] = []

    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok": failures.append(f"SQLite integrity: {integrity}")
    required = {"metadata", "products", "retailer_listings", "nutrition", "nutrient_evidence",
                "classifications", "classification_roles"}
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required <= tables: failures.append(f"Missing tables: {sorted(required - tables)}")

    bad_nutrition = db.execute("""SELECT COUNT(*) FROM nutrition WHERE
      calories < 0 OR calories > 1000 OR protein_g < 0 OR protein_g > 100 OR
      carbohydrate_g < 0 OR carbohydrate_g > 100 OR fat_g < 0 OR fat_g > 100 OR
      fiber_g < 0 OR fiber_g > 100""").fetchone()[0]
    if bad_nutrition: failures.append(f"Implausible nutrition rows: {bad_nutrition}")
    bad_portions = db.execute("SELECT COUNT(*) FROM classifications WHERE portion_basis_grams <= 0 OR portion_basis_grams > 5000").fetchone()[0]
    if bad_portions: failures.append(f"Invalid portions: {bad_portions}")
    unknown_roles = [(row[0], row[1]) for row in db.execute("SELECT axis,role FROM classification_roles")
                     if row[1] not in (NUTRITIONAL if row[0] == "NUTRITIONAL" else CULINARY)]
    if unknown_roles: failures.append(f"Unknown roles: {unknown_roles[:10]}")
    invalid_eligible = db.execute("""SELECT COUNT(*) FROM classifications c JOIN nutrition n USING(product_id)
      WHERE c.status='MENU_ELIGIBLE' AND (c.classified != 1 OR n.calories IS NULL OR
      n.protein_g IS NULL OR n.carbohydrate_g IS NULL OR n.fat_g IS NULL OR
      NOT EXISTS (SELECT 1 FROM classification_roles r WHERE r.product_id=c.product_id AND r.axis='CULINARY'))""").fetchone()[0]
    if invalid_eligible: failures.append(f"Invalid MENU_ELIGIBLE rows: {invalid_eligible}")

    role_counts = dict(db.execute("SELECT role,COUNT(*) FROM classification_roles GROUP BY role"))
    essential = {"PRIMARY_PROTEIN", "PRIMARY_CARBOHYDRATE", "CONCENTRATED_FAT", "FRUIT", "VEGETABLE"}
    missing_coverage = sorted(role for role in essential if role_counts.get(role, 0) < 3)
    if missing_coverage: failures.append(f"Insufficient generator coverage: {missing_coverage}")
    statuses = dict(db.execute("SELECT status,COUNT(*) FROM classifications GROUP BY status"))
    result = {
        "valid": not failures, "failures": failures,
        "products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "statuses": statuses, "role_counts": role_counts,
        "families": db.execute("SELECT COUNT(DISTINCT family) FROM products WHERE family IS NOT NULL").fetchone()[0],
        "retailer_listings": db.execute("SELECT COUNT(*) FROM retailer_listings").fetchone()[0],
    }
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.json: args.json.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
