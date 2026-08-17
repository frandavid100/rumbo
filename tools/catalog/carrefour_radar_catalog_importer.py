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

BASE = "https://radarsuper.com"
ROOT = BASE + "/carrefour"
USER_AGENT = "RumboCatalogImporter/1.0 (+https://github.com/frandavid100/rumbo)"
IMPORTER_VERSION = "radarsuper-carrefour-1.0.0"

# Deliberately food-only. Bodega and mixed non-food departments are excluded.
ALLOWED_TOP_CATEGORIES = {
    "Aceite, especias y salsas",
    "Agua y refrescos",
    "Aperitivos",
    "Arroz, legumbres y pasta",
    "Azúcar, caramelos y chocolate",
    "Cacao, café e infusiones",
    "Carne",
    "Cereales y galletas",
    "Charcutería y quesos",
    "Congelados",
    "Conservas, caldos y cremas",
    "Fruta y verdura",
    "Huevos, leche y mantequilla",
    "Marisco y pescado",
    "Panadería y pastelería",
    "Pizzas y platos preparados",
    "Postres y yogures",
    "Zumos",
}

@dataclass
class ProductRecord:
    radar_url: str
    carrefour_url: str | None
    retailer_sku: str
    gtin: str | None
    name: str
    brand: str | None
    legal_name: str | None
    ingredients: str | None
    family: str
    subcategory: str | None
    calories: float | None
    protein_g: float | None
    carbohydrate_g: float | None
    fat_g: float | None
    fiber_g: float | None
    salt_g: float | None
    price_eur: float | None
    nutrition_evidence_level: str | None
    nutrition_source: str | None
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
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"fetch_failed:{type(last).__name__}:{last}")


def textify(raw: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html_lib.unescape(s)).strip()


def clean_fragment(s: str | None) -> str | None:
    if not s:
        return None
    s = textify(s).strip(" :-")
    return s or None


def decimal(v: str | None) -> float | None:
    if not v:
        return None
    try:
        return float(v.replace(".", "").replace(",", ".") if "," in v else v)
    except ValueError:
        return None


