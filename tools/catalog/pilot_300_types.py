from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from classifier import ProductFeatures, classify_type, CLASSIFIER_VERSION
from mercadona_weekly_catalog_adapter import deterministic_candidate_ids, fetch_product_ids, stratified_sample
from pilot_large_catalog import _fetch_candidate_products, _is_food_category

SEED = "rumbo-mercadona-pilot-2026-08"


def main() -> int:
    ids = fetch_product_ids()
    candidate_ids = deterministic_candidate_ids(ids, seed=SEED, limit=900)
    products, errors = _fetch_candidate_products(candidate_ids, 16)
    food = [p for p in products if _is_food_category(p.category_key)]
    sample = stratified_sample(food, size=300, per_category_cap=24)

    types = Counter()
    unknown = []
    for p in sample:
        assignment = classify_type(ProductFeatures(
            name=p.name, legal_name=p.legal_name, ingredients=p.ingredients,
            family=p.family, subcategory=p.subcategory,
        ))
        if assignment is None:
            unknown.append({"product_id": p.product_id, "name": p.name, "category": p.category_key})
        else:
            types[assignment.value] += 1

    report = {
        "classifier_version": CLASSIFIER_VERSION,
        "index_size": len(ids),
        "candidate_products_fetched": len(products),
        "sample": len(sample),
        "type_recognized": len(sample) - len(unknown),
        "type_rate": round((len(sample)-len(unknown))/len(sample), 4) if sample else 0,
        "unknown": unknown,
        "types": dict(types.most_common()),
        "acquisition_errors": errors,
    }
    Path("pilot-300-types-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if len(sample) == 300 else 2


if __name__ == "__main__":
    raise SystemExit(main())
