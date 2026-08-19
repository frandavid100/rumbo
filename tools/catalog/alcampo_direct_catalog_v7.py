from __future__ import annotations

import argparse
import concurrent.futures as cf
import http.cookiejar
import json
import time
import urllib.parse
from pathlib import Path
from urllib.request import Request, build_opener, HTTPCookieProcessor

from alcampo_direct_catalog_v6 import (
    BASE, CATALOGUE_ENDPOINT, FOOD_ROOTS, PAGE_SIZE, UA,
    Product, allowed_food, map_product, merge, write_outputs,
)

VERSION = "alcampo-direct-v7.0"


class ApiSession:
    """Keep Alcampo's anonymous session cookies so pageToken remains valid."""
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.jar))

    def json(self, url: str, timeout: int = 90):
        req = Request(url, headers={
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-ES,es;q=0.9",
            "Referer": BASE + "/categories?source=navigation",
            "Cache-Control": "no-cache",
        })
        with self.opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))


def page_url(retailer_category_id: str, page_token: str | None = None) -> str:
    params = [
        ("maxProductsToDecorate", str(PAGE_SIZE)),
        ("maxPageSize", str(PAGE_SIZE)),
        ("includeAdditionalPageInfo", "false" if page_token else "true"),
        ("retailerCategoryId", retailer_category_id),
    ]
    if page_token:
        params.append(("pageToken", page_token))
    return CATALOGUE_ENDPOINT + "?" + urllib.parse.urlencode(params)


def collect_root(label: str, rid: str, max_pages: int = 0) -> tuple[list[Product], dict]:
    session = ApiSession()
    products: dict[str, Product] = {}
    page_token = None
    token_seen = set()
    pages = 0
    errors = []
    child_categories = []
    while True:
        if max_pages and pages >= max_pages:
            break
        try:
            payload = session.json(page_url(rid, page_token))
        except Exception as exc:
            errors.append(f"{type(exc).__name__}:{exc}")
            break
        pages += 1
        if pages == 1:
            info = payload.get("additionalPageInfo") or {}
            for c in info.get("categories") or []:
                if isinstance(c, dict):
                    child_categories.append({k:c.get(k) for k in ("name","categoryId","retailerCategoryId","productCount")})
        decorated = 0
        other_ids = 0
        for group in payload.get("productGroups") or []:
            if not isinstance(group, dict):
                continue
            for raw in group.get("decoratedProducts") or []:
                if not isinstance(raw, dict):
                    continue
                p = map_product(raw, label)
                if not p:
                    continue
                decorated += 1
                if p.product_id in products:
                    products[p.product_id] = merge(products[p.product_id], p)
                else:
                    products[p.product_id] = p
            other_ids += len(group.get("otherProductIds") or [])
        next_token = (payload.get("metadata") or {}).get("nextPageToken")
        print(f"root={rid} page={pages} decorated={decorated} other_ids={other_ids} unique={len(products)} cookies={len(session.jar)} next={bool(next_token)}", flush=True)
        if not next_token or next_token in token_seen:
            break
        token_seen.add(next_token)
        page_token = next_token
        time.sleep(0.08)
    return list(products.values()), {
        "label": label,
        "retailer_category_id": rid,
        "pages": pages,
        "unique_decorated_products": len(products),
        "errors": errors,
        "child_categories": child_categories,
        "pagination_session_cookies": True,
    }


def run(out: Path, only_root: str | None, max_pages: int, workers: int):
    roots = FOOD_ROOTS
    if only_root:
        roots = [x for x in FOOD_ROOTS if x[1] == only_root or x[0].lower() == only_root.lower()]
        if not roots and only_root.startswith("OC"):
            roots = [(only_root, only_root)]
    all_products: dict[str, Product] = {}
    roots_meta = []

    def job(root):
        return root, collect_root(root[0], root[1], max_pages)

    with cf.ThreadPoolExecutor(max_workers=max(1, min(workers, len(roots) or 1))) as ex:
        for (_root, (plist, meta)) in ex.map(job, roots):
            roots_meta.append(meta)
            for p in plist:
                if p.product_id in all_products:
                    all_products[p.product_id] = merge(all_products[p.product_id], p)
                else:
                    all_products[p.product_id] = p

    summary = write_outputs(out, list(all_products.values()), roots_meta)
    summary["importer_version"] = VERSION
    summary["pagination"] = "cookie_bound_pageToken"
    (out/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="alcampo-direct-v7-output")
    ap.add_argument("--only-root")
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--min-products", type=int, default=1)
    args = ap.parse_args()
    summary = run(Path(args.out), args.only_root, args.max_pages, args.workers)
    return 0 if summary["counts"]["food_products"] >= args.min_products else 2


if __name__ == "__main__":
    raise SystemExit(main())
