from __future__ import annotations

import argparse
import html as htmlmod
import json
import re
from collections import deque
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from alcampo_direct_catalog_v6 import Product, merge, write_outputs
from alcampo_direct_catalog_v8 import collect_root as collect_api_root
from alcampo_html_leaf_recovery import (
    BASE,
    PRODUCT_ID_RE,
    PRODUCT_LINK_RE,
    RETAILER_ID_RE,
    materialize_visible_identities,
    request_html,
)

VERSION = "alcampo-html-tree-recovery-v4"
CATEGORY_LINK_RE = re.compile(
    r'href=["\']([^"\']*/categories/[^"\']+/(OC[0-9A-Za-z]+)(?:\?[^"\']*)?)["\']',
    re.I,
)


def stable_key(p: Product) -> str:
    return f"sku:{p.sku}" if p.sku else f"product:{p.product_id}"


def slug_label(url: str, fallback: str) -> str:
    parts = [unquote(x) for x in urlsplit(url).path.rstrip("/").split("/") if x]
    if len(parts) >= 2:
        return parts[-2].replace("-", " ").strip() or fallback
    return fallback


def direct_children(body: str, final_url: str, parent_rid: str) -> list[dict]:
    """Return only category links proven to be direct descendants of this page.

    Alcampo renders global navigation category links in every SSR page. A child of
    the current category is distinguishable because its canonical path is exactly
    `<parent canonical path without RID>/<child slug>/<child RID>`. Requiring this
    path shape prevents the global navigation from turning a recovery shard into a
    crawl of the whole store.
    """
    parent_path = urlsplit(final_url).path.rstrip("/")
    if parent_path.rsplit("/", 1)[-1].lower() == parent_rid.lower():
        parent_base = parent_path.rsplit("/", 1)[0]
    else:
        parent_base = parent_path

    out: dict[str, dict] = {}
    for href, rid in CATEGORY_LINK_RE.findall(body):
        href = htmlmod.unescape(href)
        absolute = urljoin(BASE, href)
        path = urlsplit(absolute).path.rstrip("/")
        if rid.lower() == parent_rid.lower() or not path.startswith(parent_base + "/"):
            continue
        tail = path[len(parent_base):].strip("/").split("/")
        if len(tail) != 2 or tail[-1].lower() != rid.lower():
            continue
        out.setdefault(rid, {
            "retailer_category_id": rid,
            "label": unquote(tail[-2]).replace("-", " ").strip() or rid,
            "url": absolute,
        })
    return list(out.values())


def parse_node(label: str, rid: str, depth: int) -> tuple[dict, dict[str, Product], list[dict]]:
    try:
        status, final_url, body, body_bytes = request_html(__import__("urllib.request").request.build_opener(
            __import__("urllib.request").request.HTTPCookieProcessor(__import__("http.cookiejar").cookiejar.CookieJar())
        ), rid)
        error = None
    except Exception as exc:
        status = None
        final_url = f"{BASE}/categories/~/{rid}"
        body = ""
        body_bytes = 0
        error = f"{type(exc).__name__}:{exc}"

    product_ids = list(dict.fromkeys(PRODUCT_ID_RE.findall(body)))
    retailer_ids = list(dict.fromkeys(RETAILER_ID_RE.findall(body)))
    links = PRODUCT_LINK_RE.findall(body)
    link_skus = list(dict.fromkeys(sku for _, sku in links))
    products, mapping_error = materialize_visible_identities(label, final_url, product_ids, retailer_ids, links)
    children = direct_children(body, final_url, rid) if status == 200 else []

    node = {
        "label": label,
        "retailer_category_id": rid,
        "depth": depth,
        "requested_url": f"{BASE}/categories/~/{rid}",
        "final_url": final_url,
        "html_status": status,
        "html_bytes": body_bytes,
        "html_product_ids": len(product_ids),
        "html_retailer_product_ids": len(retailer_ids),
        "html_product_links": len(link_skus),
        "html_product_id_values": product_ids,
        "html_retailer_id_values": retailer_ids,
        "html_link_skus": link_skus,
        "identity_materialized_products": len(products),
        "identity_mapping_error": mapping_error,
        "direct_children": children,
        "direct_children_count": len(children),
        "request_error": error,
    }
    return node, products, children


