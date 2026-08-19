from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://www.compraonline.alcampo.es"
ENDPOINT = BASE + "/api/webproductpagews/v6/product-pages"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36"
CATEGORY = "OC100402"  # Conservas de pescado; retailer category id from official URL.


def get(url: str) -> tuple[int, str, str]:
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9",
        "Referer": BASE + "/categories/alimentaci%C3%B3n/conservas-de-pescado/OC100402?sortBy=favorite",
    })
    try:
        with urlopen(req, timeout=45) as r:
            return r.status, r.headers.get("content-type", ""), r.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, e.headers.get("content-type", ""), body
    except URLError as e:
        return 0, "", repr(e)


def shape(obj):
    if isinstance(obj, dict):
        return {k: shape(v) for k, v in list(obj.items())[:30] if k in (
            "metadata","nextPageToken","additionalPageInfo","productGroups","totalProducts","categoryId","retailerCategoryId",
            "decoratedProducts","otherProductIds","products","categories","breadcrumb","sortOptions"
        )}
    if isinstance(obj, list):
        return [shape(x) for x in obj[:3]]
    return obj


def count_products(obj) -> int:
    total = 0
    if isinstance(obj, dict):
        for k,v in obj.items():
            if k in ("decoratedProducts","otherProductIds","products") and isinstance(v,list): total += len(v)
            else: total += count_products(v)
    elif isinstance(obj,list):
        for v in obj: total += count_products(v)
    return total


def main() -> int:
    out = Path("alcampo-api-probe"); out.mkdir(exist_ok=True)
    base_params = [
        ("maxProductsToDecorate", "300"),
        ("maxPageSize", "300"),
        ("includeAdditionalPageInfo", "true"),
        ("retailerCategoryId", CATEGORY),
    ]
    variants = {
        "minimal": base_params,
        "tag_repeat": base_params + [("tag","web"),("tag","category-item")],
        "tag_indices": base_params + [("tag[0]","web"),("tag[1]","category-item")],
        "tag_comma": base_params + [("tag","web,category-item")],
        "decorate_100": [("maxProductsToDecorate","100"),("maxPageSize","300"),("includeAdditionalPageInfo","true"),("retailerCategoryId",CATEGORY)],
        "decorate_20": [("maxProductsToDecorate","20"),("maxPageSize","300"),("includeAdditionalPageInfo","true"),("retailerCategoryId",CATEGORY)],
        "no_decorate": [("maxProductsToDecorate","0"),("maxPageSize","300"),("includeAdditionalPageInfo","true"),("retailerCategoryId",CATEGORY)],
    }
    results=[]
    success=False
    for name, params in variants.items():
        qs = urllib.parse.urlencode(params, doseq=True)
        url = ENDPOINT + "?" + qs
        status, ct, body = get(url)
        row={"variant":name,"url":url,"status":status,"content_type":ct,"body_length":len(body)}
        try:
            obj=json.loads(body)
            row["json_type"]=type(obj).__name__
            row["shape"]=shape(obj)
            row["approx_product_mentions"]=count_products(obj)
            row["top_keys"]=list(obj.keys()) if isinstance(obj,dict) else None
            if status==200 and isinstance(obj,dict) and ("productGroups" in obj or "metadata" in obj or "additionalPageInfo" in obj): success=True
        except Exception:
            row["body_preview"]=body[:3000]
        results.append(row)
        print(json.dumps({k:row.get(k) for k in ("variant","status","content_type","body_length","top_keys","approx_product_mentions")},ensure_ascii=False),flush=True)
    payload={"endpoint":ENDPOINT,"category":CATEGORY,"success":success,"results":results}
    (out/"summary.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    return 0 if success else 2

if __name__ == "__main__":
    raise SystemExit(main())
