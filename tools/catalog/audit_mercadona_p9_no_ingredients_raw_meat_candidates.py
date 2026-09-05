from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

AUDIT_POLICY_VERSION = "1.0.0"
EXPECTED_PRODUCTS = 4280
EXPECTED_FOOD_SIGNAL_CANDIDATES = 95
EXPECTED_PRIOR_FOOD_SIGNAL_PROCESSED = 32
EXPECTED_RAW_MEAT_RESIDUAL = 31
EXPECTED_ALREADY_PROCESSED_LATER = 5
EXPECTED_CANDIDATES = 26
PILOT_SIZE = 8

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

# These Carne rows were processed after the first 32-item food-signal tranche and
# therefore must not be duplicated here. 4073/4334 belong to the closed secondary
# frozen-meat front; 52776 to the closed deferred-packaged front; 25243/4949 are
# already-known DECLARED controls reused by the row-order live validation.
ALREADY_PROCESSED_LATER_IDS = frozenset({"4073", "4334", "52776", "25243", "4949"})


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
            and photo.get("zoom")
        ),
        None,
    )


def top_level_category(row: dict[str, Any]) -> str | None:
    path = row.get("category_path") if isinstance(row.get("category_path"), list) else []
    if not path or not isinstance(path[0], dict):
        return None
    value = path[0].get("name")
    return str(value) if value else None


def is_food_signal_candidate(row: dict[str, Any]) -> bool:
    if p9_photo(row) is None or row.get("ingredients"):
        return False
    if top_level_category(row) not in FOOD_TOP_LEVEL_CATEGORIES:
        return False
    return bool(row.get("legal_name") or row.get("legal_denomination") or row.get("allergens"))


def stable_key(row: dict[str, Any]) -> tuple[str, str]:
    product_id = str(row.get("product_id") or "")
    ean = str(row.get("ean") or "")
    digest = hashlib.sha256(f"{product_id}\0{ean}".encode("utf-8")).hexdigest()
    return digest, product_id


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
        "routing_state": "P9_NO_INGREDIENTS_RAW_MEAT_AFTER_CLOSED_FRONTS",
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
        raise ValueError(
            f"expected {EXPECTED_FOOD_SIGNAL_CANDIDATES} food-signal candidates, got {len(food_signal)}"
        )

    prior_ids = prior_food_signal_processed_ids(food_signal)
    if len(prior_ids) != EXPECTED_PRIOR_FOOD_SIGNAL_PROCESSED:
        raise ValueError(
            f"expected {EXPECTED_PRIOR_FOOD_SIGNAL_PROCESSED} prior food-signal rows, got {len(prior_ids)}"
        )

    raw_meat_residual = [
        row
        for row in food_signal
        if top_level_category(row) == "Carne"
        and str(row.get("product_id") or "") not in prior_ids
    ]
    if len(raw_meat_residual) != EXPECTED_RAW_MEAT_RESIDUAL:
        raise ValueError(
            f"expected {EXPECTED_RAW_MEAT_RESIDUAL} raw-meat residual rows, got {len(raw_meat_residual)}"
        )

    residual_ids = {str(row.get("product_id") or "") for row in raw_meat_residual}
    if not ALREADY_PROCESSED_LATER_IDS <= residual_ids:
        raise ValueError(
            "known later-processed raw-meat ids missing from residual: "
            f"{sorted(ALREADY_PROCESSED_LATER_IDS - residual_ids)}"
        )

    candidates = [
        candidate_payload(row)
        for row in raw_meat_residual
        if str(row.get("product_id") or "") not in ALREADY_PROCESSED_LATER_IDS
    ]
    candidates.sort(key=stable_key)
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CANDIDATES} raw-meat candidates, got {len(candidates)}")

    pilot = candidates[:PILOT_SIZE]
    packaging_counts = Counter(str(row.get("packaging") or "UNKNOWN") for row in candidates)
    allergen_counts = Counter(
        "SUBSTANTIVE"
        if row.get("allergens") and str(row.get("allergens")).strip().casefold() not in {"x99", "x99."}
        else "PLACEHOLDER_OR_NONE"
        for row in candidates
    )
    summary = {
        "audit_policy_version": AUDIT_POLICY_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "inventory_products": len(rows),
        "food_signal_candidate_universe": len(food_signal),
        "prior_food_signal_processed": len(prior_ids),
        "raw_meat_residual_before_later_closed_fronts": len(raw_meat_residual),
        "already_processed_later": len(ALREADY_PROCESSED_LATER_IDS),
        "already_processed_later_ids": sorted(ALREADY_PROCESSED_LATER_IDS),
        "candidate_universe": len(candidates),
        "pilot_size": len(pilot),
        "pilot_product_ids": [row["product_id"] for row in pilot],
        "candidate_product_ids": [row["product_id"] for row in candidates],
        "packaging_counts": dict(sorted(packaging_counts.items())),
        "allergen_signal_counts": dict(sorted(allergen_counts.items())),
        "policy": (
            "perspective=9 official image + no structured ingredients + existing first-party food-routing signal + "
            "top-level Carne; subtract the exact deterministic 32-item food-signal tranche and later closed/known "
            "processed Carne rows. This is OCR routing only, not semantic classification. The first eight stable-hash "
            "rows form the bounded pilot."
        ),
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    return pilot, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows = load_jsonl(Path(args.products))
    pilot, summary = audit_rows(rows)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "candidates.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in pilot),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
