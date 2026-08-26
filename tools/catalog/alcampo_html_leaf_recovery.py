from __future__ import annotations

import argparse
import html as htmlmod
import http.cookiejar
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor

from alcampo_direct_catalog_v6 import BASE, UA, Product, map_product, merge, write_outputs

PRODUCTS_ENDPOINT = BASE + "/api/webproductpagews/v6/products"
PRODUCT_ID_RE = re.compile(r'["\']productId["\']\s*:\s*["\']([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})["\']', re.I)
RETAILER_ID_RE = re.compile(r'["\']retailerProductId["\']\s*:\s*["\']?([^"\',}\s]+)', re.I)
PRODUCT_LINK_RE = re.compile(r'href=["\']([^"\']*/products/[^"\']+/(\d{3,}))["\']', re.I)
VERSION = "alcampo-html-leaf-recovery-v3"


def request_html(opener, rid: str):
    url = f"{BASE}/categories/~/{rid}"
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "es-ES,es;q=0.9",
        "Cache-Control": "no-cache",
        "Referer": BASE + "/categories?source=navigation",
    })
    with opener.open(req, timeout=90) as r:
        status = getattr(r, "status", 200)
        final = r.geturl()
        raw = r.read()
    return status, final, raw.decode("utf-8", errors="replace"), len(raw)


def put_products(opener, ids: list[str], referer: str, attempts: int = 4):
    payload = json.dumps(ids).encode("utf-8")
    last = None
    for attempt in range(1, attempts + 1):
        req = Request(PRODUCTS_ENDPOINT, data=payload, method="PUT", headers={
            "User-Agent": UA,
            "Accept": "application/json; charset=utf-8",
            "Content-Type": "application/json; charset=utf-8",
            "Accept-Language": "es-ES,es;q=0.9",
            "Referer": referer,
            "Cache-Control": "no-cache",
        })
        try:
            with opener.open(req, timeout=90) as r:
                status = getattr(r, "status", 200)
                body = r.read().decode("utf-8", errors="replace")
            if status == 202 or not body.strip():
                last = f"pending:{status}"
                time.sleep(0.4 * attempt)
                continue
            return json.loads(body)
        except HTTPError as exc:
            try:
                preview = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                preview = ""
            last = f"HTTP_{exc.code}:{preview}"
            if exc.code in (400, 405, 408, 409, 425, 429, 500, 502, 503, 504) and attempt < attempts:
                time.sleep(0.5 * attempt)
                continue
            break
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = f"{type(exc).__name__}:{exc}"
            if attempt < attempts:
                time.sleep(0.5 * attempt)
                continue
            break
    raise RuntimeError(last or "PUT product decoration failed")


def materialize_visible_identities(
    label: str,
    final_url: str,
    product_ids: list[str],
    retailer_ids: list[str],
    links: list[tuple[str, str]],
) -> tuple[dict[str, Product], str | None]:
    """Materialize only identity fields proven by one-to-one SSR ordering.

    Alcampo's category SSR repeats productId, retailerProductId and product links in
    the same product-card order. Historical probes confirmed exact one-to-one order
    on independent categories. We still fail closed: if any count/order/uniqueness
    invariant differs, no identity row is emitted rather than guessing a pairing.
    """
    link_skus = list(dict.fromkeys(sku for _, sku in links))
    link_by_sku = {sku: href for href, sku in links}
    if not product_ids or not retailer_ids or not link_skus:
        return {}, "missing_identity_vector"
    if not (len(product_ids) == len(retailer_ids) == len(link_skus)):
        return {}, f"identity_vector_count_mismatch:{len(product_ids)}:{len(retailer_ids)}:{len(link_skus)}"
    if retailer_ids != link_skus:
        return {}, "retailer_id_link_sku_order_mismatch"
    if len(set(product_ids)) != len(product_ids) or len(set(retailer_ids)) != len(retailer_ids):
        return {}, "identity_vector_not_unique"

    products: dict[str, Product] = {}
    for product_id, sku in zip(product_ids, retailer_ids):
        href = link_by_sku.get(sku)
        if not href:
            return {}, f"missing_product_link_for_sku:{sku}"
        p = Product(
            product_id=product_id,
            sku=sku,
            name=None,
            brand=None,
            pack_size=None,
            category_path=[label],
            alcohol=None,
            available=None,
            image_url=None,
            product_url=BASE + htmlmod.unescape(href),
            price_eur=None,
            unit_price_eur=None,
            unit_price_unit=None,
            source_roots=[label],
            evidence_endpoint=final_url,
        )
        products[f"sku:{sku}"] = p
    return products, None


