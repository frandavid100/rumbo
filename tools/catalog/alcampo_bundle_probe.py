from __future__ import annotations

import json, re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin

BASE = "https://www.compraonline.alcampo.es"
TARGET = BASE + "/categories/alimentaci%C3%B3n/conservas-de-pescado/OC100402?sortBy=favorite"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36"
TERMS = re.compile(r"nextPageToken|pageToken|retailerId|categoryId|catalogue|product-list|productList|pageSize|/api/|webproductpagews|search/v|browse|listing", re.I)
URL_RE = re.compile(r"[\"']([^\"']+\.js(?:\?[^\"']*)?)[\"']")


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA, "Accept-Language":"es-ES,es;q=0.9", "Accept":"*/*"})
    with urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")


def contexts(text: str, radius: int = 700) -> list[str]:
    out=[]
    for m in TERMS.finditer(text):
        a=max(0,m.start()-radius); b=min(len(text),m.end()+radius)
        out.append(text[a:b])
    # stable de-dup
    seen=set(); ded=[]
    for s in out:
        if s not in seen:
            seen.add(s); ded.append(s)
    return ded


def main() -> int:
    out=Path("alcampo-bundle-probe"); out.mkdir(exist_ok=True)
    html=fetch(TARGET)
    srcs=[]
    for s in URL_RE.findall(html):
        u=urljoin(TARGET,s)
        if u.startswith(BASE) and "/static/" in u and u not in srcs:
            srcs.append(u)
    # Known bundle observed by the first network probe; include even if lazy-loaded.
    known = BASE + "/static/catalogue-page-product-list-B2Sggq3G.js"
    if known not in srcs: srcs.append(known)
    results=[]
    for i,u in enumerate(srcs):
        try:
            js=fetch(u)
            ctx=contexts(js)
            if ctx:
                results.append({"url":u,"length":len(js),"contexts":ctx[:100]})
                print(f"MATCH {u} len={len(js)} contexts={len(ctx)}", flush=True)
        except Exception as exc:
            results.append({"url":u,"error":f"{type(exc).__name__}:{exc}"})
    payload={"target":TARGET,"scripts_seen":len(srcs),"matched_bundles":sum('contexts' in x for x in results),"results":results}
    (out/"summary.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:payload[k] for k in ('scripts_seen','matched_bundles')},indent=2))
    return 0 if any('contexts' in x for x in results) else 2

if __name__ == "__main__":
    raise SystemExit(main())
