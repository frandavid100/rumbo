from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object")
        rows.append(value)
    return rows


def is_listing_only(row: dict) -> bool:
    if row.get("direct_page_observed") is True:
        return False
    if row.get("direct_listing_observed") is True:
        return True
    return str(row.get("capture_method") or "") == "OPENAI_WEB_OFFICIAL_CATEGORY_INDEXED"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Add observation-scope counts to the Carrefour first-party summary."
    )
    ap.add_argument("--products", required=True)
    ap.add_argument("--summary", required=True)
    args = ap.parse_args()

    products_path = Path(args.products)
    summary_path = Path(args.summary)
    rows = read_jsonl(products_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    listing_only = sum(1 for row in rows if is_listing_only(row))
    product_pages = len(rows) - listing_only
    counts = summary.setdefault("counts", {})
    counts["verified_first_party_products"] = len(rows)
    counts["verified_product_page_observations"] = product_pages
    counts["verified_listing_only_observations"] = listing_only
    # Backwards-compatible alias retained while downstream consumers migrate.
    counts["verified_direct_products"] = len(rows)
    summary["observation_scope_note"] = (
        "verified_first_party_products includes both official Carrefour product-page observations and "
        "official Carrefour category-listing-only observations. Listing-only records never imply that "
        "ingredients, nutrition or other product-detail fields were observed."
    )
    summary["source"] = "CARREFOUR_OFFICIAL_HOSTS"
    summary["source_hosts"] = [
        "https://www.carrefour.es",
        "https://actforfood.carrefour.es",
    ]
    summary["provenance_note"] = (
        "Only fields observed directly on official Carrefour-controlled pages are merged. Third-party catalogs may seed "
        "candidate URLs, but their product facts are never promoted to CARREFOUR_FIRST_PARTY. Indexed official-page "
        "retrieval is explicitly marked because crawl lag is possible."
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verified_first_party_products": len(rows),
                "verified_product_page_observations": product_pages,
                "verified_listing_only_observations": listing_only,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
