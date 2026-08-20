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


def recursive_collect(root_label: str, root_rid: str, max_depth: int = 64):
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
            "children_traversed": depth < max_depth,
        }
        node_audit.append(audit)
        if errors:
            unresolved.append(audit)

        # A max_depth=0 shard is intentionally a direct-only audit of a top-level root.
        # Descendant trees are scheduled independently by the workflow so that large
        # taxonomies are parallelised instead of timing out in one giant root job.
        if depth >= max_depth:
            continue

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
    p.add_argument("--max-depth", type=int, default=64)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()

    max_depth=max(0,a.max_depth)
    products, node_audit, unresolved, missing_ids = recursive_collect(a.label, a.rid, max_depth=max_depth)
    root_meta = [{
        "label": a.label,
        "retailer_category_id": a.rid,
        "recursive_category_nodes": node_audit,
        "recursive_categories_visited": len(node_audit),
        "unresolved_categories": unresolved,
        "children_without_retailer_category_id": missing_ids,
        "deduplication_identity": "retailer_sku_else_product_id",
        "max_depth": max_depth,
    }]
    summary = write_outputs(a.out, products, root_meta)
    got = summary["counts"]["food_products"]

    # Aggregate roots can legitimately expose only descendants. A direct-only root shard
    # is complete when its API request itself exhausted cleanly and exposed child taxonomy,
    # even if it has zero direct food listings; those children are separate scheduled shards.
    root_has_children = bool(node_audit and int(node_audit[0].get("children_discovered") or 0) > 0)
    has_expected_content = got > 0 or (max_depth == 0 and root_has_children)
    ok = not unresolved and not missing_ids and has_expected_content
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
        "max_depth": max_depth,
        "aggregate_root_with_children": bool(max_depth == 0 and root_has_children),
        "completeness_basis": "scheduled_shard_category_tree_plus_pageToken_exhaustion",
        "source_product_count_is_diagnostic_only": True,
        "ok": ok,
    }
    (a.out / "child_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding="utf-8")
    (a.out / "category_traversal.json").write_text(json.dumps(node_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(check, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
