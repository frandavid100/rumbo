from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from alcampo_direct_catalog_v8 import collect_root
from alcampo_direct_catalog_v6 import Product, merge, write_outputs

# Explicitly non-food branches are not traversed. "Sin alcohol" remains allowed.
DENY_BRANCH = re.compile(
    r"\b(vino|vinos|cerveza|cervezas|licor|licores|whisky|whiskey|ron|ginebra|vodka|brandy|cognac|champagne|cava|sidra|vermut|vermouth|sangr[ií]a|espirituosas?|bebidas?\s+alcoh[oó]licas?|perfumer[ií]a|droguer[ií]a|herbolario|control\s+de\s+peso)\b",
    re.I,
)


def denied_branch(name: str) -> bool:
    if re.search(r"\bsin\s+alcohol\b", name or "", re.I):
        return False
    return bool(DENY_BRANCH.search(name or ""))


def stable_product_key(product: Product) -> str:
    """Alcampo's retailerProductId is the stable listing identity across taxonomy nodes."""
    return f"sku:{product.sku}" if product.sku else f"product:{product.product_id}"


def collect_with_fresh_session_retries(label: str, rid: str, attempts: int = 6):
    """Retry a category with a fresh anonymous session when Alcampo leaves a token pending."""
    best_products = []
    best_meta = None
    for attempt in range(1, attempts + 1):
        products, meta = collect_root(label, rid, 0)
        # Prefer the attempt that exposed the most products; on a tie prefer the one
        # that exposed more child taxonomy, because descendants remain independently
        # addressable even if a later pageToken was transiently pending.
        score = (len(products), len(meta.get("child_categories") or []))
        best_score = (
            len(best_products),
            len((best_meta or {}).get("child_categories") or []),
        )
        if score > best_score:
            best_products = products
            best_meta = meta
        if not meta.get("errors"):
            return products, meta, attempt
        if attempt < attempts:
            time.sleep(min(0.8 * attempt, 4.0))
    return best_products, best_meta or meta, attempts


def recursive_collect(root_label: str, root_rid: str):
    products: dict[str, Product] = {}
    queue: list[tuple[str, str, int | None, int]] = [(root_label, root_rid, None, 0)]
    queued = {root_rid}
    visited: set[str] = set()
    node_audit: list[dict] = []
    unresolved: list[dict] = []
    missing_retailer_ids: list[dict] = []

    while queue:
        label, rid, source_count, depth = queue.pop(0)
        queued.discard(rid)
        if rid in visited:
            continue
        visited.add(rid)

        plist, meta, attempts = collect_with_fresh_session_retries(label, rid)
        for product in plist:
            key = stable_product_key(product)
            products[key] = merge(products[key], product) if key in products else product

        errors = list(meta.get("errors") or [])
        children = list(meta.get("child_categories") or [])
        audit = {
            "label": label,
            "retailer_category_id": rid,
            "depth": depth,
            "source_reported_product_count": source_count,
            "direct_unique_products": int(meta.get("unique_decorated_products") or 0),
            "pages": int(meta.get("pages") or 0),
            "fresh_session_attempts": attempts,
            "errors": errors,
            "children_discovered": len(children),
        }
        node_audit.append(audit)
        if errors:
            unresolved.append(audit)

        # Child taxonomy comes from page 1 and is independently addressable. Do not
        # discard it merely because a later pageToken on the parent remained pending;
        # traversing descendants both improves coverage and preserves the evidence needed
        # to diagnose the one unresolved parent node. Completeness still remains false
        # until every such parent error is cleared.
        for child in children:
            if not isinstance(child, dict):
                continue
            child_label = str(child.get("name") or "").strip()
            child_rid = child.get("retailerCategoryId")
            child_count = child.get("productCount")
            if denied_branch(child_label):
                continue
            if not child_rid:
                if int(child_count or 0) > 0:
                    missing_retailer_ids.append({
                        "parent_retailer_category_id": rid,
                        "name": child_label,
                        "productCount": child_count,
                    })
                continue
            child_rid = str(child_rid)
            if child_rid not in visited and child_rid not in queued:
                queue.append((child_label or child_rid, child_rid, int(child_count or 0), depth + 1))
                queued.add(child_rid)

    return list(products.values()), node_audit, unresolved, missing_retailer_ids


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--rid", required=True)
    p.add_argument("--expected", type=int, default=0)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()

    products, node_audit, unresolved, missing_ids = recursive_collect(a.label, a.rid)
    # write_outputs performs the existing first-party alcohol filter and creates JSONL + SQLite.
    root_meta = [{
        "label": a.label,
        "retailer_category_id": a.rid,
        "recursive_category_nodes": node_audit,
        "recursive_categories_visited": len(node_audit),
        "unresolved_categories": unresolved,
        "children_without_retailer_category_id": missing_ids,
        "deduplication_identity": "retailer_sku_else_product_id",
    }]
    summary = write_outputs(a.out, products, root_meta)
    got = summary["counts"]["food_products"]

    # Alcampo's productCount is retained only as source diagnostics. It is not a valid
    # completeness denominator for the active regional assortment: direct API traversal
    # can exhaust pageTokens cleanly at a different count. Completeness is therefore
    # defined by exhausting every discovered first-party category node without API errors.
    ok = not unresolved and not missing_ids and got > 0
    check = {
        "label": a.label,
        "rid": a.rid,
        "source_reported_product_count": a.expected,
        "food_products_recursive_union": got,
        "recursive_categories_visited": len(node_audit),
        "api_error_categories": len(unresolved),
        "children_without_retailer_category_id": len(missing_ids),
        "unresolved": unresolved,
        "missing_retailer_ids": missing_ids,
        "deduplication_identity": "retailer_sku_else_product_id",
        "completeness_basis": "recursive_first_party_category_tree_plus_pageToken_exhaustion",
        "source_product_count_is_diagnostic_only": True,
        "ok": ok,
    }
    (a.out / "child_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding="utf-8")
    (a.out / "category_traversal.json").write_text(json.dumps(node_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(check, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