def extract_links(raw: str, prefix: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', raw, re.I | re.S):
        href = html_lib.unescape(m.group(1))
        label = clean_fragment(m.group(2)) or ""
        if href.startswith(prefix):
            out.append((urljoin(BASE, href), label))
    return out


def category_urls() -> dict[str, str]:
    raw = fetch_text(ROOT)
    result = {}
    for url, label in extract_links(raw, "/carrefour/c/"):
        label = re.sub(r"\s+\d[\d.]*\s+productos.*$", "", label, flags=re.I).strip()
        if label in ALLOWED_TOP_CATEGORIES:
            result[label] = url
    return result


def enumerate_category(name: str, url: str, max_pages: int | None = None) -> list[str]:
    first = fetch_text(url)
    plain = textify(first)
    m = re.search(r"P[aá]gina\s+1\s+de\s+(\d+)", plain, re.I)
    pages = int(m.group(1)) if m else 1
    if max_pages:
        pages = min(pages, max_pages)
    seen, products = set(), []
    for page in range(1, pages + 1):
        raw = first if page == 1 else fetch_text(url.rstrip("/") + f"/pagina/{page}")
        for href, _ in extract_links(raw, "/carrefour/p/"):
            if href not in seen:
                seen.add(href); products.append(href)
        print(f"enumerate category={name!r} page={page}/{pages} products={len(products)}", flush=True)
        time.sleep(0.08)
    return products


def first_match(patterns: list[str], raw: str) -> str | None:
    for p in patterns:
        m = re.search(p, raw, re.I | re.S)
        if m:
            return html_lib.unescape(m.group(1)).strip()
    return None


def parse_product(url: str, family: str) -> ProductRecord:
    observed = datetime.now(timezone.utc).isoformat()
    fallback_sku = url.rstrip("/").split("/")[-1]
    try:
        raw = fetch_text(url)
        plain = textify(raw)
        name = first_match([r"<h1[^>]*>(.*?)</h1>", r"<title[^>]*>(.*?)</title>"], raw)
        name = clean_fragment(name) or fallback_sku

        sku = first_match([r'"sku"\s*:\s*"([^"]+)"', r"SKU\s*:?\s*([A-Za-z0-9_-]+)"], raw) or fallback_sku
        gtin = first_match([r'"gtin13"\s*:\s*"(\d{8,14})"', r'"gtin"\s*:\s*"(\d{8,14})"'], raw)
        brand = first_match([r'"brand"\s*:\s*\{[^{}]*"name"\s*:\s*"([^"]+)"', r"Marca\s*</[^>]+>\s*<[^>]+>\s*([^<]+)"], raw)
        carrefour_url = first_match([r'"url"\s*:\s*"(https://www\.carrefour\.es/supermercado/[^"]+)"', r'href=["\'](https://www\.carrefour\.es/supermercado/[^"\']+)["\']'], raw)

        # RadarSuper exposes the source-derived Carrefour fields in the page plus a visible human-readable section.
        ingredients = first_match([
            r"Ingredientes\s*</h[1-6]>\s*<p[^>]*>(.*?)</p>",
            r"Ingredientes\s*</[^>]+>\s*<[^>]+>(.*?)</[^>]+>",
            r'"ingredients"\s*:\s*"([^"]+)"',
        ], raw)
        ingredients = clean_fragment(ingredients)
        legal_name = first_match([
            r"Denominaci[oó]n legal\s*</h[1-6]>\s*<p[^>]*>(.*?)</p>",
            r"Denominaci[oó]n legal\s*</[^>]+>\s*<[^>]+>(.*?)</[^>]+>",
        ], raw)
        legal_name = clean_fragment(legal_name)

        subcategory = None
        crumbs = [label for _, label in extract_links(raw, "/carrefour/c/") if label]
        if crumbs:
            subcategory = crumbs[-1]

        def nutrient(label_patterns: str) -> float | None:
            m = re.search(label_patterns + r"[^\d<]{0,80}([\d]+(?:[.,]\d+)?)\s*g\b", plain, re.I)
            return decimal(m.group(1)) if m else None

        kcal = None
        km = re.search(r"Valor energ[eé]tico[^\d]{0,80}([\d]+(?:[.,]\d+)?)\s*kcal", plain, re.I)
        if not km:
            km = re.search(r"([\d]+(?:[.,]\d+)?)\s*kcal", plain, re.I)
        if km: kcal = decimal(km.group(1))
        fat = nutrient(r"Grasas?(?:\s+totales?)?")
        carb = nutrient(r"Hidratos?\s+de\s+carbono")
        protein = nutrient(r"Prote[ií]nas?")
        fiber = nutrient(r"Fibra(?:\s+alimentaria)?")
        salt = nutrient(r"Sal")

        # These pages explicitly attribute nutritional values to Open Food Facts.
        has_off_note = bool(re.search(r"Datos nutricionales\s*:\s*Open Food Facts|Open Food Facts", plain, re.I))
        core_complete = all(x is not None for x in (kcal, fat, carb, protein))
        evidence_level = "MATCHED" if core_complete and has_off_note else ("MATCHED" if core_complete else None)
        nutrition_source = "OPEN_FOOD_FACTS_VIA_RADARSUPER" if core_complete and has_off_note else ("RADARSUPER" if core_complete else None)

        price = None
        pm = re.search(r"(?:cuesta|precio)[^\d]{0,30}([\d]+(?:[.,]\d+)?)\s*€", plain, re.I)
        if pm: price = decimal(pm.group(1))

        return ProductRecord(url, carrefour_url, sku, gtin, name, clean_fragment(brand), legal_name,
                             ingredients, family, subcategory, kcal, protein, carb, fat, fiber, salt,
                             price, evidence_level, nutrition_source, observed,
                             hashlib.sha256(raw.encode()).hexdigest())
    except Exception as exc:
        return ProductRecord(url, None, fallback_sku, None, fallback_sku, None, None, None,
                             family, None, None, None, None, None, None, None, None, None, None,
                             observed, "", f"{type(exc).__name__}:{exc}")


def init_db(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS products(
      product_id TEXT PRIMARY KEY, gtin TEXT, name TEXT NOT NULL, brand TEXT, legal_name TEXT,
      ingredients TEXT, family TEXT, subcategory TEXT, source_page TEXT, original_carrefour_url TEXT, page_sha256 TEXT);
    CREATE INDEX IF NOT EXISTS idx_products_gtin ON products(gtin);
    CREATE INDEX IF NOT EXISTS idx_products_family ON products(family);
    CREATE TABLE IF NOT EXISTS retailer_listings(
      retailer TEXT NOT NULL, retailer_sku TEXT NOT NULL, product_id TEXT NOT NULL, url TEXT,
      price_eur REAL, observed_at TEXT NOT NULL, status TEXT NOT NULL,
      PRIMARY KEY(retailer, retailer_sku));
    CREATE TABLE IF NOT EXISTS nutrition(
      product_id TEXT PRIMARY KEY, calories REAL, protein_g REAL, carbohydrate_g REAL, fat_g REAL,
      fiber_g REAL, salt_g REAL, evidence_level TEXT NOT NULL, source TEXT NOT NULL, observed_at TEXT NOT NULL);
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


def persist(db: sqlite3.Connection, r: ProductRecord) -> tuple[bool, bool, str]:
    pid = "carrefour:" + r.retailer_sku
    db.execute("INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?)",
               (pid,r.gtin,r.name,r.brand,r.legal_name,r.ingredients,r.family,r.subcategory,
                r.radar_url,r.carrefour_url,r.page_sha256))
    db.execute("INSERT OR REPLACE INTO retailer_listings VALUES(?,?,?,?,?,?,?)",
               ("CARREFOUR",r.retailer_sku,pid,r.carrefour_url,r.price_eur,r.observed_at,
                "UNKNOWN" if r.fetch_error else "ACTIVE"))
    usable = all(x is not None for x in (r.calories,r.protein_g,r.carbohydrate_g,r.fat_g))
    if usable:
        db.execute("INSERT OR REPLACE INTO nutrition VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (pid,r.calories,r.protein_g,r.carbohydrate_g,r.fat_g,r.fiber_g,r.salt_g,
                    r.nutrition_evidence_level or "MATCHED",r.nutrition_source or "RADARSUPER",r.observed_at))
        f = ProductFeatures(name=r.name, legal_name=r.legal_name, ingredients=r.ingredients,
                            family=r.family, subcategory=r.subcategory, calories=r.calories,
                            protein_g=r.protein_g, carbohydrate_g=r.carbohydrate_g,
                            fat_g=r.fat_g, fiber_g=r.fiber_g)
        result = classify(f)
        ctype = result.culinary_type.value if result.culinary_type else None
        status = "MENU_ELIGIBLE" if result.classified else "REVIEW"
        db.execute("INSERT OR REPLACE INTO classifications VALUES(?,?,?,?,?,?,?,?,?)",
                   (pid,CLASSIFIER_VERSION,ctype,result.preferred_grams,result.minimum_grams,result.maximum_grams,
                    int(result.classified),status,json.dumps(result.review_reasons,ensure_ascii=False)))
        for axis, roles in (("NUTRITIONAL",result.nutritional_roles),("CULINARY",result.culinary_roles)):
            for a in roles:
                db.execute("INSERT OR REPLACE INTO classification_roles VALUES(?,?,?,?,?,?)",
                           (pid,axis,a.value,a.confidence,a.rule_id,json.dumps(a.evidence,ensure_ascii=False)))
        return True, result.classified, status
    db.execute("INSERT OR REPLACE INTO classifications VALUES(?,?,?,?,?,?,?,?,?)",
               (pid,CLASSIFIER_VERSION,None,None,None,None,0,"NUTRITION_MISSING",'["NUTRITION_MISSING"]'))
    return False, False, "NUTRITION_MISSING"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="carrefour-catalog-output")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--max-products", type=int, default=0)
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    cats = category_urls()
    missing = sorted(ALLOWED_TOP_CATEGORIES - set(cats))
    if missing:
        print("warning missing categories:", missing, flush=True)
    refs: list[tuple[str,str]] = []
    enum_counts = {}
    for family, url in sorted(cats.items()):
        products = enumerate_category(family,url,args.max_pages or None)
        enum_counts[family] = len(products)
        refs.extend((p,family) for p in products)
    # Product URLs should be unique; if duplicated across departments preserve the first category deterministically.
    unique = {}
    for u,f in refs: unique.setdefault(u,f)
    refs = list(unique.items())
    if args.max_products: refs = refs[:args.max_products]

    db = init_db(out/"carrefour_food_catalog.sqlite")
    for k,v in {
        "schema_version":"carrefour-dev-mirror-1",
        "importer_version":IMPORTER_VERSION,
        "classifier_version":CLASSIFIER_VERSION,
        "built_at":datetime.now(timezone.utc).isoformat(),
        "catalog_identity_source":"RadarSuper mirror of Carrefour",
        "nutrition_policy":"MATCHED; Open Food Facts via RadarSuper when attributed",
    }.items(): db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)",(k,v))

    counts = {"DISCOVERABLE":len(refs),"IDENTIFIED":0,"NUTRITIONALLY_USABLE":0,"CLASSIFIED":0,
              "MENU_ELIGIBLE":0,"REVIEW":0,"NUTRITION_MISSING":0,"FETCH_ERROR":0}
    source_counts = {}
    observations = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        future_map = {ex.submit(parse_product,u,f):(u,f) for u,f in refs}
        for i,fut in enumerate(cf.as_completed(future_map),1):
            r = fut.result(); observations.append(asdict(r))
            if r.fetch_error: counts["FETCH_ERROR"] += 1
            else: counts["IDENTIFIED"] += 1
            usable, classified, status = persist(db,r)
            if usable:
                counts["NUTRITIONALLY_USABLE"] += 1
                source_counts[r.nutrition_source or "UNKNOWN"] = source_counts.get(r.nutrition_source or "UNKNOWN",0)+1
            if classified:
                counts["CLASSIFIED"] += 1; counts["MENU_ELIGIBLE"] += 1
            elif status == "REVIEW": counts["REVIEW"] += 1
            elif status == "NUTRITION_MISSING": counts["NUTRITION_MISSING"] += 1
            if i % 250 == 0:
                db.commit(); print(f"products={i}/{len(refs)} usable={counts['NUTRITIONALLY_USABLE']} eligible={counts['MENU_ELIGIBLE']}",flush=True)
    db.commit(); db.close()

    observations.sort(key=lambda x:(x["family"],x["retailer_sku"]))
    with (out/"observations.jsonl").open("w",encoding="utf-8") as fh:
        for x in observations: fh.write(json.dumps(x,ensure_ascii=False)+"\n")
    summary = {
        "importer_version":IMPORTER_VERSION,"classifier_version":CLASSIFIER_VERSION,
        "allowed_food_categories":sorted(ALLOWED_TOP_CATEGORIES),"discovered_categories":cats,
        "enumerated_per_category":enum_counts,"unique_product_urls":len(refs),"counts":counts,
        "nutrition_sources":source_counts,
        "provenance_note":"Identity/listing is obtained from RadarSuper's Carrefour mirror. Nutrition attributed there to Open Food Facts is stored as MATCHED, never DECLARED Carrefour evidence.",
        "distribution_note":"Development artifact only; do not redistribute as a Carrefour-derived database without rights review.",
    }
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if refs else 2

if __name__ == "__main__":
    raise SystemExit(main())
