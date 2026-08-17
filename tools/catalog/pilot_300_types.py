from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import unicodedata

from classifier import ProductFeatures, classify_type, CLASSIFIER_VERSION
from mercadona_weekly_catalog_adapter import deterministic_candidate_ids, fetch_product, fetch_product_ids, stratified_sample

SEED = "rumbo-mercadona-pilot-2026-08"
MIN_TYPE_RECOGNIZED = 299
FOOD_CATEGORY_MARKERS = (
    "aceite", "especias", "salsas", "agua", "refrescos", "aperitivos",
    "arroz", "legumbres", "pasta", "azucar", "caramelos", "chocolate",
    "cacao", "cafe", "infusiones", "carne", "cereales", "galletas",
    "charcuteria", "quesos", "congelados", "conservas", "caldos", "cremas",
    "fruta", "verdura", "huevos", "leche", "mantequilla", "panaderia",
    "pasteleria", "pescado", "marisco", "pizzas", "platos preparados",
    "postres", "yogures", "zumos", "bebidas vegetales",
)


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFD", (value or "").lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _is_food_category(value: str) -> bool:
    folded = _fold(value)
    return any(marker in folded for marker in FOOD_CATEGORY_MARKERS)


def _fetch_products(ids: list[str], workers: int = 16):
    products = []
    errors = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_product, product_id): product_id for product_id in ids}
        for future in as_completed(futures):
            product_id = futures[future]
            try:
                products.append(future.result())
            except Exception as exc:
                errors.append({"product_id": product_id, "error": f"{type(exc).__name__}:{exc}"})
    products.sort(key=lambda x: x.product_id)
    errors.sort(key=lambda x: x["product_id"])
    return products, errors


def main() -> int:
    ids = fetch_product_ids()
    candidate_ids = deterministic_candidate_ids(ids, seed=SEED, limit=900)
    products, errors = _fetch_products(candidate_ids)
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

    recognized = len(sample) - len(unknown)
    report = {
        "classifier_version": CLASSIFIER_VERSION,
        "index_size": len(ids),
        "candidate_products_fetched": len(products),
        "sample": len(sample),
        "type_recognized": recognized,
        "minimum_required": MIN_TYPE_RECOGNIZED,
        "type_rate": round(recognized/len(sample), 4) if sample else 0,
        "unknown": unknown,
        "types": dict(types.most_common()),
        "acquisition_errors": errors,
    }
    Path("pilot-300-types-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if len(sample) != 300:
        return 2
    return 0 if recognized >= MIN_TYPE_RECOGNIZED else 3


if __name__ == "__main__":
    raise SystemExit(main())
