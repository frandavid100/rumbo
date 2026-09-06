from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

AUDIT_POLICY_VERSION = "1.0.0"
EXPECTED_PRODUCTS = 4280
EXPECTED_CANDIDATES = 38
PILOT_SIZE = 8

# Objective first-party routing only. These are Mercadona top-level departments whose
# category semantics are packaged grocery/food; fresh/raw departments and Bodega are
# deliberately excluded. A row must additionally have first-party packaging + unit-size
# metadata. This is not semantic classification and cannot make nutrition usable.
PACKAGED_FOOD_TOP_LEVEL_CATEGORIES = frozenset({
    "Aceite, especias y salsas",
    "Agua y refrescos",
    "Aperitivos",
    "Arroz, legumbres y pasta",
    "Azúcar, caramelos y chocolate",
    "Cacao, café e infusiones",
    "Cereales y galletas",
    "Conservas, caldos y cremas",
    "Huevos, leche y mantequilla",
    "Postres y yogures",
    "Zumos",
})


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


def has_food_signal(row: dict[str, Any]) -> bool:
    return bool(row.get("legal_name") or row.get("legal_denomination") or row.get("allergens"))


def is_category_packaged_candidate(row: dict[str, Any]) -> bool:
    if p9_photo(row) is None or row.get("ingredients"):
        return False
    if has_food_signal(row):
        return False
    if top_level_category(row) not in PACKAGED_FOOD_TOP_LEVEL_CATEGORIES:
        return False
    if not row.get("packaging") or row.get("unit_size") is None:
        return False
    return True


def stable_key(row: dict[str, Any]) -> tuple[str, str]:
    product_id = str(row.get("product_id") or "")
    ean = str(row.get("ean") or "")
    digest = hashlib.sha256(f"{product_id}\0{ean}".encode("utf-8")).hexdigest()
    return digest, product_id


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
        "routing_state": "P9_NO_INGREDIENTS_NO_LEGAL_OR_ALLERGEN_CATEGORY_PACKAGED_PILOT",
        "routing_signals": {
            "mercadona_packaged_food_department": True,
            "packaging": str(row.get("packaging")),
            "unit_size_present": True,
        },
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "product + label-image candidate",
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }


def audit_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(rows) != EXPECTED_PRODUCTS:
        raise ValueError(f"expected {EXPECTED_PRODUCTS} products, got {len(rows)}")

    candidates = [row for row in rows if is_category_packaged_candidate(row)]
    candidates.sort(key=stable_key)
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CANDIDATES} category-packaged candidates, got {len(candidates)}")

    pilot_rows = candidates[:PILOT_SIZE]
    pilot = [candidate_payload(row) for row in pilot_rows]
    category_counts = Counter(str(top_level_category(row)) for row in candidates)
    packaging_counts = Counter(str(row.get("packaging")) for row in candidates)

    summary = {
        "audit_policy_version": AUDIT_POLICY_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "inventory_products": len(rows),
        "candidate_universe": len(candidates),
        "pilot_size": len(pilot),
        "pilot_product_ids": [row["product_id"] for row in pilot],
        "candidate_product_ids": [str(row.get("product_id") or "") for row in candidates],
        "top_level_category_counts": dict(sorted(category_counts.items())),
        "packaging_counts": dict(sorted(packaging_counts.items())),
        "policy": (
            "perspective=9 official image + no structured ingredients + no legal-name/allergen food signal + "
            "Mercadona packaged-grocery top-level department + first-party packaging and unit-size metadata; "
            "Bodega and fresh/raw departments excluded. Routing only: no semantic classification and no nutrition promotion. "
            "The first eight stable-hash rows form the bounded pilot."
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