def recover(label: str, rid: str, out: Path, expected: int | None = None):
    out.mkdir(parents=True, exist_ok=True)
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    decoration_errors = []
    try:
        status, final_url, body, body_bytes = request_html(opener, rid)
    except Exception as exc:
        status = None
        final_url = f"{BASE}/categories/~/{rid}"
        body = ""
        body_bytes = 0
        decoration_errors.append(f"HTML:{type(exc).__name__}:{exc}")

    product_ids = list(dict.fromkeys(PRODUCT_ID_RE.findall(body)))
    retailer_ids = list(dict.fromkeys(RETAILER_ID_RE.findall(body)))
    links = PRODUCT_LINK_RE.findall(body)
    link_skus = list(dict.fromkeys(sku for _, sku in links))
    link_by_sku = {sku: urllib for urllib, sku in links}

    # The SSR category page is itself first-party enumeration evidence. Do not make
    # enumeration completeness depend on the separate product-decoration endpoint:
    # Alcampo currently serves many leaf pages as HTTP 200 with all visible product
    # links/retailer IDs while the v6 /products PUT is WAF-blocked (403).
    source_target = int(expected or 0)
    observed_target = max(len(product_ids), len(retailer_ids), len(link_skus))
    target = source_target if source_target > 0 else observed_target
    required = max(1, int(target * 0.95)) if target else 1
    overlap = len(set(link_skus) & set(retailer_ids)) if retailer_ids else len(link_skus)
    enumeration_ok = (
        status == 200
        and len(link_skus) >= required
        and overlap >= min(required, len(link_skus))
    )

    # Materialize the identity that the SSR itself proves, even if the optional
    # detail-decoration PUT is WAF-blocked. This is deliberately fail-closed: only
    # exact one-to-one productId/SKU/link vectors become Product rows.
    products, identity_mapping_error = materialize_visible_identities(
        label, final_url, product_ids, retailer_ids, links
    )
    identity_materialized = len(products)

    # Decoration remains useful when it works because it supplies structured fields,
    # but a decoration 403 must not erase valid first-party enumeration evidence.
    decorated_keys: set[str] = set()
    for start in range(0, len(product_ids), 40):
        chunk = product_ids[start:start + 40]
        try:
            payload = put_products(opener, chunk, final_url)
        except Exception as exc:
            decoration_errors.append(f"PUT[{start}:{start+len(chunk)}]:{type(exc).__name__}:{exc}")
            continue
        raw_products = payload.get("products") if isinstance(payload, dict) else None
        if not isinstance(raw_products, list):
            decoration_errors.append(f"PUT[{start}:{start+len(chunk)}]:missing_products_array")
            continue
        for raw in raw_products:
            if not isinstance(raw, dict):
                continue
            p = map_product(raw, label)
            if not p:
                continue
            if p.sku and p.sku in link_by_sku:
                p.product_url = BASE + htmlmod.unescape(link_by_sku[p.sku])
            key = f"sku:{p.sku}" if p.sku else f"product:{p.product_id}"
            products[key] = merge(products[key], p) if key in products else p
            decorated_keys.add(key)

    meta = [{
        "label": label,
        "retailer_category_id": rid,
        "method": "FIRST_PARTY_CATEGORY_HTML_VISIBLE_LINKS_IDENTITY_PLUS_OPTIONAL_V6_PRODUCTS_DECORATION",
        "requested_url": f"{BASE}/categories/~/{rid}",
        "final_url": final_url,
        "html_status": status,
        "html_bytes": body_bytes,
        "source_reported_product_count": source_target or None,
        "html_product_ids": len(product_ids),
        "html_retailer_product_ids": len(retailer_ids),
        "html_product_links": len(link_skus),
        "html_link_skus": link_skus,
        "html_retailer_ids": retailer_ids,
        "visible_id_overlap": overlap,
        "identity_materialized_products": identity_materialized,
        "identity_mapping_error": identity_mapping_error,
        "enumeration_ok": enumeration_ok,
        "decorated_products": len(decorated_keys),
        "decoration_errors": decoration_errors,
    }]
    summary = write_outputs(out, list(products.values()), meta)
    recovered = summary["counts"]["food_products"]
    decoration_ok = not decoration_errors and len(decorated_keys) >= max(1, int(observed_target * 0.95)) if observed_target else False

    check = {
        "label": label,
        "rid": rid,
        "source_reported_product_count": source_target or None,
        "food_products_recursive_union": recovered,
        "recursive_categories_visited": 1,
        "api_error_categories": 0 if enumeration_ok else 1,
        "children_without_retailer_category_id": 0,
        "unresolved": [] if enumeration_ok else meta,
        "missing_retailer_ids": [],
        "deduplication_identity": "retailer_sku_else_product_id",
        "max_depth": 0,
        "aggregate_root_with_children": False,
        "completeness_basis": "first_party_category_html_visible_links",
        "source_product_count_is_diagnostic_only": False if source_target else True,
        "html_product_links": len(link_skus),
        "html_product_ids": len(product_ids),
        "html_retailer_product_ids": len(retailer_ids),
        "html_link_skus": link_skus,
        "identity_materialized_products": identity_materialized,
        "identity_mapping_error": identity_mapping_error,
        "enumeration_ok": enumeration_ok,
        "decoration_ok": decoration_ok,
        "decoration_errors": decoration_errors,
        # Backward-compatible meaning for recovery enumeration workflows.
        "ok": enumeration_ok,
    }
    (out / "child_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "category_html_recovery.json").write_text(json.dumps(meta[0], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(check, ensure_ascii=False, indent=2))
    return 0 if enumeration_ok else 2


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--rid", required=True)
    p.add_argument("--expected", type=int)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    return recover(a.label, a.rid, a.out, a.expected)


if __name__ == "__main__":
    raise SystemExit(main())
