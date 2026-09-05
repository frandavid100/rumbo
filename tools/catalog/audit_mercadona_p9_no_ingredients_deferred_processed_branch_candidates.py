from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

AUDIT_POLICY_VERSION = "1.0.0"
EXPECTED_PRODUCTS = 4280
EXPECTED_DEFERRED = 111
EXPECTED_CANDIDATES = 4
DEFERRED_TOP_LEVEL_CATEGORIES = frozenset({"Carne", "Marisco y pescado"})
PROCESSED_LEVEL1_BRANCHES = {
    "Carne": frozenset({"Empanados y elaborados"}),
    "Marisco y pescado": frozenset({"Salazones y ahumados"}),
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def p9_photo(row: dict[str, Any]) -> dict[str, Any] | None:
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    return next((photo for photo in photos if isinstance(photo, dict) and str(photo.get("perspective")) == "9" and photo.get("zoom")), None)


def category_path(row: dict[str, Any]) -> list[dict[str, Any]]:
    path = row.get("category_path") if isinstance(row.get("category_path"), list) else []
    return [item for item in path if isinstance(item, dict)]


def top_level_category(row: dict[str, Any]) -> str | None:
    path = category_path(row)
    if not path:
        return None
    value = path[0].get("name")
    return str(value) if value else None


def level1_categories(row: dict[str, Any]) -> list[str]:
    return [str(item.get("name")) for item in category_path(row) if str(item.get("level")) == "1" and item.get("name")]


def matched_processed_branches(row: dict[str, Any]) -> list[str]:
    top = top_level_category(row)
    allowed = PROCESSED_LEVEL1_BRANCHES.get(top, frozenset())
    return sorted(name for name in level1_categories(row) if name in allowed)


def is_deferred_food_cohort(row: dict[str, Any]) -> bool:
    return p9_photo(row) is not None and not row.get("ingredients") and top_level_category(row) in {"Bodega", "Carne", "Fruta y verdura", "Marisco y pescado"}


def candidate_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    if p9_photo(row) is None or row.get("ingredients"):
        return None
    top = top_level_category(row)
    if top not in DEFERRED_TOP_LEVEL_CATEGORIES:
        return None
    branches = matched_processed_branches(row)
    if not branches:
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
        "top_level_category": top,
        "matched_processed_level1_branches": branches,
        "legal_name": row.get("legal_name") or row.get("legal_denomination"),
        "allergens": row.get("allergens"),
        "ingredients": None,
        "photos": row.get("photos"),
        "observed_at": row.get("observed_at"),
        "share_url": row.get("share_url"),
        "routing_state": "DEFERRED_FRESH_TOP_LEVEL_WITH_PROCESSED_SUBBRANCH",
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "product + label-image routing audit",
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = load_jsonl(Path(args.products))
    if len(rows) != EXPECTED_PRODUCTS:
        raise ValueError(f"expected {EXPECTED_PRODUCTS} products, got {len(rows)}")
    deferred = [row for row in rows if is_deferred_food_cohort(row)]
    if len(deferred) != EXPECTED_DEFERRED:
        raise ValueError(f"expected {EXPECTED_DEFERRED} deferred p9/no-ingredients food products, got {len(deferred)}")
    candidates = sorted((payload for row in rows if (payload := candidate_payload(row)) is not None), key=lambda row: row["product_id"])
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CANDIDATES} candidates, got {len(candidates)}")

    branch_counts = Counter(branch for row in candidates for branch in row["matched_processed_level1_branches"])
    category_counts = Counter(str(row["top_level_category"]) for row in candidates)
    summary = {
        "audit_policy_version": AUDIT_POLICY_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "inventory_products": len(rows),
        "deferred_p9_without_structured_ingredients": len(deferred),
        "candidate_universe": len(candidates),
        "candidate_product_ids": [row["product_id"] for row in candidates],
        "candidate_names": {row["product_id"]: row.get("name") for row in candidates},
        "top_level_category_counts": dict(sorted(category_counts.items())),
        "matched_level1_branch_counts": dict(sorted(branch_counts.items())),
        "candidate_policy": (
            "perspective=9 official image + no structured ingredients + previously deferred fresh top-level "
            "department (Carne/Marisco y pescado) + first-party category path explicitly entering a processed "
            "level-1 branch (Empanados y elaborados or Salazones y ahumados). Category metadata is used only "
            "for bounded OCR routing; it is not semantic classification and never makes nutrition usable."
        ),
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "candidates.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in candidates), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
