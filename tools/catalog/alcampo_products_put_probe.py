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

# Product UUIDs observed directly in Alcampo's own category-page network traffic.
DEFAULT_IDS = [
    "f7e44473-e475-4fec-b4c8-86ef9f25a6c0",
    "b78cdfde-5c46-4a95-b6c7-343f7d82685e",
    "b7082ebc-2d4e-4492-8545-54928d0f2356",
    "6cdc0ea8-abe3-4894-b64d-924145a3fa99",
    "de0bdf32-576d-444a-9323-5c3d14ab68f6",
]


def describe(value, depth=0):
    if depth >= 5:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): describe(v, depth+1) for k,v in list(value.items())[:80]}
    if isinstance(value, list):
        return {"type":"list","length":len(value),"sample":describe(value[0],depth+1) if value else None}
    return type(value).__name__


def request(ids: list[str], attempts=10):
    jar=http.cookiejar.CookieJar(); opener=build_opener(HTTPCookieProcessor(jar))
    payload=json.dumps(ids).encode("utf-8")
    last=None
    for attempt in range(1,attempts+1):
        req=Request(ENDPOINT,data=payload,method="PUT",headers={
            "User-Agent":UA,
            "Accept":"application/json; charset=utf-8",
            "Content-Type":"application/json; charset=utf-8",
            "Accept-Language":"es-ES,es;q=0.9",
            "Referer":BASE+"/categories/Alimentaci%C3%B3n/OCC10",
            "Cache-Control":"no-cache",
        })
        try:
            with opener.open(req,timeout=90) as r:
                status=getattr(r,"status",200); raw=r.read()
            text=raw.decode("utf-8",errors="replace")
            if status==202 or not text.strip():
                last={"status":status,"body":""}; time.sleep(min(attempt*0.5,4)); continue
            try: body=json.loads(text)
            except Exception: body=text
            return status,body,len(raw),len(jar)
        except HTTPError as exc:
            try: text=exc.read().decode("utf-8",errors="replace")
            except Exception: text=""
            last={"status":exc.code,"body":text[:1000]}
            if exc.code in (400,408,409,425,429,500,502,503,504):
                time.sleep(min(attempt*0.6,5)); continue
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
        "body":body,
    }
    (a.out/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="body"},ensure_ascii=False,indent=2))
    return 0 if status==200 else 2

if __name__=="__main__": raise SystemExit(main())
