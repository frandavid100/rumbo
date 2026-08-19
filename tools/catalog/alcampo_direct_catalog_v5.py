from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from playwright.async_api import async_playwright

from alcampo_direct_catalog_v4 import (
    BASE, ROOT, UA, DENY, FOOD_ROOT_TERMS, Product, parse_detail, write_outputs, sku_from_url
)

VERSION = "alcampo-direct-v5.0"


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self._href=None; self._text=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=="a":
            self._href=dict(attrs).get("href"); self._text=[]
    def handle_data(self, data):
        if self._href is not None: self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower()=="a" and self._href is not None:
            self.links.append((" ".join(self._text).strip(), self._href)); self._href=None; self._text=[]


def requote_url(url: str) -> str:
    p=urlsplit(url)
    path=quote(unquote(p.path),safe="/%:@")
    query=quote(unquote(p.query),safe="=&%:+,;@")
    return urlunsplit((p.scheme,p.netloc,path,query,p.fragment))


def fetch_html(url: str, attempts: int = 4, timeout: int = 45) -> str:
    last=None
    target=requote_url(url)
    for i in range(attempts):
        try:
            req=Request(target,headers={
                "User-Agent":UA,
                "Accept-Language":"es-ES,es;q=0.9",
                "Accept":"text/html,application/xhtml+xml",
                "Cache-Control":"no-cache",
            })
            with urlopen(req,timeout=timeout) as r:
                raw=r.read().decode("utf-8",errors="replace")
            # Alcampo occasionally returns a tiny application shell/error page. Retry it.
            if "/categories/" in target and len(raw)<30000 and i+1<attempts:
                time.sleep(0.7*(i+1)); continue
            return raw
        except Exception as exc:
            last=exc
            if i+1<attempts: time.sleep(0.7*(i+1))
    raise last


def extract_links(raw: str, base: str):
    p=Links(); p.feed(raw); out=[]
    for text,href in p.links:
        if not href: continue
        u=urljoin(base,html.unescape(href)).split("#")[0]
        if urlparse(u).netloc!=urlparse(BASE).netloc: continue
        text=re.sub(r"\s+"," ",html.unescape(text)).strip()
        out.append((text,u))
    return out


def category_root_slug(url: str) -> str | None:
    path=unquote(urlparse(url).path)
    m=re.match(r"/categories/([^/]+)",path,re.I)
    return m.group(1).lower() if m else None


