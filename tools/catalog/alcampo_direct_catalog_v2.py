from __future__ import annotations

import argparse
import asyncio
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from nutrition_validation import validate_nutrition

BASE = "https://www.compraonline.alcampo.es"
ROOT = BASE + "/categories"
VERSION = "alcampo-direct-v2.0"

FOOD_ROOT_TERMS = (
    "frescos",
    "leche",
    "huevos",
    "lácteos",
    "lacteos",
    "yogures",
    "bebidas vegetales",
    "alimentación",
    "alimentacion",
    "desayuno",
    "merienda",
    "congelados",
    "comida preparada",
    "ecológico",
    "ecologico",
    "bebidas",
    "sin gluten",
    "sin lactosa",
    "nutrición deportiva",
    "nutricion deportiva",
    "funcional",
    "veganos",
)

DENY = re.compile(
    r"\b(vino|vinos|cerveza|cervezas|licor|licores|whisky|whiskey|ron|ginebra|vodka|brandy|cognac|champagne|cava|sidra|vermut|vermouth|sangr[ií]a|alcohol|bebidas espirituosas)\b",
    re.I,
)


@dataclass
class Observation:
    url: str
    sku: str
    name: str | None
    brand: str | None
    gtin: str | None
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
    error: str | None = None


def clean(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"\s+", " ", s).strip(" :-\n\t")
    return s or None


def num(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r"[-+]?\d+(?:[.,]\d+)?", s.replace("\xa0", " "))
    return float(m.group(0).replace(",", ".")) if m else None


def same_host(url: str) -> bool:
    return urlparse(url).netloc == urlparse(BASE).netloc


async def collect_links(page) -> list[tuple[str, str]]:
    rows = await page.eval_on_selector_all(
        "a[href]",
        "els => els.map(a => [(a.innerText || a.getAttribute('aria-label') || '').trim(), a.href])",
    )
    return [(clean(t) or "", h.split("#")[0]) for t, h in rows if h and same_host(h)]


async def settle_and_scroll(page, max_rounds: int = 35) -> None:
    stable = 0
    last_products = -1
    for _ in range(max_rounds):
        n = await page.locator('a[href*="/products/"]').count()
        if n == last_products:
            stable += 1
        else:
            stable = 0
        last_products = n
        if stable >= 4:
            break
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(450)


async def discover(page) -> tuple[list[tuple[str, str]], dict]:
    await page.goto(ROOT, wait_until="domcontentloaded", timeout=60000)
    await settle_and_scroll(page, 12)
    root_links = await collect_links(page)

    seeds: list[tuple[str, str]] = []
    for label, href in root_links:
        if "/categories/" not in href:
            continue
        hay = (label + " " + href.replace("-", " ")).lower()
        if any(term in hay for term in FOOD_ROOT_TERMS) and not DENY.search(hay):
            seeds.append((label or href, href.split("?")[0]))

    # Known stable fallback if top-level labels/layout change.
    if not seeds:
        seeds = [("Alimentación", BASE + "/categories/alimentaci%C3%B3n/OCC10")]

    category_seen: dict[str, str] = {}
    product_to_category: dict[str, str] = {}
    queue = list(dict.fromkeys((u, l) for l, u in seeds))

    while queue and len(category_seen) < 600:
        url, label = queue.pop(0)
        url = url.split("?")[0]
        if url in category_seen:
            continue
        hay = (label + " " + url.replace("-", " ")).lower()
        if DENY.search(hay):
            continue
        category_seen[url] = label
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await settle_and_scroll(page)
            links = await collect_links(page)
        except Exception:
            continue

        for text, href in links:
            href0 = href.split("?")[0]
            context = (text + " " + href0.replace("-", " ")).lower()
            if DENY.search(context):
                continue
            if "/products/" in href0:
                # Product URLs end in numeric retailer SKU.
                if re.search(r"/products/.+/\d+/?$", href0):
                    product_to_category.setdefault(href0.rstrip("/"), label)
            elif "/categories/" in href0 and href0 not in category_seen:
                # Stay inside descendants exposed from food roots; non-food cross-links are filtered by deny and root traversal.
                queue.append((href0, text or label))

        if len(category_seen) % 20 == 0:
            print(f"discovery categories={len(category_seen)} products={len(product_to_category)} queue={len(queue)}", flush=True)

    refs = sorted(product_to_category.items())
    meta = {
        "root": ROOT,
        "seed_categories": len(seeds),
        "categories_visited": len(category_seen),
        "products_discovered": len(refs),
        "version": VERSION,
    }
    return refs, meta


