from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import re
import sqlite3
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from playwright.async_api import async_playwright

from nutrition_validation import validate_nutrition

BASE = "https://www.compraonline.alcampo.es"
ROOT = BASE + "/categories"
VERSION = "alcampo-direct-v4.0"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36"

FOOD_ROOT_TERMS = (
    "frescos", "leche", "huevos", "lacte", "yogur", "bebidas vegetales",
    "alimentaci", "desayuno", "merienda", "congelados", "comida preparada",
    "ecol", "sin gluten", "sin lactosa", "nutrici", "funcional", "vegan",
)
DENY = re.compile(
    r"\b(vino|vinos|cerveza|cervezas|licor|licores|whisky|whiskey|ron|ginebra|vodka|brandy|cognac|champagne|cava|sidra|vermut|vermouth|sangr[ií]a|alcohol|espirituosas)\b",
    re.I,
)
PRODUCT_RE = re.compile(r"/products/.+/(\d+)/?$", re.I)


def clean(value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(re.sub(r"\s+", " ", value)).strip(" :-\n\t")
    return value or None


def norm_key(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c)).replace("_", "").replace("-", "")


def number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value).replace("\xa0", " "))
    return float(m.group(0).replace(",", ".")) if m else None


def stable_id(namespace: str, key: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{namespace}:{key}".encode()).digest()[:7], "big")


def same_host(url: str) -> bool:
    return urlparse(url).netloc == urlparse(BASE).netloc


def sku_from_url(url: str) -> str | None:
    m = PRODUCT_RE.search(url.split("?")[0])
    return m.group(1) if m else None


def walk_json(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_json(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_json(value)


def product_records(payload) -> list[dict]:
    out = []
    seen = set()
    for obj in walk_json(payload):
        sku = obj.get("retailerProductId") or obj.get("retailer_product_id")
        name = obj.get("name")
        if sku is None or not isinstance(name, str):
            continue
        sku = str(sku)
        if sku in seen:
            continue
        seen.add(sku)
        out.append(obj)
    return out


def recursive_scalar(obj, keys: tuple[str, ...]):
    wanted = {norm_key(k) for k in keys}
    for node in walk_json(obj):
        for key, value in node.items():
            if norm_key(str(key)) in wanted and isinstance(value, (str, int, float)):
                return value
    return None


def recursive_url(obj) -> str | None:
    for node in walk_json(obj):
        for key, value in node.items():
            if isinstance(value, str) and "/products/" in value and ("url" in str(key).lower() or "href" in str(key).lower()):
                return urljoin(BASE, value)
    return None


def recursive_image(obj) -> str | None:
    for node in walk_json(obj):
        for key, value in node.items():
            if isinstance(value, str) and value.startswith("http") and ("image" in str(key).lower() or str(key).lower() in ("src", "url")):
                if "/images" in value or re.search(r"\.(?:jpg|jpeg|png|webp)(?:\?|$)", value, re.I):
                    return value
    return None


def parse_text_nutrition(text: str) -> dict[str, float | None]:
    section = text
    m = re.search(r"(?:Datos|Informaci[oó]n) nutricionales?\s*(.+?)(?=Ingredientes|Al[eé]rgenos|Caracter[ií]sticas|Conservaci[oó]n|Productos similares|Opiniones|$)", text, re.I | re.S)
    if m:
        section = m.group(1)

    def val(patterns: tuple[str, ...], unit: str = "g") -> float | None:
        for pattern in patterns:
            mm = re.search(pattern + rf"[^0-9]{{0,35}}([0-9]+(?:[.,][0-9]+)?)\s*{unit}", section, re.I)
            if mm:
                return number(mm.group(1))
        return None

    kcal = None
    for p in (
        r"Valor energ[eé]tico\s*\(Kcal\)", r"Energ[ií]a[^\n]{0,30}", r"Valor energ[eé]tico[^\n]{0,30}"
    ):
        mm = re.search(p + r"[^0-9]{0,30}([0-9]+(?:[.,][0-9]+)?)\s*kcal", section, re.I)
        if mm:
            kcal = number(mm.group(1)); break
    return {
        "calories": kcal,
        "fat_g": val((r"Grasas?(?!\s+saturadas)",)),
        "carbohydrate_g": val((r"Hidratos?\s+de\s+carbono", r"Carbohidratos?")),
        "protein_g": val((r"Prote[ií]nas?",)),
        "fiber_g": val((r"Fibra(?:\s+alimentaria)?",)),
        "salt_g": val((r"Sal",)),
    }


def parse_json_nutrition(payload) -> dict[str, float | None]:
    # Alcampo schemas have changed over time. Prefer semantic key/value pairs when present.
    result = {"calories": None, "fat_g": None, "carbohydrate_g": None, "protein_g": None, "fiber_g": None, "salt_g": None}
    labels = {
        "calories": ("kcal", "energykcal", "energy-kcal", "valorenergeticokcal"),
        "fat_g": ("fat", "grasas", "grasa"),
        "carbohydrate_g": ("carbohydrate", "carbohydrates", "hidratosdecarbono"),
        "protein_g": ("protein", "proteins", "proteina", "proteinas"),
        "fiber_g": ("fiber", "fibre", "fibra"),
        "salt_g": ("salt", "sal"),
    }
    for node in walk_json(payload):
        # Flat direct keys.
        for target, names in labels.items():
            if result[target] is not None:
                continue
            for key, value in node.items():
                nk = norm_key(str(key))
                if any(n == nk or n in nk for n in names) and isinstance(value, (str, int, float)):
                    candidate = number(value)
                    if candidate is not None:
                        result[target] = candidate
                        break
        # Label/value rows.
        label = None
        for k in ("name", "label", "description", "nutrient", "title"):
            if isinstance(node.get(k), str):
                label = norm_key(node[k]); break
        if label:
            raw_value = None
            for k in ("value", "amount", "quantity", "per100g", "per100", "nutrientValue"):
                if k in node and isinstance(node[k], (str, int, float)):
                    raw_value = node[k]; break
            if raw_value is not None:
                for target, names in labels.items():
                    if result[target] is None and any(n in label for n in names):
                        result[target] = number(raw_value)
    return result


def extract_text_field(text: str, patterns: tuple[str, ...], stops: tuple[str, ...]) -> str | None:
    stop = "|".join(re.escape(x) for x in stops)
    for pattern in patterns:
        m = re.search(pattern + r"\s*(.+?)(?=\n(?:" + stop + r")|(?:" + stop + r")|$)", text, re.I | re.S)
        if m:
            value = clean(m.group(1))
            if value and len(value) < 8000:
                return value
    return None


@dataclass
class Product:
    sku: str
    url: str | None = None
    name: str | None = None
    brand: str | None = None
    gtin: str | None = None
    legal_name: str | None = None
    ingredients: str | None = None
    category: str | None = None
    image_url: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    carbohydrate_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None
    salt_g: float | None = None
    nutrition_status: str = "DECLARED_INCOMPLETE"
    detail_error: str | None = None
    raw_listing: dict | None = field(default=None, repr=False)

    def merge_listing(self, record: dict, category: str | None = None):
        self.raw_listing = self.raw_listing or record
        self.name = self.name or clean(record.get("name"))
        self.brand = self.brand or clean(record.get("brand"))
        self.category = self.category or category
        self.url = self.url or recursive_url(record)
        self.image_url = self.image_url or recursive_image(record)
        gtin = recursive_scalar(record, ("gtin", "gtin13", "ean", "barcode"))
        if gtin and re.fullmatch(r"\d{8,14}", str(gtin)):
            self.gtin = self.gtin or str(gtin)


class Collector:
    def __init__(self):
        self.products: dict[str, Product] = {}
        self.api_responses = 0
        self.api_errors = 0
        self.lock = asyncio.Lock()

    async def ingest_payload(self, payload, category: str | None = None):
        records = product_records(payload)
        if not records:
            return
        async with self.lock:
            for rec in records:
                sku = str(rec.get("retailerProductId") or rec.get("retailer_product_id"))
                product = self.products.setdefault(sku, Product(sku=sku))
                product.merge_listing(rec, category)


async def main_content_links(page, needle: str) -> list[tuple[str, str]]:
    selector = f'main a[href*="{needle}"]'
    if await page.locator("main").count() == 0:
        selector = f'a[href*="{needle}"]'
    rows = await page.eval_on_selector_all(
        selector,
        "els => els.map(a => [(a.innerText || a.getAttribute('aria-label') || '').trim(), a.href])",
    )
    out = []
    for text, href in rows:
        if href and same_host(href):
            out.append((clean(text) or "", href.split("#")[0]))
    return out


async def seed_categories(page) -> list[tuple[str, str]]:
    await page.goto(ROOT, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(1800)
    links = await main_content_links(page, "/categories/")
    seeds = []
    for label, href in links:
        hay = unquote((label + " " + href).lower())
        if any(term in hay for term in FOOD_ROOT_TERMS) and not DENY.search(hay):
            seeds.append((href.split("?")[0], label or href))
    if not seeds:
        seeds = [
            (BASE + "/categories/alimentaci%C3%B3n/OCC10", "Alimentación"),
            (BASE + "/categories/frescos/OC17", "Frescos"),
        ]
    return list(dict.fromkeys(seeds))


async def settle_category(page, collector: Collector, label: str, rounds: int = 36):
    stable = 0
    last_count = -1
    last_height = -1
    for _ in range(rounds):
        links = await main_content_links(page, "/products/")
        async with collector.lock:
            for text, href in links:
                sku = sku_from_url(href)
                if not sku:
                    continue
                product = collector.products.setdefault(sku, Product(sku=sku))
                product.url = product.url or href.split("?")[0]
                product.name = product.name or clean(text)
                product.category = product.category or label
            count = len(collector.products)
        try:
            height = await page.evaluate("document.body.scrollHeight")
        except Exception:
            height = -1
        if count == last_count and height == last_height:
            stable += 1
        else:
            stable = 0
        last_count, last_height = count, height
        if stable >= 5:
            break
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(700)
        for selector in (
            "text=/ver más/i", "text=/cargar más/i", "text=/mostrar más/i",
            "button[aria-label*=siguiente i]", "a[aria-label*=siguiente i]",
        ):
            try:
                loc = page.locator(selector).first
                if await loc.count() and await loc.is_visible():
                    await loc.click(timeout=1200)
                    await page.wait_for_timeout(900)
            except Exception:
                pass


async def discover_catalog(context, max_categories: int = 0) -> tuple[Collector, dict]:
    page = await context.new_page()
    collector = Collector()
    current_category = {"label": None}

    async def on_response(resp):
        if "/api/" not in resp.url:
            return
        try:
            ct = resp.headers.get("content-type", "")
            if "json" not in ct.lower():
                return
            payload = await resp.json()
            collector.api_responses += 1
            await collector.ingest_payload(payload, current_category["label"])
        except Exception:
            collector.api_errors += 1

    page.on("response", on_response)
    seeds = await seed_categories(page)
    queue = list(seeds)
    seen: dict[str, str] = {}
    errors = []

    while queue:
        if max_categories and len(seen) >= max_categories:
            break
        url, label = queue.pop(0)
        url = url.split("?")[0]
        if url in seen:
            continue
        hay = unquote((label + " " + url).lower())
        if DENY.search(hay):
            continue
        seen[url] = label
        current_category["label"] = label
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(1200)
            await settle_category(page, collector, label)
            sublinks = await main_content_links(page, "/categories/")
            for text, href in sublinks:
                href0 = href.split("?")[0]
                ctx = unquote((text + " " + href0).lower())
                if DENY.search(ctx) or href0 in seen:
                    continue
                queue.append((href0, text or label))
        except Exception as exc:
            errors.append([url, f"{type(exc).__name__}:{exc}"])
        if len(seen) % 10 == 0:
            print(f"discovery categories={len(seen)} products={len(collector.products)} queue={len(queue)} api={collector.api_responses}", flush=True)

    await page.close()
    meta = {
        "root": ROOT,
        "seed_categories": len(seeds),
        "categories_visited": len(seen),
        "category_errors": len(errors),
        "products_discovered": len(collector.products),
        "api_json_responses": collector.api_responses,
        "api_parse_errors": collector.api_errors,
        "version": VERSION,
    }
    return collector, meta


async def parse_detail(context, product: Product, semaphore: asyncio.Semaphore):
    if not product.url:
        product.detail_error = "NO_PRODUCT_URL"
        return
    async with semaphore:
        page = await context.new_page()
        payloads = []

        async def on_response(resp):
            if "/api/" not in resp.url:
                return
            try:
                if "json" in resp.headers.get("content-type", "").lower():
                    payloads.append(await resp.json())
            except Exception:
                pass

        page.on("response", on_response)
        try:
            await page.goto(product.url, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(1800)
            text = await page.locator("body").inner_text()
            if await page.locator("h1").count():
                product.name = clean(await page.locator("h1").first.inner_text()) or product.name

            for payload in payloads:
                # Prefer the record matching this SKU when product endpoint returns a batch.
                for rec in product_records(payload):
                    if str(rec.get("retailerProductId")) == product.sku:
                        product.merge_listing(rec, product.category)
                product.brand = product.brand or clean(str(recursive_scalar(payload, ("brand",)) or ""))
                product.legal_name = product.legal_name or clean(str(recursive_scalar(payload, ("legalName", "legal_name", "regulatedProductName", "regulatedName")) or ""))
                product.ingredients = product.ingredients or clean(str(recursive_scalar(payload, ("ingredients", "ingredientsText", "ingredientStatement")) or ""))
                gtin = recursive_scalar(payload, ("gtin", "gtin13", "ean", "barcode"))
                if gtin and re.fullmatch(r"\d{8,14}", str(gtin)):
                    product.gtin = product.gtin or str(gtin)

            product.legal_name = product.legal_name or extract_text_field(
                text, (r"Denominaci[oó]n legal(?: del alimento)?\s*[:|]?", r"Denominaci[oó]n del alimento\s*[:|]?"),
                ("Ingredientes", "Alérgenos", "Datos nutricionales", "Información nutricional", "Características"),
            )
            product.ingredients = product.ingredients or extract_text_field(
                text, (r"Ingredientes\s*[:|]?",),
                ("Alérgenos", "Datos nutricionales", "Información nutricional", "Características", "Conservación", "Almacenamiento"),
            )

            nt = parse_text_nutrition(text)
            for payload in payloads:
                nj = parse_json_nutrition(payload)
                for key, value in nj.items():
                    if nt.get(key) is None and value is not None:
                        nt[key] = value
            product.calories = nt["calories"]
            product.fat_g = nt["fat_g"]
            product.carbohydrate_g = nt["carbohydrate_g"]
            product.protein_g = nt["protein_g"]
            product.fiber_g = nt["fiber_g"]
            product.salt_g = nt["salt_g"]
            if all(v is not None for v in (product.calories, product.protein_g, product.carbohydrate_g, product.fat_g)):
                vr = validate_nutrition(product.calories, product.protein_g, product.carbohydrate_g, product.fat_g, product.fiber_g, product.salt_g)
                product.nutrition_status = "DECLARED_VALID" if vr.valid else "DECLARED_INVALID:" + ",".join(vr.reasons)
            else:
                product.nutrition_status = "DECLARED_INCOMPLETE"
        except Exception as exc:
            product.detail_error = f"{type(exc).__name__}:{exc}"
        finally:
            await page.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY, gtin TEXT, canonical_name TEXT NOT NULL, brand TEXT, legal_name TEXT, ingredients TEXT
);
CREATE TABLE IF NOT EXISTS retailer_listings(
  id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, retailer TEXT NOT NULL, retailer_sku TEXT NOT NULL,
  context TEXT NOT NULL, display_name TEXT NOT NULL, url TEXT, availability TEXT NOT NULL, observed_at TEXT NOT NULL,
  UNIQUE(retailer, retailer_sku, context)
);
CREATE TABLE IF NOT EXISTS nutrition(
  product_id INTEGER PRIMARY KEY, basis TEXT NOT NULL, calories REAL, fat_g REAL, carbohydrate_g REAL,
  protein_g REAL, fiber_g REAL, saturated_fat_g REAL, sugar_g REAL, salt_g REAL, source TEXT NOT NULL,
  evidence_level TEXT NOT NULL, confidence REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS eligibility(
  product_id INTEGER PRIMARY KEY, discoverable INTEGER NOT NULL, identified INTEGER NOT NULL,
  nutritionally_usable INTEGER NOT NULL, classified INTEGER NOT NULL, menu_eligible INTEGER NOT NULL, reason TEXT
);
CREATE TABLE IF NOT EXISTS catalog_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS product_images(
  id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, kind TEXT NOT NULL, url TEXT NOT NULL, source TEXT NOT NULL,
  source_record_id TEXT, license TEXT, attribution TEXT, redistributable INTEGER NOT NULL DEFAULT 0,
  width INTEGER, height INTEGER, is_primary INTEGER NOT NULL DEFAULT 0, observed_at TEXT NOT NULL,
  UNIQUE(product_id,kind,url)
);
"""


def write_outputs(out: Path, products: list[Product], discovery: dict) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with (out / "observations.jsonl").open("w", encoding="utf-8") as fh:
        for p in products:
            row = asdict(p); row.pop("raw_listing", None)
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out / "listing_records.jsonl").open("w", encoding="utf-8") as fh:
        for p in products:
            if p.raw_listing is not None:
                fh.write(json.dumps({"sku": p.sku, "record": p.raw_listing}, ensure_ascii=False) + "\n")

    db_path = out / "alcampo_food_catalog.sqlite"
    db_path.unlink(missing_ok=True)
    con = sqlite3.connect(db_path); con.executescript(SCHEMA)
    for key, value in {
        "schema_version": "4", "source": BASE, "retailer": "Alcampo", "context": "Spain-online",
        "importer_version": VERSION, "built_at": ts, "third_party_product_data": "false",
    }.items():
        con.execute("INSERT INTO catalog_metadata VALUES(?,?)", (key, str(value)))
    for p in products:
        pid = stable_id("alcampo-sku", p.sku)
        name = p.name or f"Alcampo SKU {p.sku}"
        con.execute("INSERT INTO products VALUES(?,?,?,?,?,?)", (pid, p.gtin, name, p.brand, p.legal_name, p.ingredients))
        con.execute(
            "INSERT INTO retailer_listings(product_id,retailer,retailer_sku,context,display_name,url,availability,observed_at) VALUES(?,?,?,?,?,?,?,?)",
            (pid, "Alcampo", p.sku, "Spain-online", name, p.url, "ACTIVE", ts),
        )
        nutrition_ok = p.nutrition_status == "DECLARED_VALID"
        if any(v is not None for v in (p.calories, p.protein_g, p.carbohydrate_g, p.fat_g)):
            con.execute(
                "INSERT INTO nutrition VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pid, "100_g", p.calories, p.fat_g, p.carbohydrate_g, p.protein_g, p.fiber_g, None, None, p.salt_g,
                 "Alcampo declared", "DECLARED", 1.0 if nutrition_ok else 0.5),
            )
        identified = bool(p.name)
        reason = None if nutrition_ok else (p.detail_error or "Falta nutrición declarada completa")
        con.execute("INSERT INTO eligibility VALUES(?,?,?,?,?,?,?)", (pid, 1, int(identified), int(nutrition_ok), 0, 0, reason))
        if p.image_url:
            con.execute(
                "INSERT OR IGNORE INTO product_images(product_id,kind,url,source,source_record_id,redistributable,is_primary,observed_at) VALUES(?,?,?,?,?,?,?,?)",
                (pid, "front", p.image_url, "Alcampo", p.sku, 0, 1, ts),
            )
    con.commit(); con.close()

    counts = {
        "discovered": len(products),
        "identified": sum(bool(p.name) for p in products),
        "with_product_url": sum(bool(p.url) for p in products),
        "with_gtin": sum(bool(p.gtin) for p in products),
        "with_ingredients": sum(bool(p.ingredients) for p in products),
        "with_legal_name": sum(bool(p.legal_name) for p in products),
        "with_image": sum(bool(p.image_url) for p in products),
        "declared_valid_nutrition": sum(p.nutrition_status == "DECLARED_VALID" for p in products),
        "declared_incomplete_nutrition": sum(p.nutrition_status == "DECLARED_INCOMPLETE" for p in products),
        "declared_invalid_nutrition": sum(p.nutrition_status.startswith("DECLARED_INVALID") for p in products),
        "detail_errors": sum(bool(p.detail_error) for p in products),
    }
    summary = {
        "retailer": "ALCAMPO", "source": BASE, "importer_version": VERSION,
        "built_at": ts, "discovery": discovery, "counts": counts, "third_party_product_data": False,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


async def run(args) -> dict:
    out = Path(args.out)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(locale="es-ES", user_agent=UA)
        collector, discovery = await discover_catalog(context, args.max_categories)
        products = sorted(collector.products.values(), key=lambda p: int(p.sku) if p.sku.isdigit() else p.sku)
        if args.max_products:
            products = products[:args.max_products]
        print(f"discovered_unique={len(collector.products)} detail_target={len(products)}", flush=True)
        sem = asyncio.Semaphore(max(1, args.workers))
        done = 0
        lock = asyncio.Lock()

        async def one(p):
            nonlocal done
            await parse_detail(context, p, sem)
            async with lock:
                done += 1
                if done % 50 == 0 or done == len(products):
                    valid = sum(x.nutrition_status == "DECLARED_VALID" for x in products[:done])
                    errors = sum(bool(x.detail_error) for x in products[:done])
                    print(f"detail={done}/{len(products)} valid~={valid} errors~={errors}", flush=True)

        await asyncio.gather(*(one(p) for p in products))
        await browser.close()
    return write_outputs(out, products, discovery)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="alcampo-direct-v4-output")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-categories", type=int, default=0)
    ap.add_argument("--max-products", type=int, default=0)
    ap.add_argument("--min-discovered", type=int, default=1)
    ap.add_argument("--min-valid-nutrition", type=int, default=0)
    args = ap.parse_args()
    summary = asyncio.run(run(args))
    discovered_total = int(summary["discovery"]["products_discovered"])
    valid = int(summary["counts"]["declared_valid_nutrition"])
    return 0 if discovered_total >= args.min_discovered and valid >= args.min_valid_nutrition else 2


if __name__ == "__main__":
    raise SystemExit(main())
