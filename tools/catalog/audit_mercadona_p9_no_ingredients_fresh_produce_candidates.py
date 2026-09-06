from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

AUDIT_POLICY_VERSION = "1.0.0"
EXPECTED_PRODUCTS = 4280
EXPECTED_FOOD_SIGNAL_CANDIDATES = 95
EXPECTED_PRIOR_FOOD_SIGNAL_PROCESSED = 32
EXPECTED_FRESH_PRODUCE_TOTAL = 28
EXPECTED_CANDIDATES = 15

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


def p9_photo(row: dict[str, Any]) -> dict[str, Any] | None:
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    return next((photo for photo in photos if isinstance(photo, dict) and str(photo.get("perspective")) == "9" and photo.get("zoom")), None)


def top_level_category(row: dict[str, Any]) -> str | None:
    path = row.get("category_path") if isinstance(row.get("category_path"), list) else []
    if not path or not isinstance(path[0], dict):
        return None
    value = path[0].get("name")
    return str(value) if value else None


def is_food_signal_candidate(row: dict[str, Any]) -> bool:
    return bool(
        p9_photo(row) is not None
        and not row.get("ingredients")
        and top_level_category(row) in FOOD_TOP_LEVEL_CATEGORIES
        and (row.get("legal_name") or row.get("legal_denomination") or row.get("allergens"))
    )


def stable_key(row: dict[str, Any]) -> tuple[str, str]:
    product_id = str(row.get("product_id") or "")
    ean = str(row.get("ean") or "")
    return hashlib.sha256(f"{product_id}\0{ean}".encode("utf-8")).hexdigest(), product_id


def prior_food_signal_processed_ids(food_signal_rows: list[dict[str, Any]]) -> set[str]:
    ordered = sorted(food_signal_rows, key=stable_key)
    processed: set[str] = set()
    for shard in range(4):
        shard_rows = [row for i, row in enumerate(ordered) if i % 4 == shard]
        processed.update(str(row.get("product_id") or "") for row in shard_rows[:8])
    return processed


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
        "legal_name": row.get("legal_name") or row.get("legal_denomination"),
        "allergens": row.get("allergens"),
        "ingredients": None,
        "photos": row.get("photos"),
        "observed_at": row.get("observed_at"),
        "share_url": row.get("share_url"),
        "routing_state": "P9_NO_INGREDIENTS_FRESH_PRODUCE_AFTER_INITIAL_FOOD_SIGNAL_TRANCHES",
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "product + label-image candidate",
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }


def audit_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(rows) != EXPECTED_PRODUCTS:
        raise ValueError(f"expected {EXPECTED_PRODUCTS} products, got {len(rows)}")

    food_signal = [row for row in rows if is_food_signal_candidate(row)]
    if len(food_signal) != EXPECTED_FOOD_SIGNAL_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_FOOD_SIGNAL_CANDIDATES} food-signal candidates, got {len(food_signal)}")

    prior_ids = prior_food_signal_processed_ids(food_signal)
    if len(prior_ids) != EXPECTED_PRIOR_FOOD_SIGNAL_PROCESSED:
        raise ValueError(f"expected {EXPECTED_PRIOR_FOOD_SIGNAL_PROCESSED} prior rows, got {len(prior_ids)}")

    produce = [row for row in food_signal if top_level_category(row) == "Fruta y verdura"]
    if len(produce) != EXPECTED_FRESH_PRODUCE_TOTAL:
        raise ValueError(f"expected {EXPECTED_FRESH_PRODUCE_TOTAL} produce rows, got {len(produce)}")

    candidates = [candidate_payload(row) for row in produce if str(row.get("product_id") or "") not in prior_ids]
    candidates.sort(key=stable_key)
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CANDIDATES} fresh-produce residuals, got {len(candidates)}")

    summary = {
        "audit_policy_version": AUDIT_POLICY_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "inventory_products": len(rows),
        "food_signal_candidate_universe": len(food_signal),
        "prior_food_signal_processed": len(prior_ids),
        "fresh_produce_total": len(produce),
        "candidate_universe": len(candidates),
        "candidate_product_ids": [row["product_id"] for row in candidates],
        "policy": (
            "perspective=9 official image + no structured ingredients + existing first-party food-routing signal + "
            "top-level Fruta y verdura; subtract the exact deterministic 32-item initial food-signal tranche. "
            "Routing only: no semantic classification and no nutrition inference."
        ),
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    return candidates, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    candidates, summary = audit_rows(load_jsonl(Path(args.products)))
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
