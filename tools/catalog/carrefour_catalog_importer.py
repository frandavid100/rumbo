from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import html as html_lib
import json
import re
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from classifier import CLASSIFIER_VERSION, ProductFeatures, classify

BASE_URL = "https://www.carrefour.es"
USER_AGENT = "RumboCatalogImporter/1.0 (+https://github.com/frandavid100/rumbo)"
IMPORTER_VERSION = "1.0.0"
ROOT_CATEGORIES = {
    "FRESCOS": "https://www.carrefour.es/supermercado/frescos/cat20002/c",
    "DESPENSA": "https://www.carrefour.es/supermercado/la-despensa/cat20001/c",
    "CONGELADOS": "https://www.carrefour.es/supermercado/congelados/cat21449123/c",
}
PRODUCT_LINK_RE = re.compile(r'href=["\']([^"\']+/supermercado/[^"\']+/R-[^"\']+/p[^"\']*)', re.I)
PRODUCT_LINK_ALT_RE = re.compile(r'href=["\']([^"\']+/supermercado/[^"\']+/R-[^"\']+/p)', re.I)
PAGE_COUNT_RE = re.compile(r"P[aá]gina\s+\d+\s+de\s+(\d+)", re.I)
SKU_RE = re.compile(r"/(R-[^/]+)/p(?:[?#]|$)", re.I)

@dataclass
class ProductRecord:
    retailer_sku: str
    url: str
    name: str
    brand: str | None
    gtin: str | None
    legal_name: str | None
    ingredients: str | None
    family: str | None
    subcategory: str | None
    calories: float | None
    protein_g: float | None
    carbohydrate_g: float | None
    fat_g: float | None
    fiber_g: float | None
    price_eur: float | None
    content_net: str | None
    observed_at: str
    page_sha256: str
    fetch_error: str | None = None


def fetch_text(url: str, timeout: float = 25.0, retries: int = 3) -> str:
    last = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "es-ES,es;q=0.9"})
            with urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(0.7 * (attempt + 1))
    raise RuntimeError(f"fetch_failed:{type(last).__name__}:{last}")


def strip_text(raw: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_lib.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def json_ld_blocks(raw: str) -> list[dict]:
    out = []
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', raw, re.I | re.S):
        try:
            obj = json.loads(html_lib.unescape(m.group(1)).strip())
        except Exception:
            continue
        items = obj if isinstance(obj, list) else [obj]
        for item in items:
            if isinstance(item, dict):
                if isinstance(item.get("@graph"), list):
                    out.extend(x for x in item["@graph"] if isinstance(x, dict))
                else:
                    out.append(item)
    return out


def first_product_ld(blocks: list[dict]) -> dict:
    for x in blocks:
        typ = x.get("@type")
        if typ == "Product" or (isinstance(typ, list) and "Product" in typ):
            return x
    return {}


def breadcrumb_categories(blocks: list[dict]) -> tuple[str | None, str | None]:
    for x in blocks:
        if x.get("@type") != "BreadcrumbList":
            continue
        names = []
        for el in x.get("itemListElement", []):
            if not isinstance(el, dict):
                continue
            item = el.get("item")
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
            elif el.get("name"):
                names.append(str(el["name"]))
        names = [n for n in names if n.lower() not in {"inicio", "supermercado"}]
        if names:
            return (names[0], names[-1] if len(names) > 1 else None)
    return None, None


def num(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, re.I)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def section_value(label: str, text: str, stop: str) -> str | None:
    m = re.search(label + r"\s*:?\s*(.*?)\s*(?=" + stop + r")", text, re.I)
    return m.group(1).strip() if m and m.group(1).strip() else None


def parse_product(url: str) -> ProductRecord:
    observed = datetime.now(timezone.utc).isoformat()
    sku_m = SKU_RE.search(url)
    sku = sku_m.group(1) if sku_m else hashlib.sha256(url.encode()).hexdigest()[:20]
    try:
        raw = fetch_text(url)
        text = strip_text(raw)
        blocks = json_ld_blocks(raw)
        p = first_product_ld(blocks)
        family, subcategory = breadcrumb_categories(blocks)
        name = str(p.get("name") or "").strip()
        if not name:
            title_m = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.I | re.S)
            name = strip_text(title_m.group(1)) if title_m else sku
        brand_obj = p.get("brand")
        brand = (brand_obj.get("name") if isinstance(brand_obj, dict) else brand_obj) or None
        gtin = p.get("gtin13") or p.get("gtin14") or p.get("gtin12") or p.get("gtin8")
        legal = section_value(r"Denominaci[oó]n legal", text, r"Direcci[oó]n del operador|Raz[oó]n social|Medidas|Marca|Modo de empleo|$" )
        ingredients = section_value(r"Ingredientes", text, r"M[aá]s informaci[oó]n|Datos del producto|Medidas|Marca|Valoraci[oó]n Nutri|$" )
        if not ingredients and isinstance(p.get("description"), str):
            ingredients = p.get("description")
        calories = num(r"Valor energ[eé]tico\s*[\d.,]+\s*KJ\s*([\d.,]+)\s*Kcal", text)
        fat = num(r"Grasas?\s*\(g\)\s*([\d.,]+)\s*g", text)
        carb = num(r"Hidratos? de carbono\s*\(g\)\s*([\d.,]+)\s*g", text)
        protein = num(r"Prote[ií]nas?\s*\(g\)\s*([\d.,]+)\s*g", text)
        fiber = num(r"Fibra alimentaria\s*\(g\)\s*([\d.,]+)\s*g", text)
        offers = p.get("offers") if isinstance(p.get("offers"), dict) else {}
        price = None
        try:
            if offers.get("price") is not None:
                price = float(str(offers["price"]).replace(",", "."))
        except ValueError:
            pass
        content_net = section_value(r"Contenido neto", text, r"Modo de empleo|Datos del producto|Marca|Instrucciones|$" )
        return ProductRecord(sku, url, name, str(brand).strip() if brand else None, str(gtin).strip() if gtin else None,
                             legal, ingredients, family, subcategory, calories, protein, carb, fat, fiber,
                             price, content_net, observed, hashlib.sha256(raw.encode()).hexdigest())
    except Exception as exc:
        return ProductRecord(sku, url, sku, None, None, None, None, None, None,
                             None, None, None, None, None, None, None, observed, "", f"{type(exc).__name__}:{exc}")


