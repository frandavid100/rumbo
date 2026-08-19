from __future__ import annotations

import argparse
import concurrent.futures as cf
import http.cookiejar
import json
import time
import urllib.parse
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor

from alcampo_direct_catalog_v6 import (
    BASE, CATALOGUE_ENDPOINT, FOOD_ROOTS, PAGE_SIZE, UA,
    Product, map_product, merge, write_outputs,
)

VERSION = "alcampo-direct-v8.1"


class ApiSession:
    """Anonymous Alcampo session with retries for asynchronously prepared catalogue pages."""
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.jar))

    def json(self, url: str, timeout: int = 90, attempts: int = 20):
        last = None
        for attempt in range(1, attempts + 1):
            req = Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "es-ES,es;q=0.9",
                "Referer": BASE + "/categories?source=navigation",
                "Cache-Control": "no-cache",
            })
            try:
                with self.opener.open(req, timeout=timeout) as r:
                    status = getattr(r, "status", 200)
                    body = r.read().decode("utf-8", errors="replace")
                # The service uses 202/empty while a pageToken result is being prepared.
                # Keep the same cookie-bound session and token long enough for the async
                # catalogue page to materialise before abandoning the category attempt.
                if status == 202 or not body.strip():
                    last = RuntimeError(f"catalogue page pending status={status}")
                    time.sleep(min(0.35 * attempt, 3.0))
                    continue
                try:
                    return json.loads(body)
                except json.JSONDecodeError as exc:
                    last = RuntimeError(f"invalid JSON status={status} preview={body[:240]!r}: {exc}")
                    time.sleep(min(0.35 * attempt, 3.0))
                    continue
            except HTTPError as exc:
                try: body = exc.read().decode("utf-8", errors="replace")
                except Exception: body = ""
                last = RuntimeError(f"HTTP {exc.code}: {body[:400]}")
                if exc.code in (400, 408, 409, 425, 429, 500, 502, 503, 504):
                    time.sleep(min(0.45 * attempt, 4.0))
                    continue
                raise
            except (URLError, TimeoutError) as exc:
                last = exc
                time.sleep(min(0.45 * attempt, 4.0))
                continue
        raise last or RuntimeError("catalogue request failed")


def page_url(rid: str, token: str | None = None) -> str:
    params = [
        ("maxProductsToDecorate", str(PAGE_SIZE)),
        ("maxPageSize", str(PAGE_SIZE)),
        ("includeAdditionalPageInfo", "false" if token else "true"),
        ("retailerCategoryId", rid),
    ]
    if token: params.append(("pageToken", token))
    return CATALOGUE_ENDPOINT + "?" + urllib.parse.urlencode(params)


def collect_root(label: str, rid: str, max_pages: int = 0):
    session = ApiSession(); products: dict[str, Product] = {}; pages = 0; token = None; token_seen=set(); errors=[]; children=[]
    while True:
        if max_pages and pages >= max_pages: break
        try:
            payload = session.json(page_url(rid, token))
        except Exception as exc:
            errors.append(f"{type(exc).__name__}:{exc}"); break
        pages += 1
        if pages == 1:
            for c in (payload.get("additionalPageInfo") or {}).get("categories") or []:
                if isinstance(c, dict): children.append({k:c.get(k) for k in ("name","categoryId","retailerCategoryId","productCount")})
        decorated=0; other=0
        for group in payload.get("productGroups") or []:
            if not isinstance(group, dict): continue
            for raw in group.get("decoratedProducts") or []:
                if not isinstance(raw, dict): continue
                p=map_product(raw,label)
                if not p: continue
                decorated += 1
                products[p.product_id] = merge(products[p.product_id],p) if p.product_id in products else p
            other += len(group.get("otherProductIds") or [])
        nxt=(payload.get("metadata") or {}).get("nextPageToken")
        print(f"root={rid} page={pages} decorated={decorated} other={other} unique={len(products)} cookies={len(session.jar)} next={bool(nxt)}",flush=True)
        if not nxt or nxt in token_seen: break
        token_seen.add(nxt); token=nxt; time.sleep(0.12)
    return list(products.values()), {"label":label,"retailer_category_id":rid,"pages":pages,"unique_decorated_products":len(products),"errors":errors,"child_categories":children,"pagination_session_cookies":True,"pending_page_retries":True}


def run(out: Path, only_root: str | None, max_pages: int, workers: int):
    roots=FOOD_ROOTS
    if only_root:
        roots=[x for x in roots if x[1]==only_root or x[0].lower()==only_root.lower()]
        if not roots and only_root.startswith("OC"): roots=[(only_root,only_root)]
    all_products: dict[str,Product]={}; metas=[]
    def job(x): return x,collect_root(x[0],x[1],max_pages)
    with cf.ThreadPoolExecutor(max_workers=max(1,min(workers,len(roots) or 1))) as ex:
        for _,(plist,meta) in ex.map(job,roots):
            metas.append(meta)
            for p in plist: all_products[p.product_id]=merge(all_products[p.product_id],p) if p.product_id in all_products else p
    summary=write_outputs(out,list(all_products.values()),metas)
    summary["importer_version"]=VERSION; summary["pagination"]="cookie_bound_pageToken_with_202_retry"
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    return summary


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",default="alcampo-direct-v8-output"); ap.add_argument("--only-root"); ap.add_argument("--max-pages",type=int,default=0); ap.add_argument("--workers",type=int,default=1); ap.add_argument("--min-products",type=int,default=1)
    a=ap.parse_args(); s=run(Path(a.out),a.only_root,a.max_pages,a.workers); return 0 if s["counts"]["food_products"]>=a.min_products else 2
if __name__=="__main__": raise SystemExit(main())
