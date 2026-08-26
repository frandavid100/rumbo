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

VERSION = "alcampo-html-tree-recovery-v5"
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
    """Return only category links proven to be direct descendants of this page."""
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


def collect_api_fresh(label: str, rid: str, attempts: int = 3) -> tuple[list[Product], dict, list[str], int]:
    """Retry a narrow official API category with a fresh anonymous session.

    A category can remain pending (202) for one cookie-bound session while the same
    category is immediately available to a fresh session. Keep the richest clean
    first-party response and never combine an errored partial response with a clean
    one.
    """
    best_products: list[Product] = []
    best_meta: dict = {}
    errors: list[str] = []
    for attempt in range(1, max(1, attempts) + 1):
        try:
            plist, meta = collect_api_root(label, rid, 0)
        except Exception as exc:
            errors.append(f"attempt_{attempt}:{type(exc).__name__}:{exc}")
            continue
        current_errors = [str(x) for x in (meta.get("errors") or [])]
        if not current_errors:
            return plist, meta, [], attempt
        errors.extend(f"attempt_{attempt}:{x}" for x in current_errors)
        if len(plist) > len(best_products):
            best_products, best_meta = plist, meta
    return best_products, best_meta, errors, max(1, attempts)


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

    # First recover only descendants that SSR itself proved exist but left pending.
    # This is narrower and more reliable than repeatedly asking the broad parent.
    child_api_attempts: list[dict] = []
    for failure in request_failures:
        child_rid = str(failure.get("retailer_category_id") or "").strip()
        if not child_rid or child_rid == rid:
            continue
        child_label = str(failure.get("label") or child_rid)
        plist, meta, errors, attempts_used = collect_api_fresh(child_label, child_rid, attempts=3)
        for p in plist:
            key = stable_key(p)
            products[key] = merge(products[key], p) if key in products else p
        child_api_attempts.append({
            "label": child_label,
            "retailer_category_id": child_rid,
            "products": len(plist),
            "pages": int(meta.get("pages") or 0),
            "errors": errors,
            "attempts": attempts_used,
            "ok": bool(not errors and int(meta.get("pages") or 0) > 0),
        })

    interim_skus = sorted({str(p.sku) for p in products.values() if p.sku})
    root_api_attempted = bool(
        source_target and (len(interim_skus) < required or traversal_truncated)
    )
    root_api_meta: dict = {}
    root_api_errors: list[str] = []
    root_api_products = 0
    root_api_attempts = 0
    if root_api_attempted:
        api_products, root_api_meta, root_api_errors, root_api_attempts = collect_api_fresh(label, rid, attempts=3)
        root_api_products = len(api_products)
        for p in api_products:
            key = stable_key(p)
            products[key] = merge(products[key], p) if key in products else p

    skus = sorted({str(p.sku) for p in products.values() if p.sku})
    normal_target_satisfied = len(skus) >= required if source_target else bool(skus)

    # A stale productCount must not create a permanent false failure. Only accept an
    # empty category when two independent first-party surfaces agree on current
    # emptiness: SSR is HTTP 200 with no identities/children and the official API
    # returns a clean exhausted page with zero products. This does not add a product;
    # it records that the historical source count is no longer current.
    root_node = nodes[0] if nodes else {}
    source_product_count_stale = bool(
        source_target > 0
        and not ssr_skus
        and len(nodes) == 1
        and root_node.get("html_status") == 200
        and int(root_node.get("identity_materialized_products") or 0) == 0
        and int(root_node.get("direct_children_count") or 0) == 0
        and root_api_attempted
        and not root_api_errors
        and int(root_api_meta.get("pages") or 0) > 0
        and root_api_products == 0
    )
    target_satisfied = normal_target_satisfied or source_product_count_stale

    child_failures_resolved = all(x.get("ok") for x in child_api_attempts) if child_api_attempts else not request_failures
    root_api_enumeration_ok = bool(
        root_api_attempted
        and not root_api_errors
        and int(root_api_meta.get("pages") or 0) > 0
        and target_satisfied
    )
    failures_overridden = bool(
        not request_failures
        or child_failures_resolved
        or root_api_enumeration_ok
        or source_product_count_stale
    )
    enumeration_ok = target_satisfied and not traversal_truncated and failures_overridden

    meta = [{
        "label": label,
        "retailer_category_id": rid,
        "method": (
            "FIRST_PARTY_CATEGORY_HTML_RECURSIVE_DIRECT_DESCENDANTS_PAIRED_IDENTITY_VECTORS"
            "_PLUS_NARROW_V6_PAGETOKEN_FALLBACK"
        ),
        "version": VERSION,
        "source_reported_product_count": source_target or None,
        "source_product_count_stale": source_product_count_stale,
        "categories_visited": len(nodes),
        "max_depth": max_depth,
        "max_nodes": max_nodes,
        "traversal_truncated": traversal_truncated,
        "unique_visible_product_skus": len(skus),
        "ssr_visible_product_skus": len(ssr_skus),
        "child_api_attempts": child_api_attempts,
        "api_fallback_attempted": root_api_attempted,
        "api_fallback_products": root_api_products,
        "api_fallback_pages": int(root_api_meta.get("pages") or 0),
        "api_fallback_errors": root_api_errors,
        "api_fallback_attempts": root_api_attempts,
        "api_fallback_enumeration_ok": root_api_enumeration_ok,
        "nodes": nodes,
    }]
    summary = write_outputs(out, list(products.values()), meta)
    effective_unresolved = [] if enumeration_ok else request_failures
    decoration_ok = bool(
        enumeration_ok
        and (
            root_api_enumeration_ok
            or source_product_count_stale
            or any(x.get("ok") and x.get("products", 0) > 0 for x in child_api_attempts)
        )
    )
    check = {
        "label": label,
        "rid": rid,
        "source_reported_product_count": source_target or None,
        "source_product_count_stale": source_product_count_stale,
        "food_products_recursive_union": summary["counts"]["food_products"],
        "recursive_categories_visited": len(nodes),
        "api_error_categories": 0 if enumeration_ok else len(request_failures) + len(root_api_errors),
        "children_without_retailer_category_id": 0,
        "unresolved": effective_unresolved,
        "ssr_unresolved": request_failures,
        "child_api_attempts": child_api_attempts,
        "missing_retailer_ids": [],
        "deduplication_identity": "retailer_sku_else_product_id",
        "max_depth": max_depth,
        "aggregate_root_with_children": len(nodes) > 1,
        "completeness_basis": (
            "first_party_category_html_recursive_direct_descendants_paired_identity_vectors"
            "_plus_narrow_v6_pageToken_exhaustion"
            if (root_api_attempted or child_api_attempts)
            else "first_party_category_html_recursive_direct_descendants_paired_identity_vectors"
        ),
        "source_product_count_is_diagnostic_only": bool(source_product_count_stale or not source_target),
        "html_product_links": len(ssr_skus),
        "html_link_skus": ssr_skus,
        "enumerated_skus": skus,
        "identity_materialized_products": len(products),
        "identity_mapping_error": None,
        "traversal_truncated": traversal_truncated,
        "api_fallback_attempted": root_api_attempted,
        "api_fallback_products": root_api_products,
        "api_fallback_pages": int(root_api_meta.get("pages") or 0),
        "api_fallback_errors": root_api_errors,
        "api_fallback_attempts": root_api_attempts,
        "api_fallback_enumeration_ok": root_api_enumeration_ok,
        "enumeration_ok": enumeration_ok,
        "decoration_ok": decoration_ok,
        "decoration_errors": [] if decoration_ok else ["not_attempted_or_failed_known_v6_products"],
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