def page_url(base: str, page: int) -> str:
    return base if page == 1 else f"{base}?page={page}"


def enumerate_category(base: str, max_pages: int | None = None) -> list[str]:
    first = fetch_text(base)
    count = PAGE_COUNT_RE.search(strip_text(first))
    pages = int(count.group(1)) if count else 1
    if max_pages:
        pages = min(pages, max_pages)
    urls: list[str] = []
    seen = set()
    for page in range(1, pages + 1):
        raw = first if page == 1 else fetch_text(page_url(base, page))
        links = PRODUCT_LINK_RE.findall(raw) or PRODUCT_LINK_ALT_RE.findall(raw)
        for href in links:
            url = urljoin(BASE_URL, html_lib.unescape(href))
            if url not in seen:
                seen.add(url); urls.append(url)
        print(f"enumerate {base} page={page}/{pages} unique={len(urls)}", flush=True)
        time.sleep(0.15)
    return urls


def init_db(path: Path):
    db = sqlite3.connect(path)
    db.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS products(
      product_id TEXT PRIMARY KEY, gtin TEXT, name TEXT NOT NULL, brand TEXT, legal_name TEXT,
      ingredients TEXT, family TEXT, subcategory TEXT, content_net TEXT, page_sha256 TEXT);
    CREATE TABLE IF NOT EXISTS retailer_listings(
      retailer TEXT NOT NULL, retailer_sku TEXT NOT NULL, product_id TEXT NOT NULL, url TEXT NOT NULL,
      price_eur REAL, observed_at TEXT NOT NULL, status TEXT NOT NULL,
      PRIMARY KEY(retailer, retailer_sku));
    CREATE TABLE IF NOT EXISTS nutrition(
      product_id TEXT PRIMARY KEY, calories REAL, protein_g REAL, carbohydrate_g REAL, fat_g REAL, fiber_g REAL,
      evidence_level TEXT NOT NULL, source TEXT NOT NULL, observed_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS classifications(
      product_id TEXT PRIMARY KEY, classifier_version TEXT NOT NULL, culinary_type TEXT,
      preferred_grams REAL, minimum_grams REAL, maximum_grams REAL, classified INTEGER NOT NULL,
      status TEXT NOT NULL, review_reasons_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS classification_roles(
      product_id TEXT NOT NULL, axis TEXT NOT NULL, role TEXT NOT NULL, confidence REAL NOT NULL,
      rule_id TEXT NOT NULL, evidence_json TEXT NOT NULL,
      PRIMARY KEY(product_id, axis, role));
    """)
    return db


def write_record(db: sqlite3.Connection, r: ProductRecord):
    product_id = "carrefour:" + r.retailer_sku
    db.execute("INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?,?,?,?,?)",
               (product_id,r.gtin,r.name,r.brand,r.legal_name,r.ingredients,r.family,r.subcategory,r.content_net,r.page_sha256))
    listing_status = "UNKNOWN" if r.fetch_error else "ACTIVE"
    db.execute("INSERT OR REPLACE INTO retailer_listings VALUES(?,?,?,?,?,?,?)",
               ("CARREFOUR",r.retailer_sku,product_id,r.url,r.price_eur,r.observed_at,listing_status))
    core = (r.calories,r.protein_g,r.carbohydrate_g,r.fat_g)
    nutritionally_usable = all(v is not None for v in core)
    if nutritionally_usable:
        db.execute("INSERT OR REPLACE INTO nutrition VALUES(?,?,?,?,?,?,?,?,?)",
                   (product_id,r.calories,r.protein_g,r.carbohydrate_g,r.fat_g,r.fiber_g,"DECLARED","CARREFOUR",r.observed_at))
    features = ProductFeatures(name=r.name, legal_name=r.legal_name, ingredients=r.ingredients,
                               family=r.family, subcategory=r.subcategory, calories=r.calories,
                               protein_g=r.protein_g, carbohydrate_g=r.carbohydrate_g,
                               fat_g=r.fat_g, fiber_g=r.fiber_g)
    result = classify(features) if nutritionally_usable else None
    if result:
        ctype = result.culinary_type.value if result.culinary_type else None
        classified = result.classified
        status = "MENU_ELIGIBLE" if classified else "REVIEW"
        review = result.review_reasons
        db.execute("INSERT OR REPLACE INTO classifications VALUES(?,?,?,?,?,?,?,?,?)",
                   (product_id,CLASSIFIER_VERSION,ctype,result.preferred_grams,result.minimum_grams,result.maximum_grams,
                    1 if classified else 0,status,json.dumps(review,ensure_ascii=False)))
        for axis, roles in (("NUTRITIONAL",result.nutritional_roles),("CULINARY",result.culinary_roles)):
            for a in roles:
                db.execute("INSERT OR REPLACE INTO classification_roles VALUES(?,?,?,?,?,?)",
                           (product_id,axis,a.value,a.confidence,a.rule_id,json.dumps(a.evidence,ensure_ascii=False)))
    else:
        status = "NUTRITION_MISSING" if not nutritionally_usable else "REVIEW"
        db.execute("INSERT OR REPLACE INTO classifications VALUES(?,?,?,?,?,?,?,?,?)",
                   (product_id,CLASSIFIER_VERSION,None,None,None,None,0,status,json.dumps([status],ensure_ascii=False)))
    return nutritionally_usable, bool(result and result.classified), status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="carrefour-catalog-output")
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--max-pages", type=int, default=0, help="0 = all")
    ap.add_argument("--max-products", type=int, default=0, help="0 = all")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    all_urls = []
    per_category = {}
    for name, base in ROOT_CATEGORIES.items():
        urls = enumerate_category(base, args.max_pages or None)
        per_category[name] = len(urls)
        all_urls.extend(urls)
    all_urls = list(dict.fromkeys(all_urls))
    if args.max_products:
        all_urls = all_urls[:args.max_products]
    (out/"urls.txt").write_text("\n".join(all_urls), encoding="utf-8")

    db = init_db(out/"carrefour_food_catalog.sqlite")
    db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)",("schema_version","carrefour-dev-1"))
    db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)",("importer_version",IMPORTER_VERSION))
    db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)",("classifier_version",CLASSIFIER_VERSION))
    db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)",("built_at",datetime.now(timezone.utc).isoformat()))
    counts = {"DISCOVERABLE":len(all_urls),"IDENTIFIED":0,"NUTRITIONALLY_USABLE":0,"CLASSIFIED":0,"MENU_ELIGIBLE":0,"REVIEW":0,"NUTRITION_MISSING":0,"FETCH_ERROR":0}
    observations = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(parse_product,u):u for u in all_urls}
        for i, fut in enumerate(cf.as_completed(futures),1):
            r = fut.result(); observations.append(asdict(r))
            if r.fetch_error:
                counts["FETCH_ERROR"] += 1
            else:
                counts["IDENTIFIED"] += 1
            usable, classified, status = write_record(db,r)
            if usable: counts["NUTRITIONALLY_USABLE"] += 1
            if classified:
                counts["CLASSIFIED"] += 1; counts["MENU_ELIGIBLE"] += 1
            elif status in counts:
                counts[status] += 1
            if i % 100 == 0:
                db.commit(); print(f"products={i}/{len(all_urls)} usable={counts['NUTRITIONALLY_USABLE']} eligible={counts['MENU_ELIGIBLE']}", flush=True)
    db.commit(); db.close()
    observations.sort(key=lambda x:x["retailer_sku"])
    with (out/"observations.jsonl").open("w",encoding="utf-8") as f:
        for row in observations: f.write(json.dumps(row,ensure_ascii=False)+"\n")
    summary = {"importer_version":IMPORTER_VERSION,"classifier_version":CLASSIFIER_VERSION,"root_categories":ROOT_CATEGORIES,
               "enumerated_per_category":per_category,"unique_product_urls":len(all_urls),"counts":counts,
               "notes":["Only Frescos, La Despensa and Congelados are imported.","Nutrition from Carrefour product pages is DECLARED evidence.","Missing nutrition remains null; no generic substitution is performed in this importer."]}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if all_urls else 2

if __name__ == "__main__":
    raise SystemExit(main())
