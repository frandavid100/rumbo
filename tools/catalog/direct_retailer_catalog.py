from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from nutrition_validation import validate_nutrition


@dataclass
class ProductObservation:
    retailer: str
    url: str
    sku: str
    name: str | None
    gtin: str | None
    brand: str | None
    legal_name: str | None
    ingredients: str | None
    category: str | None
    calories: float | None
    protein_g: float | None
    carbohydrate_g: float | None
    fat_g: float | None
    fiber_g: float | None
    salt_g: float | None
    nutrition_status: str
    fetch_error: str | None = None


def norm_num(v: str | None) -> float | None:
    if not v:
        return None
    m = re.search(r"[-+]?\d+(?:[.,]\d+)?", v.replace("\xa0", " "))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def clean(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"\s+", " ", s).strip(" :-\n\t")
    return s or None


class CarrefourAdapter:
    retailer = "CARREFOUR"
    base = "https://www.carrefour.es"
    roots = [
        ("Frescos", "https://www.carrefour.es/supermercado/frescos/cat20002/c"),
        ("La Despensa", "https://www.carrefour.es/supermercado/la-despensa/cat20001/c"),
        ("Bebidas", "https://www.carrefour.es/supermercado/bebidas/cat20003/c"),
        ("Congelados", "https://www.carrefour.es/supermercado/congelados/cat21449123/c"),
    ]
    deny_category_terms = re.compile(
        r"\b(vino|vinos|cerveza|cervezas|licor|licores|whisky|whiskey|ron|ginebra|vodka|brandy|cognac|champagne|cava|sidra|aperitivos? alcohol|bodega)\b",
        re.I,
    )

    async def discover_category_tree(self, page) -> list[tuple[str, str]]:
        seen: dict[str, str] = {}
        queue = list(self.roots)
        while queue:
            label, url = queue.pop(0)
            canon = url.split("?")[0]
            if canon in seen:
                continue
            seen[canon] = label
            try:
                await page.goto(canon, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(800)
                links = await page.eval_on_selector_all(
                    'a[href*="/supermercado/"]',
                    "els => els.map(a => [a.innerText.trim(), a.href])",
                )
            except Exception:
                continue
            for text, href in links:
                href = href.split("?")[0]
                if not re.search(r"/cat\d+/c/?$", href):
                    continue
                if self.deny_category_terms.search((text or "") + " " + href.replace("-", " ")):
                    continue
                # Keep only grocery catalogue categories, never navigation into non-food departments.
                if not any(seg in href for seg in ("/frescos/", "/la-despensa/", "/bebidas/", "/congelados/")):
                    continue
                if href not in seen:
                    queue.append((clean(text) or href, href))
            if len(seen) > 250:
                break
        return sorted((label, url) for url, label in seen.items())

    async def product_links_from_category(self, page, label: str, url: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        seen = set()
        current = url
        for page_no in range(1, 80):
            try:
                await page.goto(current, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(700)
            except Exception:
                break
            links = await page.eval_on_selector_all(
                'a[href*="/supermercado/"]',
                "els => els.map(a => [a.innerText.trim(), a.href])",
            )
            found = 0
            for text, href in links:
                href = href.split("?")[0]
                if re.search(r"/R-[^/]+/p/?$", href):
                    if href not in seen:
                        seen.add(href); out.append((href, label)); found += 1
            body = await page.locator("body").inner_text()
            m = re.search(r"P[aá]gina\s+(\d+)\s+de\s+(\d+)", body, re.I)
            if not m or int(m.group(1)) >= int(m.group(2)):
                break
            # Prefer the actual next-page href rendered by Carrefour.
            next_href = await page.eval_on_selector_all(
                'a[href]',
                "els => { const a=els.find(x => /siguiente|next/i.test((x.innerText||'')+' '+(x.getAttribute('aria-label')||''))); return a ? a.href : null; }",
            )
            if next_href and next_href != current:
                current = next_href
            else:
                # Carrefour has used both page and pagination query names over time; try page first.
                sep = "&" if "?" in url else "?"
                current = f"{url}{sep}page={page_no+1}"
            if found == 0 and page_no > 1:
                break
        return out

    async def parse_product(self, page, url: str, category: str) -> ProductObservation:
        sku = re.search(r"/R-([^/]+)/p/?$", url)
        sku = sku.group(1) if sku else url.rstrip("/").split("/")[-1]
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(350)
            text = await page.locator("body").inner_text()
            html = await page.content()
            name = clean(await page.locator("h1").first.inner_text()) if await page.locator("h1").count() else None
            gtin = None
            for pat in (r'"gtin13"\s*:\s*"(\d{8,14})"', r'"gtin"\s*:\s*"(\d{8,14})"', r'"ean"\s*:\s*"(\d{8,14})"'):
                m = re.search(pat, html, re.I)
                if m: gtin = m.group(1); break
            brand = None
            for pat in (r'"brand"\s*:\s*\{[^{}]*"name"\s*:\s*"([^"]+)"', r'"brand"\s*:\s*"([^"]+)"'):
                m = re.search(pat, html, re.I)
                if m: brand = clean(m.group(1)); break

            def section_value(start: str, ends: tuple[str, ...]) -> str | None:
                mm = re.search(start + r"\s*(.+?)(?=" + "|".join(map(re.escape, ends)) + r"|$)", text, re.I | re.S)
                return clean(mm.group(1)) if mm else None

            ingredients = section_value("Ingredientes", ("Alérgenos", "Más información", "Características producto", "Otra información obligatoria"))
            legal_name = section_value("Denominación legal", ("Ingredientes", "Alérgenos", "Más información", "Otra información obligatoria"))

            nutrition = ""
            nm = re.search(r"Información nutricional\s*(.+?)(?=Ingredientes|Alérgenos|Más información|Características producto|Otra información obligatoria|$)", text, re.I | re.S)
            if nm: nutrition = nm.group(1)
            kcal = None
            km = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*Kcal", nutrition, re.I)
            if km: kcal = norm_num(km.group(1))
            def g(label):
                mm = re.search(label + r"[^0-9]{0,25}([0-9]+(?:[.,][0-9]+)?)\s*g", nutrition, re.I)
                return norm_num(mm.group(1)) if mm else None
            fat = g(r"Grasas?(?:\s*\(g\))?")
            carb = g(r"Hidratos?\s+de\s+carbono(?:\s*\(g\))?")
            fiber = g(r"Fibra(?:\s+alimentaria)?(?:\s*\(g\))?")
            protein = g(r"Prote[ií]nas?(?:\s*\(g\))?")
            salt = g(r"Sal(?:\s*\(g\))?")
            if all(v is not None for v in (kcal, protein, carb, fat)):
                valid = validate_nutrition(kcal, protein, carb, fat, fiber, salt)
                status = "DECLARED_VALID" if valid.valid else "DECLARED_INVALID:" + ",".join(valid.reasons)
            else:
                status = "DECLARED_INCOMPLETE"
            return ProductObservation(self.retailer, url, sku, name, gtin, brand, legal_name, ingredients, category,
                                      kcal, protein, carb, fat, fiber, salt, status)
        except Exception as exc:
            return ProductObservation(self.retailer, url, sku, None, None, None, None, None, category,
                                      None, None, None, None, None, None, "FETCH_ERROR", f"{type(exc).__name__}:{exc}")


class AlcampoAdapter:
    retailer = "ALCAMPO"
    base = "https://www.compraonline.alcampo.es"
    sitemap = base + "/sitemap.xml"
    deny = re.compile(r"/(?:wine|wines|beer|beers|spirits|alcohol)|\b(vino|cerveza|licor|whisky|ron|ginebra|vodka|cava|sidra)\b", re.I)

    async def discover_products(self, page) -> list[tuple[str, str]]:
        urls = []
        try:
            await page.goto(self.sitemap, wait_until="domcontentloaded", timeout=45000)
            raw = await page.locator("body").inner_text()
            # XML is rendered as text in Chromium; collect every sitemap child or product URL.
            locs = re.findall(r"https?://[^\s<>]+", raw)
        except Exception:
            locs = []
        child_maps = [x for x in locs if "sitemap" in x and "/products/" not in x]
        product_urls = [x for x in locs if "/products/" in x]
        for sm in child_maps[:100]:
            try:
                await page.goto(sm, wait_until="domcontentloaded", timeout=45000)
                txt = await page.locator("body").inner_text()
                product_urls.extend(re.findall(r"https?://[^\s<>]+/products/[^\s<>]+", txt))
            except Exception:
                continue
        out=[]; seen=set()
        for u in product_urls:
            u=u.rstrip('.,<>")\'')
            if self.deny.search(u):
                continue
            if u not in seen:
                seen.add(u); out.append((u, "Alcampo"))
        return out

    async def parse_product(self, page, url: str, category: str) -> ProductObservation:
        sku = url.rstrip("/").split("/")[-1]
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(250)
            text = await page.locator("body").inner_text(); html = await page.content()
            name = clean(await page.locator("h1").first.inner_text()) if await page.locator("h1").count() else None
            def first(pats):
                for p in pats:
                    m=re.search(p,html,re.I|re.S)
                    if m: return clean(m.group(1))
                return None
            gtin=first([r'"gtin13"\s*:\s*"(\d{8,14})"',r'"gtin"\s*:\s*"(\d{8,14})"',r'"ean"\s*:\s*"(\d{8,14})"'])
            brand=first([r'"brand"\s*:\s*"([^"]+)"',r'"brand"\s*:\s*\{[^{}]*"name"\s*:\s*"([^"]+)"'])
            legal=first([r'"legalName"\s*:\s*"([^"]+)"'])
            ingredients=first([r'"ingredients"\s*:\s*"([^"]+)"'])
            if not ingredients:
                m=re.search(r"Ingredientes\s*(.+?)(?=Alérgenos|Información nutricional|Denominación|$)",text,re.I|re.S); ingredients=clean(m.group(1)) if m else None
            if not legal:
                m=re.search(r"Denominaci[oó]n legal\s*(.+?)(?=Ingredientes|Alérgenos|Información nutricional|$)",text,re.I|re.S); legal=clean(m.group(1)) if m else None
            nm=re.search(r"(?:Información|Informacion) nutricional\s*(.+?)(?=Ingredientes|Alérgenos|Denominaci[oó]n|$)",text,re.I|re.S)
            nutrition=nm.group(1) if nm else text
            km=re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*kcal",nutrition,re.I); kcal=norm_num(km.group(1)) if km else None
            def g(label):
                mm=re.search(label+r"[^0-9]{0,30}([0-9]+(?:[.,][0-9]+)?)\s*g",nutrition,re.I); return norm_num(mm.group(1)) if mm else None
            fat=g(r"Grasas?(?:\s+totales?)?"); carb=g(r"Hidratos?\s+de\s+carbono"); protein=g(r"Prote[ií]nas?"); fiber=g(r"Fibra(?:\s+alimentaria)?"); salt=g(r"Sal")
            if all(v is not None for v in (kcal,protein,carb,fat)):
                val=validate_nutrition(kcal,protein,carb,fat,fiber,salt); status="DECLARED_VALID" if val.valid else "DECLARED_INVALID:"+",".join(val.reasons)
            else: status="DECLARED_INCOMPLETE"
            return ProductObservation(self.retailer,url,sku,name,gtin,brand,legal,ingredients,category,kcal,protein,carb,fat,fiber,salt,status)
        except Exception as exc:
            return ProductObservation(self.retailer,url,sku,None,None,None,None,None,category,None,None,None,None,None,None,"FETCH_ERROR",f"{type(exc).__name__}:{exc}")


def init_db(path: Path):
    db=sqlite3.connect(path)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS products(retailer TEXT, sku TEXT, url TEXT, name TEXT, gtin TEXT, brand TEXT, legal_name TEXT, ingredients TEXT, category TEXT, PRIMARY KEY(retailer,sku));
    CREATE TABLE IF NOT EXISTS nutrition(retailer TEXT, sku TEXT, calories REAL, protein_g REAL, carbohydrate_g REAL, fat_g REAL, fiber_g REAL, salt_g REAL, evidence_level TEXT, status TEXT, PRIMARY KEY(retailer,sku));
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
    ''')
    return db


async def run(retailer: str, out: Path, workers: int, max_products: int):
    out.mkdir(parents=True,exist_ok=True)
    adapter = CarrefourAdapter() if retailer == "carrefour" else AlcampoAdapter()
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        context=await browser.new_context(locale="es-ES", user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36")
        discovery_page=await context.new_page()
        if retailer == "carrefour":
            cats=await adapter.discover_category_tree(discovery_page)
            refs=[]
            # Use terminal/specific categories first; duplicates are removed globally.
            for i,(label,url) in enumerate(cats,1):
                links=await adapter.product_links_from_category(discovery_page,label,url)
                refs.extend(links)
                print(f"discover category={i}/{len(cats)} {label!r} refs={len(refs)}",flush=True)
        else:
            cats=[]; refs=await adapter.discover_products(discovery_page)
        dedup={}
        for url,cat in refs: dedup.setdefault(url,cat)
        refs=list(dedup.items())
        if max_products: refs=refs[:max_products]
        print(f"discovered_unique={len(refs)}",flush=True)

        db=init_db(out/f"{retailer}_food_catalog.sqlite")
        now=datetime.now(timezone.utc).isoformat()
        db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)",("source",adapter.base))
        db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)",("built_at",now))
        db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)",("evidence_policy","DECLARED from retailer page; no third-party product-data source"))
        observations=[]
        q=asyncio.Queue()
        for ref in refs: q.put_nowait(ref)
        lock=asyncio.Lock(); done=0
        async def worker():
            nonlocal done
            page=await context.new_page()
            while True:
                try: url,cat=q.get_nowait()
                except asyncio.QueueEmpty: break
                obs=await adapter.parse_product(page,url,cat)
                async with lock:
                    observations.append(obs); done+=1
                    db.execute("INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?,?,?,?)",(obs.retailer,obs.sku,obs.url,obs.name,obs.gtin,obs.brand,obs.legal_name,obs.ingredients,obs.category))
                    if obs.nutrition_status.startswith("DECLARED_"):
                        db.execute("INSERT OR REPLACE INTO nutrition VALUES(?,?,?,?,?,?,?,?,?,?)",(obs.retailer,obs.sku,obs.calories,obs.protein_g,obs.carbohydrate_g,obs.fat_g,obs.fiber_g,obs.salt_g,"DECLARED",obs.nutrition_status))
                    if done%100==0 or done==len(refs):
                        db.commit(); valid=sum(o.nutrition_status=="DECLARED_VALID" for o in observations); err=sum(o.fetch_error is not None for o in observations)
                        print(f"progress={done}/{len(refs)} ({done/max(1,len(refs))*100:.1f}%) declared_valid={valid} errors={err}",flush=True)
                q.task_done()
            await page.close()
        await asyncio.gather(*(worker() for _ in range(max(1,workers))))
        db.commit(); db.close(); await browser.close()

    observations.sort(key=lambda o:o.sku)
    with (out/"observations.jsonl").open("w",encoding="utf-8") as fh:
        for o in observations: fh.write(json.dumps(asdict(o),ensure_ascii=False)+"\n")
    counts={
        "discovered":len(refs),"fetched":sum(o.fetch_error is None for o in observations),"fetch_errors":sum(o.fetch_error is not None for o in observations),
        "with_gtin":sum(bool(o.gtin) for o in observations),"with_ingredients":sum(bool(o.ingredients) for o in observations),
        "declared_valid_nutrition":sum(o.nutrition_status=="DECLARED_VALID" for o in observations),
        "declared_incomplete_nutrition":sum(o.nutrition_status=="DECLARED_INCOMPLETE" for o in observations),
        "declared_invalid_nutrition":sum(o.nutrition_status.startswith("DECLARED_INVALID") for o in observations),
    }
    summary={"retailer":adapter.retailer,"source":adapter.base,"built_at":datetime.now(timezone.utc).isoformat(),"counts":counts,"categories_discovered":len(cats) if retailer=="carrefour" else None,"third_party_product_data":False}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("retailer",choices=["carrefour","alcampo"]); ap.add_argument("--out",required=True); ap.add_argument("--workers",type=int,default=6); ap.add_argument("--max-products",type=int,default=0)
    a=ap.parse_args(); asyncio.run(run(a.retailer,Path(a.out),a.workers,a.max_products))

if __name__=="__main__": main()
