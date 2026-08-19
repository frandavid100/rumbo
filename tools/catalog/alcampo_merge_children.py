from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

from alcampo_direct_catalog_v6 import Product, merge, write_outputs


def stable_product_key(product: Product) -> str:
    return f"sku:{product.sku}" if product.sku else f"product:{product.product_id}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--downloaded", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--min-products", type=int, default=5000)
    p.add_argument("--expected-shards", type=int, default=0)
    a = p.parse_args()

    products: dict[str, Product] = {}
    checks = []
    for cp in glob.glob(str(a.downloaded / "**/child_check.json"), recursive=True):
        try:
            checks.append(json.load(open(cp, encoding="utf-8")))
        except Exception:
            pass

    rows_seen = 0
    for pp in glob.glob(str(a.downloaded / "**/products.jsonl"), recursive=True):
        for line in open(pp, encoding="utf-8"):
            if not line.strip():
                continue
            row = json.loads(line)
            obj = Product(**row)
            rows_seen += 1
            key = stable_product_key(obj)
            products[key] = merge(products[key], obj) if key in products else obj

    merged = write_outputs(a.out, list(products.values()), checks)
    failed = [c for c in checks if not c.get("ok")]
    api_error_categories = sum(int(c.get("api_error_categories") or 0) for c in checks)
    missing_id_categories = sum(int(c.get("children_without_retailer_category_id") or 0) for c in checks)
    visited_nodes = sum(int(c.get("recursive_categories_visited") or 0) for c in checks)
    source_reported_sum = sum(int(c.get("source_reported_product_count") or 0) for c in checks)
    missing_shards = max(0, int(a.expected_shards or 0) - len(checks))

    # Alcampo's productCount is a useful retailer diagnostic but is not a regional
    # completeness denominator. The authoritative completeness condition is that every
    # scheduled first-party root shard produced an audit, and every recursively discovered
    # category node exhausted its own pageToken chain without API errors or unaddressable
    # children, followed by global listing-identity deduplication.
    complete = (
        bool(checks)
        and missing_shards == 0
        and (not a.expected_shards or len(checks) == a.expected_shards)
        and not failed
        and api_error_categories == 0
        and missing_id_categories == 0
        and merged["counts"]["food_products"] >= a.min_products
    )
    report = {
        "root_shards_expected": a.expected_shards,
        "root_shards_seen": len(checks),
        "root_shards_missing": missing_shards,
        "root_shards_failed": len(failed),
        "failed": failed,
        "recursive_category_nodes_visited": visited_nodes,
        "api_error_categories": api_error_categories,
        "children_without_retailer_category_id": missing_id_categories,
        "source_reported_product_count_sum_diagnostic_only": source_reported_sum,
        "product_rows_before_global_dedup": rows_seen,
        "unique_products_after_dedup": merged["counts"]["food_products"],
        "deduplication_identity": "retailer_sku_else_product_id",
        "minimum_products_sanity_floor": a.min_products,
        "completeness_basis": "all_scheduled_root_shards_plus_recursive_first_party_category_tree_plus_pageToken_exhaustion_then_listing_identity_dedup",
        "complete_enumeration": complete,
    }
    (a.out / "enumeration_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