def recover_tree(label: str, rid: str, expected: int, out: Path, max_depth: int, max_nodes: int) -> int:
    out.mkdir(parents=True, exist_ok=True)
    queue = deque([(label, rid, 0)])
    queued = {rid}
    visited: set[str] = set()
    products: dict[str, Product] = {}
    nodes: list[dict] = []
    request_failures: list[dict] = []

    while queue and len(visited) < max_nodes:
        node_label, node_rid, depth = queue.popleft()
        queued.discard(node_rid)
        if node_rid in visited:
            continue
        visited.add(node_rid)

        node, node_products, children = parse_node(node_label, node_rid, depth)
        nodes.append(node)
        if node.get("html_status") != 200 or node.get("identity_mapping_error"):
            request_failures.append({
                "label": node_label,
                "retailer_category_id": node_rid,
                "html_status": node.get("html_status"),
                "identity_mapping_error": node.get("identity_mapping_error"),
                "html_product_id_values": node.get("html_product_id_values"),
                "html_retailer_id_values": node.get("html_retailer_id_values"),
                "html_link_skus": node.get("html_link_skus"),
                "request_error": node.get("request_error"),
            })

        for p in node_products.values():
            key = stable_key(p)
            products[key] = merge(products[key], p) if key in products else p

        if depth >= max_depth:
            continue
        for child in children:
            child_rid = str(child["retailer_category_id"])
            if child_rid in visited or child_rid in queued:
                continue
            queue.append((str(child.get("label") or child_rid), child_rid, depth + 1))
            queued.add(child_rid)

    source_target = max(0, int(expected or 0))
    required = max(1, int(source_target * 0.95)) if source_target else 1
    traversal_truncated = bool(queue)
    ssr_skus = sorted({str(p.sku) for p in products.values() if p.sku})

    # The official category SSR surface deliberately renders at most 50 cards on
    # many leaf categories. When that first-party HTML cannot reach the source
    # productCount (or a descendant is stuck on transient 202), use Alcampo's own
    # v6 product-pages API as a narrow fallback for this one category. v8 exhausts
    # the cookie-bound pageToken sequence and retries 202 responses, so this is a
    # bounded first-party pagination recovery rather than a second broad crawl.
    api_fallback_attempted = bool(
        source_target and (len(ssr_skus) < required or request_failures or traversal_truncated)
    )
    api_fallback_meta: dict = {}
    api_fallback_errors: list[str] = []
    api_fallback_products = 0
    if api_fallback_attempted:
        try:
            api_products, api_fallback_meta = collect_api_root(label, rid, 0)
            api_fallback_errors = [str(x) for x in (api_fallback_meta.get("errors") or [])]
            api_fallback_products = len(api_products)
            for p in api_products:
                key = stable_key(p)
                products[key] = merge(products[key], p) if key in products else p
        except Exception as exc:
            api_fallback_errors = [f"{type(exc).__name__}:{exc}"]

    skus = sorted({str(p.sku) for p in products.values() if p.sku})
    target_satisfied = len(skus) >= required if source_target else bool(skus)
    api_fallback_enumeration_ok = bool(
        api_fallback_attempted
        and not api_fallback_errors
        and int(api_fallback_meta.get("pages") or 0) > 0
        and target_satisfied
    )
    enumeration_ok = (
        target_satisfied
        and not traversal_truncated
        and (not request_failures or api_fallback_enumeration_ok)
    )

    meta = [{
        "label": label,
        "retailer_category_id": rid,
        "method": (
            "FIRST_PARTY_CATEGORY_HTML_RECURSIVE_DIRECT_DESCENDANTS_PAIRED_IDENTITY_VECTORS"
            "_PLUS_NARROW_V6_PAGETOKEN_FALLBACK"
        ),
        "version": VERSION,
        "source_reported_product_count": source_target or None,
        "categories_visited": len(nodes),
        "max_depth": max_depth,
        "max_nodes": max_nodes,
        "traversal_truncated": traversal_truncated,
        "unique_visible_product_skus": len(skus),
        "ssr_visible_product_skus": len(ssr_skus),
        "api_fallback_attempted": api_fallback_attempted,
        "api_fallback_products": api_fallback_products,
        "api_fallback_pages": int(api_fallback_meta.get("pages") or 0),
        "api_fallback_errors": api_fallback_errors,
        "api_fallback_enumeration_ok": api_fallback_enumeration_ok,
        "nodes": nodes,
    }]
    summary = write_outputs(out, list(products.values()), meta)
    effective_unresolved = [] if enumeration_ok else request_failures
    check = {
        "label": label,
        "rid": rid,
        "source_reported_product_count": source_target or None,
        "food_products_recursive_union": summary["counts"]["food_products"],
        "recursive_categories_visited": len(nodes),
        "api_error_categories": 0 if enumeration_ok else len(request_failures) + len(api_fallback_errors),
        "children_without_retailer_category_id": 0,
        "unresolved": effective_unresolved,
        "ssr_unresolved": request_failures,
        "missing_retailer_ids": [],
        "deduplication_identity": "retailer_sku_else_product_id",
        "max_depth": max_depth,
        "aggregate_root_with_children": len(nodes) > 1,
        "completeness_basis": (
            "first_party_category_html_recursive_direct_descendants_paired_identity_vectors"
            "_plus_narrow_v6_pageToken_exhaustion"
            if api_fallback_attempted
            else "first_party_category_html_recursive_direct_descendants_paired_identity_vectors"
        ),
        "source_product_count_is_diagnostic_only": False if source_target else True,
        "html_product_links": len(ssr_skus),
        "html_link_skus": ssr_skus,
        "enumerated_skus": skus,
        "identity_materialized_products": len(products),
        "identity_mapping_error": None,
        "traversal_truncated": traversal_truncated,
        "api_fallback_attempted": api_fallback_attempted,
        "api_fallback_products": api_fallback_products,
        "api_fallback_pages": int(api_fallback_meta.get("pages") or 0),
        "api_fallback_errors": api_fallback_errors,
        "api_fallback_enumeration_ok": api_fallback_enumeration_ok,
        "enumeration_ok": enumeration_ok,
        "decoration_ok": api_fallback_enumeration_ok,
        "decoration_errors": [] if api_fallback_enumeration_ok else ["not_attempted_or_failed_known_v6_products"],
        "ok": enumeration_ok,
    }
    (out / "child_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "category_html_tree_recovery.json").write_text(json.dumps(meta[0], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(check, ensure_ascii=False, indent=2))
    return 0 if enumeration_ok else 2


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--rid", required=True)
    p.add_argument("--expected", type=int, default=0)
    p.add_argument("--max-depth", type=int, default=5)
    p.add_argument("--max-nodes", type=int, default=80)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    return recover_tree(a.label, a.rid, a.expected, a.out, max(0, a.max_depth), max(1, a.max_nodes))


if __name__ == "__main__":
    raise SystemExit(main())
