from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor
import http.cookiejar

BASE = "https://www.compraonline.alcampo.es"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36"
DEFAULT_RIDS = ["OC23015", "OC120805", "OC170103"]

PRODUCT_LINK = re.compile(r'href=["\']([^"\']*/products/[^"\']+)["\']', re.I)
SKU_LINK = re.compile(r'/products/[^"\'?#]+/(\d{3,})\b', re.I)
UUID = re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b', re.I)
RETAILER_SKU = re.compile(r'["\']retailerProductId["\']\s*:\s*["\']?([^"\',}\s]+)', re.I)
PRODUCT_ID = re.compile(r'["\']productId["\']\s*:\s*["\']([^"\']+)', re.I)


def fetch(rid: str):
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    url = f"{BASE}/categories/~/{rid}"
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "es-ES,es;q=0.9",
        "Cache-Control": "no-cache",
        "Referer": BASE + "/categories?source=navigation",
    })
    try:
        with opener.open(req, timeout=90) as r:
            status = getattr(r, "status", 200)
            final = r.geturl()
            raw = r.read()
    except HTTPError as exc:
        raw = exc.read()
        status = exc.code
        final = exc.geturl()
    body = raw.decode("utf-8", errors="replace")
    links = list(dict.fromkeys(PRODUCT_LINK.findall(body)))
    skus = list(dict.fromkeys(SKU_LINK.findall(body)))
    retailer = list(dict.fromkeys(RETAILER_SKU.findall(body)))
    product_ids = list(dict.fromkeys(PRODUCT_ID.findall(body)))
    return {
        "rid": rid,
        "requested_url": url,
        "status": status,
        "final_url": final,
        "body_bytes": len(raw),
        "cookies": len(jar),
        "has_goku_props": "window.gokuProps" in body,
        "product_link_count": len(links),
        "product_link_sample": links[:20],
        "sku_from_links_count": len(skus),
        "sku_from_links_sample": skus[:30],
        "retailer_product_id_count": len(retailer),
        "retailer_product_id_sample": retailer[:30],
        "product_id_count": len(product_ids),
        "product_id_sample": product_ids[:20],
        "uuid_count": len(set(UUID.findall(body))),
        "body_prefix": body[:1000],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rid", action="append", default=[])
    p.add_argument("--out", type=Path, default=Path("alcampo-category-html-probe"))
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rows = [fetch(rid) for rid in (a.rid or DEFAULT_RIDS)]
    (a.out / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0 if any(r["status"] == 200 and (r["product_link_count"] or r["retailer_product_id_count"]) for r in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
