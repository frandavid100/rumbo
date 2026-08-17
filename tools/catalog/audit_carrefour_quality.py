from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from nutrition_validation import validate_nutrition


COLLISION_RULES = [
    ("FISH_AS_OIL", "CULINARY_OIL", re.compile(r"\b(at[uú]n|anchoa|caballa|bonito|sardina|merluza|bacalao|melva|mejill|pulpo|calamar)\b", re.I)),
    ("VINEGAR_AS_RICE", "DRY_RICE", re.compile(r"\bvinagre\b", re.I)),
    ("JAM_AS_FRUIT", "FRUIT", re.compile(r"\b(mermelada|confitura|gelatina|golosina|caramelo)\b", re.I)),
    ("FISH_AS_EGG", "MAIN_EGG", re.compile(r"\b(merluza|pescado|bacalao|at[uú]n|calamar|caballa)\b", re.I)),
    ("BROTH_AS_MEAT", "MAIN_MEAT", re.compile(r"\b(caldo|sopa|crema)\b", re.I)),
    ("PREPARED_AS_DRY_PASTA", "DRY_PASTA", re.compile(r"\b(bolo(?:n|ñ)esa|tarrito|plato preparado|listo para comer)\b", re.I)),
    ("PREPARED_AS_DRY_RICE", "DRY_RICE", re.compile(r"\b(arroz a banda|arroz tres delicias|paella preparada|listo para comer)\b", re.I)),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--out", default="audit.json")
    args = ap.parse_args()
    db = sqlite3.connect(args.db)
    rows = db.execute(
        """
        SELECT p.product_id,p.name,p.family,p.subcategory,c.culinary_type,
               n.calories,n.protein_g,n.carbohydrate_g,n.fat_g,n.fiber_g,n.salt_g
          FROM classifications c
          JOIN products p USING(product_id)
          JOIN nutrition n USING(product_id)
         WHERE c.status='MENU_ELIGIBLE'
        """
    ).fetchall()

    blocking = []
    by_reason = Counter()
    by_type = Counter()
    by_family = Counter()
    for row in rows:
        pid, name, family, subcategory, ctype, kcal, protein, carb, fat, fiber, salt = row
        check = validate_nutrition(kcal, protein, carb, fat, fiber, salt)
        for reason in check.reasons:
            blocking.append({"product_id": pid, "name": name, "reason": reason, "culinary_type": ctype})
            by_reason[reason] += 1
        for label, wrong_type, pattern in COLLISION_RULES:
            if ctype == wrong_type and pattern.search(name or ""):
                blocking.append({"product_id": pid, "name": name, "reason": label, "culinary_type": ctype})
                by_reason[label] += 1
        by_type[ctype] += 1
        by_family[family] += 1

    # Deterministic stratified sample for human inspection: first few products
    # from every (family,type) cell after sorting by stable product id.
    sample_groups = defaultdict(list)
    sample_rows = db.execute(
        """
        SELECT p.product_id,p.name,p.family,c.culinary_type,n.calories,n.protein_g,n.carbohydrate_g,n.fat_g
          FROM classifications c JOIN products p USING(product_id) JOIN nutrition n USING(product_id)
         WHERE c.status='MENU_ELIGIBLE'
         ORDER BY p.family,c.culinary_type,p.product_id
        """
    ).fetchall()
    for r in sample_rows:
        key = (r[2], r[3])
        if len(sample_groups[key]) < 3:
            sample_groups[key].append({
                "product_id": r[0], "name": r[1], "family": r[2], "culinary_type": r[3],
                "nutrition": {"calories": r[4], "protein_g": r[5], "carbohydrate_g": r[6], "fat_g": r[7]},
            })

    audit = {
        "menu_eligible": len(rows),
        "blocking_issue_count": len(blocking),
        "blocking_product_count": len({x["product_id"] for x in blocking}),
        "blocking_by_reason": dict(by_reason),
        "menu_eligible_by_type": dict(by_type),
        "menu_eligible_by_family": dict(by_family),
        "blocking_examples": blocking[:100],
        "stratified_sample": [x for key in sorted(sample_groups) for x in sample_groups[key]],
    }
    Path(args.out).write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: audit[k] for k in ("menu_eligible", "blocking_issue_count", "blocking_product_count", "blocking_by_reason")}, ensure_ascii=False, indent=2))
    return 0 if not blocking else 3


if __name__ == "__main__":
    raise SystemExit(main())
