from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

AUDIT_POLICY_VERSION = "1.0.0"
EXPECTED_PRODUCTS = 4280
EXPECTED_CANDIDATES = 1

# These departments were deliberately deferred by the processed-category expansion
# because the broad pilot was dominated by fresh/raw products or Bodega entries
# with no usable nutrition panel. A product in this set only returns to OCR when
# Mercadona itself exposes three independent packaged-food routing signals:
# brand + packaging + substantive allergen text. This is routing, not semantic
# classification, and none of these fields make nutrition usable by themselves.
DEFERRED_TOP_LEVEL_CATEGORIES = frozenset({
    "Bodega",
    "Carne",
    "Fruta y verdura",
    "Marisco y pescado",
})


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _p9_photo(row: dict[str, Any]) -> dict[str, Any] | None:
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    for photo in photos:
        if isinstance(photo, dict) and str(photo.get("perspective")) == "9" and photo.get("zoom"):
            return photo
    return None


def _top_level_category(row: dict[str, Any]) -> str | None:
    path = row.get("category_path") if isinstance(row.get("category_path"), list) else []
    if not path or not isinstance(path[0], dict):
        return None
    value = path[0].get("name")
    return str(value) if value else None


def _has_substantive_allergens(row: dict[str, Any]) -> bool:
    value = row.get("allergens")
    if not value:
        return False
    normalized = str(value).strip().casefold()
    return normalized not in {"x99", "x99."}


def candidate_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    photo = _p9_photo(row)
    if photo is None or row.get("ingredients"):
        return None

    top_level = _top_level_category(row)
    if top_level not in DEFERRED_TOP_LEVEL_CATEGORIES:
        return None

    signals = {
        "brand": bool(row.get("brand")),
        "packaging": bool(row.get("packaging")),
        "substantive_allergens": _has_substantive_allergens(row),
    }
    if not all(signals.values()):
        return None

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
        "top_level_category": top_level,
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

    deferred_p9_no_ingredients = [
        row
        for row in rows
        if _p9_photo(row) is not None
        and not row.get("ingredients")
        and _top_level_category(row) in DEFERRED_TOP_LEVEL_CATEGORIES
    ]
    candidates = [payload for row in rows if (payload := candidate_payload(row)) is not None]
    candidates.sort(key=lambda row: str(row["product_id"]))
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CANDIDATES} candidates, got {len(candidates)}")

    category_counts = Counter(str(row["top_level_category"]) for row in candidates)
    summary = {
        "audit_policy_version": AUDIT_POLICY_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "inventory_products": len(rows),
        "deferred_p9_without_structured_ingredients": len(deferred_p9_no_ingredients),
        "candidate_universe": len(candidates),
        "candidate_product_ids": [row["product_id"] for row in candidates],
        "candidate_policy": (
            "perspective=9 official image + no structured ingredients + top-level category previously deferred "
            "from the low-yield broad no-ingredients route + Mercadona first-party brand + packaging + substantive "
            "allergen text. Placeholder allergen x99 is not evidence. This is OCR routing only: it does not "
            "classify the product and does not make nutrition usable."
        ),
        "top_level_category_counts": dict(sorted(category_counts.items())),
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
