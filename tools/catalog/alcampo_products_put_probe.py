from __future__ import annotations

import argparse
import http.cookiejar
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor

BASE = "https://www.compraonline.alcampo.es"
ENDPOINT = BASE + "/api/webproductpagews/v6/products"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36"

# This UUID was observed directly while Alcampo rendered SKU 522881
# (ALCAMPO ECOLÓGICO tofu 2 x 200 g) on its own product page. Keep a few
# category-observed UUIDs as secondary samples to learn whether response shape
# varies by product type.
DEFAULT_IDS = [
    "2f4e38b2-74bf-42d9-a20d-d3512ce7614c",
    "f7e44473-e475-4fec-b4c8-86ef9f25a6c0",
    "b78cdfde-5c46-4a95-b6c7-343f7d82685e",
    "b7082ebc-2d4e-4492-8545-54928d0f2356",
    "6cdc0ea8-abe3-4894-b64d-924145a3fa99",
]

INTERESTING_KEY_FRAGMENTS = (
    "nutrition", "nutrient", "ingredient", "legal", "denomination", "gtin",
    "ean", "barcode", "retailerproduct", "productid", "name", "brand", "pack",
)


def describe(value, depth=0):
    if depth >= 6:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): describe(v, depth+1) for k,v in list(value.items())[:120]}
    if isinstance(value, list):
        return {"type":"list","length":len(value),"sample":describe(value[0],depth+1) if value else None}
    return type(value).__name__


def interesting_paths(value, path="$", depth=0, out=None):
    if out is None:
        out=[]
    if depth > 9 or len(out) >= 500:
        return out
    if isinstance(value, dict):
        for key, child in value.items():
            p=f"{path}.{key}"
            if any(fragment in str(key).lower() for fragment in INTERESTING_KEY_FRAGMENTS):
                preview=child
                if isinstance(preview,(dict,list)):
                    preview=describe(preview,0)
                out.append({"path":p,"value":preview})
            interesting_paths(child,p,depth+1,out)
    elif isinstance(value,list):
        for i,child in enumerate(value[:20]):
            interesting_paths(child,f"{path}[{i}]",depth+1,out)
    return out


def request(ids: list[str], attempts=16):
    jar=http.cookiejar.CookieJar(); opener=build_opener(HTTPCookieProcessor(jar))
    payload=json.dumps(ids).encode("utf-8")
    last=None
    for attempt in range(1,attempts+1):
        req=Request(ENDPOINT,data=payload,method="PUT",headers={
            "User-Agent":UA,
            "Accept":"application/json; charset=utf-8",
            "Content-Type":"application/json; charset=utf-8",
            "Accept-Language":"es-ES,es;q=0.9",
            "Referer":BASE+"/products/x/522881",
            "Cache-Control":"no-cache",
        })
        try:
            with opener.open(req,timeout=90) as r:
                status=getattr(r,"status",200); raw=r.read()
            text=raw.decode("utf-8",errors="replace")
            if status==202 or not text.strip():
                last={"status":status,"body":""}; time.sleep(min(attempt*0.7,6)); continue
            try: body=json.loads(text)
            except Exception: body=text
            return status,body,len(raw),len(jar)
        except HTTPError as exc:
            try: text=exc.read().decode("utf-8",errors="replace")
            except Exception: text=""
            last={"status":exc.code,"body":text[:1000]}
            if exc.code in (400,408,409,425,429,500,502,503,504):
                time.sleep(min(attempt*0.8,7)); continue
            break
    raise RuntimeError(f"PUT probe failed: {last}")


def main():
    p=argparse.ArgumentParser(); p.add_argument("--out",type=Path,default=Path("alcampo-products-put-probe")); p.add_argument("--id",action="append",default=[])
    a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    ids=a.id or DEFAULT_IDS
    status,body,nbytes,cookies=request(ids)
    result={
        "source":ENDPOINT,
        "method":"PUT",
        "requested_product_ids":ids,
        "status":status,
        "body_bytes":nbytes,
        "cookies":cookies,
        "shape":describe(body),
        "interesting_paths":interesting_paths(body),
        "body":body,
    }
    (a.out/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="body"},ensure_ascii=False,indent=2))
    return 0 if status==200 else 2

if __name__=="__main__": raise SystemExit(main())
