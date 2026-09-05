from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_PRODUCTS = 4280
EXPECTED_ALL_SECONDARY = 7
EXPECTED_RESIDUALS = 3
ALREADY_PROCESSED_PRODUCT_IDS = frozenset({"60400"})
BRANDED_FRONT_PRODUCT_IDS = frozenset({"13240", "19852", "22444"})
PROCESSED_TOP_LEVEL_CATEGORIES = frozenset({
    "Aceite, especias y salsas",
    "Agua y refrescos",
    "Aperitivos",
    "Arroz, legumbres y pasta",
    "Azúcar, caramelos y chocolate",
    "Cacao, café e infusiones",
    "Cereales y galletas",
    "Charcutería y quesos",
    "Congelados",
    "Conservas, caldos y cremas",
    "Huevos, leche y mantequilla",
    "Panadería y pastelería",
    "Pizzas y platos preparados",
    "Postres y yogures",
    "Zumos",
})


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def p9_photo(row: dict[str, Any]) -> dict[str, Any] | None:
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    return next(
        (
            photo for photo in photos
            if isinstance(photo, dict)
            and str(photo.get("perspective")) == "9"
            and photo.get("zoom")
        ),
        None,
    )


def level0_categories(row: dict[str, Any]) -> list[str]:
    path = row.get("category_path") if isinstance(row.get("category_path"), list) else []
    return [
        str(item.get("name"))
        for item in path
        if isinstance(item, dict)
        and str(item.get("level")) == "0"
        and item.get("name")
    ]


def primary_top_level(row: dict[str, Any]) -> str | None:
    categories = level0_categories(row)
    return categories[0] if categories else None


def secondary_processed_categories(row: dict[str, Any]) -> list[str]:
    return [name for name in level0_categories(row)[1:] if name in PROCESSED_TOP_LEVEL_CATEGORIES]


def is_secondary_cohort(row: dict[str, Any]) -> bool:
    return (
        p9_photo(row) is not None
        and not row.get("ingredients")
        and primary_top_level(row) not in PROCESSED_TOP_LEVEL_CATEGORIES
        and bool(secondary_processed_categories(row))
    )


def residual_payload(row: dict[str, Any]) -> dict[str, Any]:
    pid = str(row.get("product_id") or "")
    return {
        "product_id": pid,
        "ean": row.get("ean"),
        "name": row.get("name"),
        "brand": row.get("brand"),
        "packaging": row.get("packaging"),
        "unit_size": row.get("unit_size"),
        "category_id": row.get("category_id"),
        "category_name": row.get("category_name"),
        "category_path": row.get("category_path"),
        "primary_top_level_category": primary_top_level(row),
        "secondary_processed_top_level_categories": secondary_processed_categories(row),
        "legal_name": row.get("legal_name") or row.get("legal_denomination"),
        "supplier": row.get("supplier") or row.get("provider"),
        "ingredients": None,
        "allergens": row.get("allergens"),
        "photos": row.get("photos"),
        "observed_at": row.get("observed_at"),
        "share_url": row.get("share_url"),
        "routing_state": "RESIDUAL_UNBRANDED_OR_OTHER_AFTER_CLOSED_FRONTS",
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "product + label-image routing audit",
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows = load_jsonl(Path(args.products))
    if len(rows) != EXPECTED_PRODUCTS:
        raise ValueError(f"expected {EXPECTED_PRODUCTS} products, got {len(rows)}")

    cohort = [row for row in rows if is_secondary_cohort(row)]
    if len(cohort) != EXPECTED_ALL_SECONDARY:
        raise ValueError(f"expected {EXPECTED_ALL_SECONDARY} secondary-cohort products, got {len(cohort)}")

    cohort_ids = {str(row.get("product_id") or "") for row in cohort}
    known_ids = ALREADY_PROCESSED_PRODUCT_IDS | BRANDED_FRONT_PRODUCT_IDS
    if not known_ids <= cohort_ids:
        raise ValueError(f"known closed-front ids missing from cohort: {sorted(known_ids - cohort_ids)}")

    residual_rows = [row for row in cohort if str(row.get("product_id") or "") not in known_ids]
    residuals = sorted((residual_payload(row) for row in residual_rows), key=lambda row: row["product_id"])
    if len(residuals) != EXPECTED_RESIDUALS:
        raise ValueError(f"expected {EXPECTED_RESIDUALS} residuals, got {len(residuals)}")

    primary_counts = Counter(str(row["primary_top_level_category"]) for row in residuals)
    secondary_counts = Counter(
        category
        for row in residuals
        for category in row["secondary_processed_top_level_categories"]
    )
    brand_counts = Counter("BRANDED" if row.get("brand") else "UNBRANDED" for row in residuals)

    summary = {
        "audit_policy_version": "1.0.0",
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "inventory_products": len(rows),
        "secondary_cohort": len(cohort),
        "already_processed_product_ids": sorted(ALREADY_PROCESSED_PRODUCT_IDS),
        "closed_branded_front_product_ids": sorted(BRANDED_FRONT_PRODUCT_IDS),
        "residual_universe": len(residuals),
        "residual_product_ids": [row["product_id"] for row in residuals],
        "residual_names": {row["product_id"]: row.get("name") for row in residuals},
        "primary_top_level_category_counts": dict(sorted(primary_counts.items())),
        "secondary_processed_category_counts": dict(sorted(secondary_counts.items())),
        "brand_presence_counts": dict(sorted(brand_counts.items())),
        "policy": (
            "Diagnostic routing audit only: perspective=9 official image + no structured ingredients + primary "
            "top-level outside the already processed packaged-food route + secondary processed level-0 category; "
            "subtract the already processed baby-food product and the closed branded secondary front. Residuals "
            "are not OCR-eligible merely by appearing here; inspect their product semantics before any OCR launch."
        ),
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "residuals.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in residuals),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for row in residuals:
        print(json.dumps({
            "product_id": row["product_id"],
            "name": row.get("name"),
            "brand": row.get("brand"),
            "packaging": row.get("packaging"),
            "primary": row.get("primary_top_level_category"),
            "secondary": row.get("secondary_processed_top_level_categories"),
            "legal_name": row.get("legal_name"),
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