def first(patterns: list[str], raw: str) -> str | None:
    for p in patterns:
        m = re.search(p, raw, re.I | re.S)
        if m:
            return clean(m.group(1))
    return None


async def parse_product(page, url: str, category: str) -> Observation:
    sku = url.rstrip("/").split("/")[-1]
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(200)
        text = await page.locator("body").inner_text()
        html = await page.content()
        name = clean(await page.locator("h1").first.inner_text()) if await page.locator("h1").count() else None
        brand = first([r'"brand"\s*:\s*"([^"]+)"', r'"brand"\s*:\s*\{[^{}]*"name"\s*:\s*"([^"]+)"'], html)
        gtin = first([r'"gtin13"\s*:\s*"(\d{8,14})"', r'"gtin"\s*:\s*"(\d{8,14})"', r'"ean"\s*:\s*"(\d{8,14})"'], html)

        legal = None
        lm = re.search(r"Denominaci[oó]n legal del alimento\s*[|:]?\s*(.+?)(?=\n|Ingredientes|##|$)", text, re.I)
        if lm:
            legal = clean(lm.group(1))
        if not legal:
            legal = first([r'"legalName"\s*:\s*"([^"]+)"'], html)

        ingredients = None
        im = re.search(r"Ingredientes\s*(?:Ingredientes:)?\s*(.+?)(?=Características|Datos nutricionales|Alérgenos|Almacenamiento|##|$)", text, re.I | re.S)
        if im:
            ingredients = clean(im.group(1))
        if not ingredients:
            ingredients = first([r'"ingredients"\s*:\s*"([^"]+)"'], html)

        nm = re.search(r"Datos nutricionales\s*(.+?)(?=Productos similares|Opiniones de los clientes|## [A-ZÁÉÍÓÚÑ]|$)", text, re.I | re.S)
        nutrition = nm.group(1) if nm else ""
        kcal = num(re.search(r"Valor energ[eé]tico \(Kcal\)\s*[|:]?\s*([0-9]+(?:[.,][0-9]+)?)", nutrition, re.I).group(1)) if re.search(r"Valor energ[eé]tico \(Kcal\)\s*[|:]?\s*([0-9]+(?:[.,][0-9]+)?)", nutrition, re.I) else None

        def g(label: str) -> float | None:
            m = re.search(label + r"\s*[|:]?\s*([0-9]+(?:[.,][0-9]+)?)\s*g", nutrition, re.I)
            return num(m.group(1)) if m else None

        fat = g(r"Grasas(?! saturadas)")
        carb = g(r"Hidratos de carbono")
        protein = g(r"Prote[ií]nas")
        fiber = g(r"Fibra(?: alimentaria)?")
        salt = g(r"Sal")

        if all(v is not None for v in (kcal, protein, carb, fat)):
            val = validate_nutrition(kcal, protein, carb, fat, fiber, salt)
            status = "DECLARED_VALID" if val.valid else "DECLARED_INVALID:" + ",".join(val.reasons)
        else:
            status = "DECLARED_INCOMPLETE"

        return Observation(url, sku, name, brand, gtin, legal, ingredients, category, kcal, protein, carb, fat, fiber, salt, status)
    except Exception as exc:
        return Observation(url, sku, None, None, None, None, None, category, None, None, None, None, None, None, "FETCH_ERROR", f"{type(exc).__name__}:{exc}")


