from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

AUDIT_POLICY_VERSION = "1.0.0"
EXPECTED_PRODUCTS = 4280
FRESH_FOOD_TOP_LEVEL_CATEGORIES = frozenset({"Carne", "Marisco y pescado", "Fruta y verdura"})
EXPECTED_CANDIDATE_IDS = frozenset({"17564", "81416", "81422", "87196", "87254", "68462", "69287", "69495"})


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def p9_photo(row: dict[str, Any]) -> dict[str, Any] | None:
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    return next(
        (
            photo
            for photo in photos
            if isinstance(photo, dict)
            and str(photo.get("perspective")) == "9"
            and bool(photo.get("zoom"))
        ),
        None,
    )


def top_level_category(row: dict[str, Any]) -> str | None:
    path = row.get("category_path") if isinstance(row.get("category_path"), list) else []
    if not path or not isinstance(path[0], dict):
        return None
    value = path[0].get("name")
    return str(value) if value else None


def has_food_signal(row: dict[str, Any]) -> bool:
    return bool(row.get("legal_name") or row.get("legal_denomination") or row.get("allergens"))


def stable_key(row: dict[str, Any]) -> tuple[str, str]:
    product_id = str(row.get("product_id") or "")
    ean = str(row.get("ean") or "")
    return hashlib.sha256(f"{product_id}\0{ean}".encode("utf-8")).hexdigest(), product_id


def candidate_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_id": str(row.get("product_id") or ""),
        "ean": row.get("ean"),
        "name": row.get("name"),
        "brand": row.get("brand"),
        "packaging": row.get("packaging"),
        "unit_size": row.get("unit_size"),
        "category_id": row.get("category_id"),
        "category_name": row.get("category_name"),
        "category_path": row.get("category_path"),
        "top_level_category": top_level_category(row),
        "legal_name": None,
        "allergens": None,
        "ingredients": None,
        "photos": row.get("photos"),
        "observed_at": row.get("observed_at"),
        "share_url": row.get("share_url"),
        "routing_state": "EXACT_CURRENT_P9_RESIDUAL_FRESH_FOOD_NO_STRUCTURED_SIGNAL",
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "product + label-image candidate",
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }


def audit_rows(
    products: list[dict[str, Any]],
    residual_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(products) != EXPECTED_PRODUCTS:
        raise ValueError(f"expected {EXPECTED_PRODUCTS} products, got {len(products)}")

    product_by_id = {str(row.get("product_id") or ""): row for row in products}
    if "" in product_by_id or len(product_by_id) != EXPECTED_PRODUCTS:
        raise ValueError("first-party product ids are missing or not unique")

    residual_ids = {str(row.get("product_id") or "") for row in residual_rows if row.get("product_id")}
    routed_ids: set[str] = set()
    for product_id in residual_ids:
        row = product_by_id.get(product_id)
        if row is None:
            continue
        if top_level_category(row) not in FRESH_FOOD_TOP_LEVEL_CATEGORIES:
            continue
        if p9_photo(row) is None:
            continue
        if row.get("ingredients") or has_food_signal(row):
            continue
        routed_ids.add(product_id)

    if routed_ids != EXPECTED_CANDIDATE_IDS:
        missing = sorted(EXPECTED_CANDIDATE_IDS - routed_ids)
        unexpected = sorted(routed_ids - EXPECTED_CANDIDATE_IDS)
        raise ValueError(
            f"expected exact residual fresh-food ids; missing={missing}, unexpected={unexpected}"
        )

    candidates = [candidate_payload(product_by_id[product_id]) for product_id in routed_ids]
    candidates.sort(key=stable_key)
    summary = {
        "audit_policy_version": AUDIT_POLICY_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "inventory_products": len(products),
        "residual_p9_rows_seen": len(residual_rows),
        "fresh_food_top_level_categories": sorted(FRESH_FOOD_TOP_LEVEL_CATEGORIES),
        "candidate_universe": len(candidates),
        "candidate_product_ids": [row["product_id"] for row in candidates],
        "candidate_categories": {
            category: sum(1 for row in candidates if row["top_level_category"] == category)
            for category in sorted(FRESH_FOOD_TOP_LEVEL_CATEGORIES)
        },
        "policy": (
            "Route only product ids present in the exact artifact-derived current perspective=9 residual, "
            "restricted to first-party top-level fresh-food categories Carne, Marisco y pescado, and Fruta y verdura, "
            "with no structured ingredients/legal denomination/allergen signal. The exact eight-id set is asserted "
            "to prevent stale arithmetic coverage or accidental non-food expansion. Routing only: no semantic "
            "classification and no nutrition inference."
        ),
        "images_persisted": False,
        "missing_values_inferred": False,
        "structured_api_macros_claimed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    return candidates, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", required=True)
    parser.add_argument("--residual-p9", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    candidates, summary = audit_rows(
        load_jsonl(Path(args.products)),
        load_jsonl(Path(args.residual_p9)),
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "candidates.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in candidates),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
