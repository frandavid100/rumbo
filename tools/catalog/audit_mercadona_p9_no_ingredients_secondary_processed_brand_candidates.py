from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

AUDIT_POLICY_VERSION = "1.0.0"
EXPECTED_PRODUCTS = 4280
EXPECTED_CANDIDATES = 3
ALREADY_PROCESSED_PRODUCT_IDS = frozenset({"60400"})
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


def _p9_photo(row: dict[str, Any]) -> dict[str, Any] | None:
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    for photo in photos:
        if isinstance(photo, dict) and str(photo.get("perspective")) == "9" and photo.get("zoom"):
            return photo
    return None


def _category_path(row: dict[str, Any]) -> list[dict[str, Any]]:
    path = row.get("category_path") if isinstance(row.get("category_path"), list) else []
    return [item for item in path if isinstance(item, dict)]


def _level0_categories(row: dict[str, Any]) -> list[str]:
    return [
        str(item.get("name"))
        for item in _category_path(row)
        if str(item.get("level")) == "0" and item.get("name")
    ]


def _primary_top_level(row: dict[str, Any]) -> str | None:
    categories = _level0_categories(row)
    return categories[0] if categories else None


def _secondary_processed_categories(row: dict[str, Any]) -> list[str]:
    categories = _level0_categories(row)
    return [name for name in categories[1:] if name in PROCESSED_TOP_LEVEL_CATEGORIES]


def candidate_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    pid = str(row.get("product_id") or "")
    if pid in ALREADY_PROCESSED_PRODUCT_IDS:
        return None
    if _p9_photo(row) is None or row.get("ingredients"):
        return None
    primary = _primary_top_level(row)
    if primary in PROCESSED_TOP_LEVEL_CATEGORIES:
        return None
    secondary = _secondary_processed_categories(row)
    if not secondary or not row.get("brand"):
        return None

    signals = {
        "brand": True,
        "secondary_processed_category": True,
    }
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
        "primary_top_level_category": primary,
        "secondary_processed_top_level_categories": secondary,
        "legal_name": row.get("legal_name") or row.get("legal_denomination"),
        "allergens": row.get("allergens"),
        "ingredients": None,
        "photos": row.get("photos"),
        "observed_at": row.get("observed_at"),
        "share_url": row.get("share_url"),
        "routing_signals": signals,
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "product + label-image candidate",
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

    all_secondary = [
        row for row in rows
        if _p9_photo(row) is not None
        and not row.get("ingredients")
        and _primary_top_level(row) not in PROCESSED_TOP_LEVEL_CATEGORIES
        and _secondary_processed_categories(row)
    ]
    candidates = [payload for row in rows if (payload := candidate_payload(row)) is not None]
    candidates.sort(key=lambda row: str(row["product_id"]))
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CANDIDATES} candidates, got {len(candidates)}")

    expected_ids = ["13240", "19852", "22444"]
    actual_ids = [row["product_id"] for row in candidates]
    if actual_ids != expected_ids:
        raise ValueError(f"unexpected candidate ids: {actual_ids}")

    primary_counts = Counter(str(row["primary_top_level_category"]) for row in candidates)
    secondary_counts = Counter(
        name
        for row in candidates
        for name in row["secondary_processed_top_level_categories"]
    )
    summary = {
        "audit_policy_version": AUDIT_POLICY_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "inventory_products": len(rows),
        "p9_no_ingredients_with_secondary_processed_category": len(all_secondary),
        "already_processed_product_ids": sorted(ALREADY_PROCESSED_PRODUCT_IDS),
        "candidate_universe": len(candidates),
        "candidate_product_ids": actual_ids,
        "candidate_policy": (
            "perspective=9 official image + no structured ingredients + primary top-level category outside the "
            "already processed packaged-food route + a secondary level=0 Mercadona category inside that processed "
            "route + first-party brand; exclude product 60400 already covered by the baby-food pilot. This is OCR "
            "routing only and does not classify products or make nutrition usable."
        ),
        "primary_top_level_category_counts": dict(sorted(primary_counts.items())),
        "secondary_processed_category_counts": dict(sorted(secondary_counts.items())),
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }

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