def init_db(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS products(
      retailer TEXT NOT NULL, sku TEXT NOT NULL, url TEXT NOT NULL, name TEXT, brand TEXT, gtin TEXT,
      legal_name TEXT, ingredients TEXT, category TEXT, PRIMARY KEY(retailer, sku));
    CREATE TABLE IF NOT EXISTS nutrition(
      retailer TEXT NOT NULL, sku TEXT NOT NULL, calories REAL, protein_g REAL, carbohydrate_g REAL,
      fat_g REAL, fiber_g REAL, salt_g REAL, evidence_level TEXT, status TEXT,
      PRIMARY KEY(retailer, sku));
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT);
    """)
    return db


async def run(out: Path, workers: int, max_products: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(locale="es-ES", user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36")
        discovery_page = await context.new_page()
        refs, discovery = await discover(discovery_page)
        if max_products:
            refs = refs[:max_products]
        print(f"discovered_unique={len(refs)}", flush=True)

        q: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        for ref in refs:
            q.put_nowait(ref)
        observations: list[Observation] = []
        lock = asyncio.Lock()
        done = 0

        async def worker() -> None:
            nonlocal done
            page = await context.new_page()
            while True:
                try:
                    url, category = q.get_nowait()
                except asyncio.QueueEmpty:
                    break
                obs = await parse_product(page, url, category)
                async with lock:
                    observations.append(obs)
                    done += 1
                    if done % 100 == 0 or done == len(refs):
                        valid = sum(o.nutrition_status == "DECLARED_VALID" for o in observations)
                        errs = sum(o.error is not None for o in observations)
                        print(f"progress={done}/{len(refs)} valid={valid} errors={errs}", flush=True)
                q.task_done()
            await page.close()

        await asyncio.gather(*(worker() for _ in range(max(1, workers))))
        await browser.close()

    observations.sort(key=lambda o: o.sku)
    with (out / "observations.jsonl").open("w", encoding="utf-8") as fh:
        for o in observations:
            fh.write(json.dumps(asdict(o), ensure_ascii=False) + "\n")

    db = init_db(out / "alcampo_food_catalog.sqlite")
    for o in observations:
        db.execute("INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?,?,?,?)", ("ALCAMPO", o.sku, o.url, o.name, o.brand, o.gtin, o.legal_name, o.ingredients, o.category))
        db.execute("INSERT OR REPLACE INTO nutrition VALUES(?,?,?,?,?,?,?,?,?,?)", ("ALCAMPO", o.sku, o.calories, o.protein_g, o.carbohydrate_g, o.fat_g, o.fiber_g, o.salt_g, "DECLARED" if o.nutrition_status.startswith("DECLARED_") else None, o.nutrition_status))
    db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)", ("source", BASE))
    db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)", ("importer_version", VERSION))
    db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)", ("built_at", datetime.now(timezone.utc).isoformat()))
    db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)", ("third_party_product_data", "false"))
    db.commit(); db.close()

    counts = {
        "discovered": len(refs),
        "fetched": sum(o.error is None for o in observations),
        "fetch_errors": sum(o.error is not None for o in observations),
        "with_name": sum(bool(o.name) for o in observations),
        "with_gtin": sum(bool(o.gtin) for o in observations),
        "with_ingredients": sum(bool(o.ingredients) for o in observations),
        "with_legal_name": sum(bool(o.legal_name) for o in observations),
        "declared_valid_nutrition": sum(o.nutrition_status == "DECLARED_VALID" for o in observations),
        "declared_incomplete_nutrition": sum(o.nutrition_status == "DECLARED_INCOMPLETE" for o in observations),
        "declared_invalid_nutrition": sum(o.nutrition_status.startswith("DECLARED_INVALID") for o in observations),
    }
    summary = {
        "retailer": "ALCAMPO",
        "source": BASE,
        "importer_version": VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "discovery": discovery,
        "counts": counts,
        "third_party_product_data": False,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="alcampo-direct-v2-output")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-products", type=int, default=0)
    ap.add_argument("--min-discovered", type=int, default=1)
    args = ap.parse_args()
    summary = asyncio.run(run(Path(args.out), args.workers, args.max_products))
    return 0 if summary["counts"]["discovered"] >= args.min_discovered else 2


if __name__ == "__main__":
    raise SystemExit(main())
