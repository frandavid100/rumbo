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
VERSION = "alcampo-html-leaf-recovery-v1"


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


def recover(label: str, rid: str, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    errors = []
    try:
        status, final_url, body, body_bytes = request_html(opener, rid)
    except Exception as exc:
        status = None
        final_url = f"{BASE}/categories/~/{rid}"
        body = ""
        body_bytes = 0
        errors.append(f"HTML:{type(exc).__name__}:{exc}")

    product_ids = list(dict.fromkeys(PRODUCT_ID_RE.findall(body)))
    retailer_ids = list(dict.fromkeys(RETAILER_ID_RE.findall(body)))
    links = PRODUCT_LINK_RE.findall(body)
    link_skus = list(dict.fromkeys(sku for _, sku in links))
    link_by_sku = {sku: urllib for urllib, sku in links}

    # On Alcampo category SSR the productId/retailerProductId sequences represent
    # the actual listing cards; unrelated recommendation UUIDs do not use these keys.
    products: dict[str, Product] = {}
    for start in range(0, len(product_ids), 40):
        chunk = product_ids[start:start + 40]
        try:
            payload = put_products(opener, chunk, final_url)
        except Exception as exc:
            errors.append(f"PUT[{start}:{start+len(chunk)}]:{type(exc).__name__}:{exc}")
            continue
        raw_products = payload.get("products") if isinstance(payload, dict) else None
        if not isinstance(raw_products, list):
            errors.append(f"PUT[{start}:{start+len(chunk)}]:missing_products_array")
            continue
        for raw in raw_products:
            if not isinstance(raw, dict):
                continue
            p = map_product(raw, label)
            if not p:
                continue
            # Preserve the exact canonical link visible in the first-party category
            # page when available; listing data from another retailer is never used.
            if p.sku and p.sku in link_by_sku:
                p.product_url = BASE + htmlmod.unescape(link_by_sku[p.sku])
            key = f"sku:{p.sku}" if p.sku else f"product:{p.product_id}"
            products[key] = merge(products[key], p) if key in products else p

    meta = [{
        "label": label,
        "retailer_category_id": rid,
        "method": "FIRST_PARTY_CATEGORY_HTML_PLUS_FIRST_PARTY_V6_PRODUCTS_PUT",
        "requested_url": f"{BASE}/categories/~/{rid}",
        "final_url": final_url,
        "html_status": status,
        "html_bytes": body_bytes,
        "html_product_ids": len(product_ids),
        "html_retailer_product_ids": len(retailer_ids),
        "html_product_links": len(link_skus),
        "decorated_products": len(products),
        "errors": errors,
    }]
    summary = write_outputs(out, list(products.values()), meta)
    target = max(len(product_ids), len(retailer_ids), len(link_skus))
    recovered = summary["counts"]["food_products"]
    # Exact equality is expected for normal leaf pages. Allow a tiny difference for
    # alcohol/non-food filtering performed by write_outputs, but never claim complete
    # when the structured decoration API failed materially.
    required = max(1, int(target * 0.95)) if target else 1
    ok = status == 200 and not errors and recovered >= required
    check = {
        "label": label,
        "rid": rid,
        "source_reported_product_count": target,
        "food_products_recursive_union": recovered,
        "recursive_categories_visited": 1,
        "api_error_categories": 0 if ok else 1,
        "children_without_retailer_category_id": 0,
        "unresolved": [] if ok else meta,
        "missing_retailer_ids": [],
        "deduplication_identity": "retailer_sku_else_product_id",
        "max_depth": 0,
        "aggregate_root_with_children": False,
        "completeness_basis": "first_party_category_html_visible_cards_plus_v6_products_put",
        "source_product_count_is_diagnostic_only": True,
        "html_product_links": len(link_skus),
        "html_product_ids": len(product_ids),
        "ok": ok,
    }
    (out / "child_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "category_html_recovery.json").write_text(json.dumps(meta[0], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(check, ensure_ascii=False, indent=2))
    return 0 if ok else 2


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--rid", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    return recover(a.label, a.rid, a.out)


if __name__ == "__main__":
    raise SystemExit(main())
