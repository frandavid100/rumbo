from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

AUDIT_POLICY_VERSION = "1.0.0"
EXPECTED_PRODUCTS = 4280
EXPECTED_CANDIDATES = 5
TARGET_TOP_LEVEL = "Bodega"
TARGET_LEVEL1 = "Cerveza sin alcohol"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _p9_photo(row: dict[str, Any]) -> dict[str, Any] | None:
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


def _category_path(row: dict[str, Any]) -> list[dict[str, Any]]:
    path = row.get("category_path") if isinstance(row.get("category_path"), list) else []
    return [item for item in path if isinstance(item, dict)]


def _named_level(row: dict[str, Any], level: str) -> list[str]:
    return [
        str(item.get("name"))
        for item in _category_path(row)
        if str(item.get("level")) == level and item.get("name")
    ]


def _is_target_branch(row: dict[str, Any]) -> bool:
    level0 = _named_level(row, "0")
    level1 = _named_level(row, "1")
    return bool(level0) and level0[0] == TARGET_TOP_LEVEL and TARGET_LEVEL1 in level1


def candidate_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    photo = _p9_photo(row)
    if photo is None or row.get("ingredients") or not _is_target_branch(row):
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
        "legal_name": row.get("legal_name") or row.get("legal_denomination"),
        "allergens": row.get("allergens"),
        "ingredients": None,
        "photos": row.get("photos"),
        "observed_at": row.get("observed_at"),
        "share_url": row.get("share_url"),
        "routing_signals": {
            "perspective_9": True,
            "no_structured_ingredients": True,
            "mercadona_bodega_no_alcohol_branch": True,
        },
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
        "candidate_universe": len(candidates),
        "candidate_product_ids": [row["product_id"] for row in candidates],
        "candidate_policy": (
            "perspective=9 official image + no structured ingredients + Mercadona first-party category path "
            "Bodega > Cerveza sin alcohol. This is a bounded OCR-routing rule only: it does not classify the "
            "product and does not make nutrition usable without the normal conservative OCR contract."
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