def server_discover(max_categories: int = 1200) -> tuple[list[Product], dict]:
    root_raw=fetch_html(ROOT)
    root_links=extract_links(root_raw,ROOT)
    seeds=[]
    for text,u in root_links:
        if "/categories/" not in u: continue
        hay=unquote((text+" "+u).lower())
        if any(t in hay for t in FOOD_ROOT_TERMS) and not DENY.search(hay):
            seeds.append((u.split("?")[0].rstrip("/"),text or u))
    if not seeds:
        seeds=[
            (BASE+"/categories/frescos/OC2112","Frescos"),
            (BASE+"/categories/leche-huevos-l%C3%A1cteos-yogures-y-bebidas-vegetales/OC16","Leche, Huevos, Lácteos, Yogures y Bebidas vegetales"),
            (BASE+"/categories/alimentaci%C3%B3n/OCC10","Alimentación"),
            (BASE+"/categories/desayuno-y-merienda/OC10","Desayuno y Merienda"),
            (BASE+"/categories/congelados/OC200220183","Congelados"),
            (BASE+"/categories/comida-preparada/OC20022018","Comida Preparada"),
            (BASE+"/categories/supermercado-ecol%C3%B3gico/OC26112021","Supermercado Ecológico"),
            (BASE+"/categories/bebidas/OCC11","Bebidas"),
            (BASE+"/categories/sin-gluten-sin-lactosa-nutrici%C3%B3n-deportiva-y-funcional/OCSINGSINL","Sin Gluten / Sin Lactosa, Nutrición deportiva y Funcional"),
            (BASE+"/categories/veganos/OC09112021","Veganos"),
        ]
    # Only descend inside the selected food root slugs. This avoids menu links into non-food departments.
    allowed_roots={category_root_slug(u) for u,_ in seeds}
    allowed_roots.discard(None)
    queue=list(dict.fromkeys(seeds)); seen={}; products={}; errors=[]; tiny_pages=0
    while queue and len(seen)<max_categories:
        url,label=queue.pop(0); url=url.split("?")[0].rstrip("/")
        if url in seen: continue
        if category_root_slug(url) not in allowed_roots: continue
        hay=unquote((label+" "+url).lower())
        if DENY.search(hay): continue
        seen[url]=label
        try:
            raw=fetch_html(url)
            if len(raw)<30000: tiny_pages+=1
        except Exception as exc:
            errors.append([url,f"{type(exc).__name__}:{exc}"]); continue
        for text,u in extract_links(raw,url):
            u0=u.split("?")[0].rstrip("/"); ctx=unquote((text+" "+u0).lower())
            if DENY.search(ctx): continue
            sku=sku_from_url(u0)
            if sku:
                p=products.setdefault(sku,Product(sku=sku,url=u0,name=text or None,category=label))
                p.url=p.url or u0; p.name=p.name or text or None; p.category=p.category or label
            elif "/categories/" in u0 and category_root_slug(u0) in allowed_roots and u0 not in seen:
                queue.append((u0,text or label))
        if len(seen)%25==0:
            print(f"discovery categories={len(seen)} products={len(products)} queue={len(queue)} errors={len(errors)}",flush=True)
        time.sleep(.015)
    plist=sorted(products.values(),key=lambda p:int(p.sku) if p.sku.isdigit() else p.sku)
    meta={
        "root":ROOT,"seed_categories":len(seeds),"food_root_slugs":sorted(allowed_roots),
        "categories_visited":len(seen),"category_errors":len(errors),"tiny_category_pages":tiny_pages,
        "products_discovered":len(plist),"discovery_mode":"first_party_server_html_links",
        "error_examples":errors[:20],"version":VERSION,
    }
    return plist,meta


async def run(args):
    products,discovery=await asyncio.to_thread(server_discover,args.max_categories or 1200)
    total_discovered=len(products)
    targets=products[:args.max_products] if args.max_products else products
    print(f"discovered_unique={total_discovered} detail_target={len(targets)}",flush=True)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        context=await browser.new_context(locale="es-ES",user_agent=UA)
        sem=asyncio.Semaphore(max(1,args.workers)); done=0; lock=asyncio.Lock()
        async def one(p):
            nonlocal done
            await parse_detail(context,p,sem)
            async with lock:
                done+=1
                if done%25==0 or done==len(targets):
                    valid=sum(x.nutrition_status=="DECLARED_VALID" for x in targets)
                    errs=sum(bool(x.detail_error) for x in targets)
                    print(f"detail={done}/{len(targets)} valid={valid} errors={errs}",flush=True)
        await asyncio.gather(*(one(p) for p in targets))
        await browser.close()
    # For smoke, output only detailed targets but retain discovery total in metadata/threshold.
    summary=write_outputs(Path(args.out),targets,discovery)
    summary["discovery"]["products_discovered"]=total_discovered
    Path(args.out,"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    return summary


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",default="alcampo-direct-v5-output")
    ap.add_argument("--workers",type=int,default=8)
    ap.add_argument("--max-categories",type=int,default=0)
    ap.add_argument("--max-products",type=int,default=0)
    ap.add_argument("--min-discovered",type=int,default=1)
    ap.add_argument("--min-valid-nutrition",type=int,default=0)
    a=ap.parse_args(); summary=asyncio.run(run(a))
    discovered=int(summary["discovery"]["products_discovered"]); valid=int(summary["counts"]["declared_valid_nutrition"])
    return 0 if discovered>=a.min_discovered and valid>=a.min_valid_nutrition else 2

if __name__=="__main__": raise SystemExit(main())
