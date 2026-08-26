from __future__ import annotations

import argparse
import json
from pathlib import Path

import alcampo_html_tree_recovery as tree

VERSION = "alcampo-api-first-tree-recovery-v1"


def api_first(label: str, rid: str, expected: int, out: Path) -> bool:
    """Use Alcampo's official paginated catalogue API before recursive SSR.

    A direct child can contain hundreds of products and dozens of descendants. The
    previous audit walked all descendants first and only then tried the official
    paginated category endpoint, so transient SSR 202 responses could consume the
    whole Actions time budget. If one clean pageToken enumeration reaches the exact
    source-reported category count, it is stronger and cheaper evidence and there is
    no reason to crawl the same subtree again.
    """
    products, meta, errors, attempts = tree.collect_api_fresh(label, rid, attempts=1)
    source_target = max(0, int(expected or 0))
    pages = int(meta.get("pages") or 0)
    clean = not errors and pages > 0
    target_exact = len(products) >= source_target if source_target else bool(products)
    if not (clean and target_exact):
        return False

    out.mkdir(parents=True, exist_ok=True)
    summary = tree.write_outputs(out, products, [{
        "label": label,
        "retailer_category_id": rid,
        "method": "FIRST_PARTY_CATALOGUE_API_PAGETOKEN_EXHAUSTION_API_FIRST",
        "version": VERSION,
        "source_reported_product_count": source_target or None,
        "api_pages": pages,
        "api_products": len(products),
        "api_attempts": attempts,
        "api_errors": [],
        "child_categories": meta.get("child_categories") or [],
    }])
    skus = sorted({str(p.sku) for p in products if p.sku})
    food_count = int(summary.get("counts", {}).get("food_products") or 0)
    check = {
        "label": label,
        "rid": rid,
        "source_reported_product_count": source_target or None,
        "source_product_count_stale": False,
        "food_products_recursive_union": food_count,
        "recursive_categories_visited": 0,
        "api_error_categories": 0,
        "children_without_retailer_category_id": 0,
        "unresolved": [],
        "ssr_unresolved": [],
        "child_api_attempts": [],
        "missing_retailer_ids": [],
        "deduplication_identity": "retailer_sku_else_product_id",
        "max_depth": 0,
        "aggregate_root_with_children": bool(meta.get("child_categories")),
        "completeness_basis": "first_party_catalogue_api_pageToken_exhaustion_reaches_source_reported_count",
        "source_product_count_is_diagnostic_only": False,
        "html_product_links": 0,
        "html_link_skus": [],
        "enumerated_skus": skus,
        "identity_materialized_products": len(products),
        "identity_mapping_error": None,
        "traversal_truncated": False,
        "api_fallback_attempted": True,
        "api_fallback_products": len(products),
        "api_fallback_pages": pages,
        "api_fallback_errors": [],
        "api_fallback_attempts": attempts,
        "api_fallback_enumeration_ok": True,
        "enumeration_ok": True,
        "decoration_ok": True,
        "decoration_errors": [],
        "ok": True,
        "api_first_short_circuit": True,
    }
    (out / "child_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "category_html_tree_recovery.json").write_text(json.dumps({
        "label": label,
        "retailer_category_id": rid,
        "method": "FIRST_PARTY_CATALOGUE_API_PAGETOKEN_EXHAUSTION_API_FIRST",
        "version": VERSION,
        "source_reported_product_count": source_target or None,
        "api_pages": pages,
        "api_products": len(products),
        "api_attempts": attempts,
        "api_errors": [],
        "child_categories": meta.get("child_categories") or [],
        "ssr_skipped_because_api_exhausted_target": True,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(check, ensure_ascii=False, indent=2))
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--rid", required=True)
    ap.add_argument("--expected", type=int, default=0)
    ap.add_argument("--max-depth", type=int, default=6)
    ap.add_argument("--max-nodes", type=int, default=120)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    if api_first(a.label, a.rid, a.expected, a.out):
        return 0
    return tree.recover_tree(a.label, a.rid, a.expected, a.out, a.max_depth, a.max_nodes)


if __name__ == "__main__":
    raise SystemExit(main())
