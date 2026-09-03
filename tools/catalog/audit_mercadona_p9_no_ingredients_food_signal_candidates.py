from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

AUDIT_POLICY_VERSION = "1.0.0"
EXPECTED_PRODUCTS = 4280
EXPECTED_CANDIDATES = 95

FOOD_TOP_LEVEL_CATEGORIES = frozenset({
    "Aceite, especias y salsas",
    "Agua y refrescos",
    "Aperitivos",
    "Arroz, legumbres y pasta",
    "Azúcar, caramelos y chocolate",
    "Bodega",
    "Cacao, café e infusiones",
    "Carne",
    "Cereales y galletas",
    "Charcutería y quesos",
    "Congelados",
    "Conservas, caldos y cremas",
    "Fruta y verdura",
    "Huevos, leche y mantequilla",
    "Marisco y pescado",
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


def _top_level_category(row: dict[str, Any]) -> str | None:
    path = row.get("category_path") if isinstance(row.get("category_path"), list) else []
    if not path or not isinstance(path[0], dict):
        return None
    value = path[0].get("name")
    return str(value) if value else None


def candidate_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    photo = _p9_photo(row)
    if photo is None or row.get("ingredients"):
        return None

    top_level = _top_level_category(row)
    if top_level not in FOOD_TOP_LEVEL_CATEGORIES:
        return None

    signals = {
        "legal_name": bool(row.get("legal_name") or row.get("legal_denomination")),
        "allergens": bool(row.get("allergens")),
    }
    if not any(signals.values()):
        return None

    return {
        "product_id": str(row.get("product_id") or ""),
        "ean": row.get("ean"),
        "name": row.get("name"),
        "brand": row.get("brand"),
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

    p9_no_ingredients = [row for row in rows if _p9_photo(row) is not None and not row.get("ingredients")]
    food_routed = [row for row in p9_no_ingredients if _top_level_category(row) in FOOD_TOP_LEVEL_CATEGORIES]
    candidates = [payload for row in rows if (payload := candidate_payload(row)) is not None]
    candidates.sort(key=lambda row: str(row["product_id"]))
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CANDIDATES} candidates, got {len(candidates)}")

    category_counts = Counter(str(row["top_level_category"]) for row in candidates)
    signal_counts = Counter(
        signal
        for row in candidates
        for signal, present in row["routing_signals"].items()
        if present
    )
    summary = {
        "audit_policy_version": AUDIT_POLICY_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "inventory_products": len(rows),
        "priority_p9_with_structured_ingredients_already_processed": 2630,
        "p9_without_structured_ingredients": len(p9_no_ingredients),
        "p9_without_ingredients_in_first_party_food_categories": len(food_routed),
        "candidate_universe": len(candidates),
        "candidate_policy": (
            "perspective=9 official image + no structured ingredients + Mercadona top-level grocery/food category "
            "+ at least one independent first-party food-routing signal (legal name or allergens). This is OCR "
            "routing only: it does not classify the product and does not make nutrition usable."
        ),
        "top_level_category_counts": dict(sorted(category_counts.items())),
        "routing_signal_counts": dict(sorted(signal_counts.items())),
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
