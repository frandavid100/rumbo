from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from mercadona_ocr_image_candidates import has_p9_zoom, photos


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _still_review_ids(path: Path) -> set[str]:
    rows = _load_jsonl(path)
    if len(rows) != 2630:
        raise ValueError(f"expected 2630 persisted p9 rows, got {len(rows)}")
    return {
        str(row.get("product_id") or "")
        for row in rows
        if row.get("status") == "REVIEW"
        and (row.get("replay") or {}).get("status") == "REVIEW"
    }


def build_inventory(
    products: list[dict[str, Any]], still_review_ids: set[str]
) -> dict[str, Any]:
    perspective_products: dict[str, set[str]] = defaultdict(set)
    perspective_photos: Counter[str] = Counter()
    example_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    products_with_any_alternative: set[str] = set()
    eligible_p9_food_rows = 0

    for row in products:
        pid = str(row.get("product_id") or "")
        if pid not in still_review_ids or not row.get("ingredients") or not has_p9_zoom(row):
            continue
        eligible_p9_food_rows += 1
        seen_for_product: set[str] = set()
        for photo in photos(row):
            perspective = str(photo.get("perspective") or "")
            if not photo.get("zoom") or not perspective or perspective == "9":
                continue
            perspective_photos[perspective] += 1
            perspective_products[perspective].add(pid)
            products_with_any_alternative.add(pid)
            if perspective not in seen_for_product and len(example_rows[perspective]) < 8:
                example_rows[perspective].append(
                    {
                        "product_id": pid,
                        "ean": row.get("ean"),
                        "name": row.get("name"),
                    }
                )
            seen_for_product.add(perspective)

    perspectives = sorted(
        perspective_products,
        key=lambda value: (int(value) if value.isdigit() else 10**9, value),
    )
    return {
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image routing metadata",
        "selection_policy": "STRUCTURED_INGREDIENTS_WITH_P9; HISTORICAL_P9_AND_SAFE_REPLAY_BOTH_REVIEW; TRUE_NON_P9_ALTERNATIVE",
        "inventory_products": len(products),
        "persisted_p9_rows": 2630,
        "baseline_still_review_products": len(still_review_ids),
        "eligible_p9_food_rows": eligible_p9_food_rows,
        "products_with_any_true_non_p9_alternative": len(products_with_any_alternative),
        "perspectives": {
            perspective: {
                "eligible_products": len(perspective_products[perspective]),
                "eligible_zoom_photos": perspective_photos[perspective],
                "examples": example_rows[perspective],
            }
            for perspective in perspectives
        },
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", required=True)
    parser.add_argument("--p9-replay-results", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    products = _load_jsonl(Path(args.products))
    if len(products) != 4280:
        raise ValueError(f"expected 4280 Mercadona products, got {len(products)}")
    still_review_ids = _still_review_ids(Path(args.p9_replay_results))
    inventory = build_inventory(products, still_review_ids)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(inventory, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
