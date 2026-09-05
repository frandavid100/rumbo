from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

AUDIT_POLICY_VERSION = "1.0.0"
EXPECTED_PRODUCTS = 4280
EXPECTED_CANDIDATES = 1


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


def _top_level_category(row: dict[str, Any]) -> str | None:
    path = _category_path(row)
    if not path:
        return None
    value = path[0].get("name")
    return str(value) if value else None


def _in_baby_food_branch(row: dict[str, Any]) -> bool:
    path = _category_path(row)
    return _top_level_category(row) == "Bebé" and any(
        str(item.get("name") or "") == "Alimentación infantil" for item in path
    )


def _has_substantive_allergens(row: dict[str, Any]) -> bool:
    value = row.get("allergens")
    if not value:
        return False
    return str(value).strip().casefold() not in {"x99", "x99."}


def candidate_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    photo = _p9_photo(row)
    if photo is None or row.get("ingredients") or not _in_baby_food_branch(row):
        return None

    legal_name = row.get("legal_name") or row.get("legal_denomination")
    signals = {
        "baby_food_branch": True,
        "brand": bool(row.get("brand")),
        "legal_name": bool(legal_name),
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
        "top_level_category": _top_level_category(row),
        "legal_name": legal_name,
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

    p9_no_ingredients_baby = [
        row for row in rows
        if _p9_photo(row) is not None
        and not row.get("ingredients")
        and _top_level_category(row) == "Bebé"
    ]
    p9_no_ingredients_baby_food = [row for row in p9_no_ingredients_baby if _in_baby_food_branch(row)]
    candidates = [payload for row in rows if (payload := candidate_payload(row)) is not None]
    candidates.sort(key=lambda row: str(row["product_id"]))
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CANDIDATES} candidates, got {len(candidates)}")

    summary = {
        "audit_policy_version": AUDIT_POLICY_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "inventory_products": len(rows),
        "p9_without_structured_ingredients_in_baby": len(p9_no_ingredients_baby),
        "p9_without_structured_ingredients_in_baby_food_branch": len(p9_no_ingredients_baby_food),
        "candidate_universe": len(candidates),
        "candidate_product_ids": [row["product_id"] for row in candidates],
        "candidate_policy": (
            "perspective=9 official image + no structured ingredients + Mercadona category path under Bebé > "
            "Alimentación infantil + first-party brand + legal food denomination + substantive allergen text. "
            "Placeholder allergen x99 is not evidence. This only routes a bounded OCR pilot and does not "
            "classify the product or make nutrition usable."
        ),
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
