from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import sqlite3
import time
import urllib.parse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "https://www.compraonline.alcampo.es"
CATALOGUE_ENDPOINT = BASE + "/api/webproductpagews/v6/product-pages"
VERSION = "alcampo-direct-v6.0"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36"
PAGE_SIZE = 300

# First-party retailer category IDs taken from Alcampo's own category URLs.
FOOD_ROOTS = [
    ("Frescos", "OC2112"),
    ("Leche, Huevos, Lácteos, Yogures y Bebidas vegetales", "OC16"),
    ("Alimentación", "OCC10"),
    ("Desayuno y Merienda", "OC10"),
    ("Congelados", "OC200220183"),
    ("Comida Preparada", "OC20022018"),
    ("Supermercado Ecológico", "OC26112021"),
    ("Bebidas", "OCC11"),
    ("Sin Gluten / Sin Lactosa, Nutrición deportiva y Funcional", "OCSINGSINL"),
    ("Veganos", "OC09112021"),
]
ALCOHOL_BRANCH = re.compile(r"\b(vino|vinos|cerveza|cervezas|licor|licores|whisky|whiskey|ron|ginebra|vodka|brandy|cognac|champagne|cava|sidra|vermut|vermouth|sangr[ií]a|espirituosas?)\b", re.I)


def api_json(url: str, timeout: int = 90):
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9",
        "Referer": BASE + "/categories?source=navigation",
        "Cache-Control": "no-cache",
    })
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def page_url(retailer_category_id: str, page_token: str | None = None) -> str:
    params = [
        ("maxProductsToDecorate", str(PAGE_SIZE)),
        ("maxPageSize", str(PAGE_SIZE)),
        ("includeAdditionalPageInfo", "false" if page_token else "true"),
        ("retailerCategoryId", retailer_category_id),
    ]
    if page_token:
        params.append(("pageToken", page_token))
    return CATALOGUE_ENDPOINT + "?" + urllib.parse.urlencode(params)


def recursive_url(obj) -> str | None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and "/products/" in v and ("url" in k.lower() or "href" in k.lower() or "path" in k.lower()):
                return urllib.parse.urljoin(BASE, v)
        for v in obj.values():
            u = recursive_url(v)
            if u: return u
    elif isinstance(obj, list):
        for v in obj:
            u = recursive_url(v)
            if u: return u
    return None


def first_image(obj: dict) -> str | None:
    image = obj.get("image") or {}
    if isinstance(image, dict) and isinstance(image.get("src"), str): return image["src"]
    images = obj.get("images") or []
    if images and isinstance(images[0], dict): return images[0].get("src")
    return None


def amount(obj) -> float | None:
    try: return float(obj)
    except (TypeError, ValueError): return None


@dataclass
class Product:
    product_id: str
    sku: str | None
    name: str | None
    brand: str | None
    pack_size: str | None
    category_path: list[str]
    alcohol: bool | None
    available: bool | None
    image_url: str | None
    product_url: str | None
    price_eur: float | None
    unit_price_eur: float | None
    unit_price_unit: str | None
    source_roots: list[str]
    evidence_endpoint: str = CATALOGUE_ENDPOINT


def map_product(raw: dict, root_label: str) -> Product | None:
    pid = raw.get("productId")
    if not pid: return None
    price = raw.get("price") or {}
    unit = raw.get("unitPrice") or {}
    unit_price = unit.get("price") or {}
    return Product(
        product_id=str(pid),
        sku=str(raw.get("retailerProductId")) if raw.get("retailerProductId") is not None else None,
        name=raw.get("name") if isinstance(raw.get("name"), str) else None,
        brand=raw.get("brand") if isinstance(raw.get("brand"), str) else None,
        pack_size=raw.get("packSizeDescription") if isinstance(raw.get("packSizeDescription"), str) else None,
        category_path=[str(x) for x in (raw.get("categoryPath") or [])],
        alcohol=raw.get("alcohol") if isinstance(raw.get("alcohol"), bool) else None,
        available=raw.get("available") if isinstance(raw.get("available"), bool) else None,
        image_url=first_image(raw),
        product_url=recursive_url(raw),
        price_eur=amount(price.get("amount")) if isinstance(price, dict) else None,
        unit_price_eur=amount(unit_price.get("amount")) if isinstance(unit_price, dict) else None,
        unit_price_unit=(unit.get("unitName") or unit.get("unit")) if isinstance(unit, dict) else None,
        source_roots=[root_label],
    )


def merge(a: Product, b: Product) -> Product:
    roots = list(dict.fromkeys(a.source_roots + b.source_roots))
    # Prefer whichever occurrence provides richer category path / URL / identity fields.
    richer = b if len(b.category_path) > len(a.category_path) else a
    return Product(
        product_id=a.product_id,
        sku=a.sku or b.sku,
        name=a.name or b.name,
        brand=a.brand or b.brand,
        pack_size=a.pack_size or b.pack_size,
        category_path=richer.category_path or a.category_path or b.category_path,
        alcohol=a.alcohol if a.alcohol is not None else b.alcohol,
        available=(a.available is True or b.available is True) if (a.available is not None or b.available is not None) else None,
        image_url=a.image_url or b.image_url,
        product_url=a.product_url or b.product_url,
        price_eur=a.price_eur if a.price_eur is not None else b.price_eur,
        unit_price_eur=a.unit_price_eur if a.unit_price_eur is not None else b.unit_price_eur,
        unit_price_unit=a.unit_price_unit or b.unit_price_unit,
        source_roots=roots,
    )


def allowed_food(p: Product) -> bool:
    if p.alcohol is True:
        return False
    context = " ".join([p.name or "", *p.category_path])
    if ALCOHOL_BRANCH.search(context) and not re.search(r"\bsin\s+alcohol\b", context, re.I):
        return False
    return True


def collect_root(label: str, rid: str, max_pages: int = 0) -> tuple[list[Product], dict]:
    products: dict[str, Product] = {}
    page_token = None
    token_seen = set()
    pages = 0
    errors = []
    child_categories = []
    while True:
        if max_pages and pages >= max_pages: break
        url = page_url(rid, page_token)
        try:
            payload = api_json(url)
        except Exception as exc:
            errors.append(f"{type(exc).__name__}:{exc}")
            break
        pages += 1
        if pages == 1:
            info = payload.get("additionalPageInfo") or {}
            for c in info.get("categories") or []:
                if isinstance(c, dict):
                    child_categories.append({k:c.get(k) for k in ("name","categoryId","retailerCategoryId","productCount")})
        decorated = 0
        other_ids = 0
        for group in payload.get("productGroups") or []:
            if not isinstance(group, dict): continue
            for raw in group.get("decoratedProducts") or []:
                if not isinstance(raw, dict): continue
                p = map_product(raw, label)
                if not p: continue
                decorated += 1
                if p.product_id in products: products[p.product_id] = merge(products[p.product_id], p)
                else: products[p.product_id] = p
            other_ids += len(group.get("otherProductIds") or [])
        next_token = (payload.get("metadata") or {}).get("nextPageToken")
        print(f"root={rid} page={pages} decorated={decorated} other_ids={other_ids} unique={len(products)} next={bool(next_token)}", flush=True)
        if not next_token or next_token in token_seen: break
        token_seen.add(next_token); page_token = next_token
        time.sleep(0.08)
    return list(products.values()), {
        "label": label,
        "retailer_category_id": rid,
        "pages": pages,
        "unique_decorated_products": len(products),
        "errors": errors,
        "child_categories": child_categories,
    }


def write_outputs(out: Path, products: list[Product], roots_meta: list[dict]) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    before = len(products)
    kept = [p for p in products if allowed_food(p)]
    excluded = before - len(kept)
    kept.sort(key=lambda p: ((int(p.sku) if p.sku and p.sku.isdigit() else 10**20), p.sku or "", p.product_id))
    with (out/"products.jsonl").open("w", encoding="utf-8") as f:
        for p in kept: f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")
    db=sqlite3.connect(out/"alcampo_food_catalog.sqlite")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS products(
      retailer TEXT NOT NULL, product_id TEXT NOT NULL, sku TEXT, name TEXT, brand TEXT, pack_size TEXT,
      category_path_json TEXT, alcohol INTEGER, available INTEGER, image_url TEXT, product_url TEXT,
      price_eur REAL, unit_price_eur REAL, unit_price_unit TEXT, source_roots_json TEXT, evidence_endpoint TEXT,
      PRIMARY KEY(retailer,product_id));
    CREATE INDEX IF NOT EXISTS idx_alcampo_sku ON products(retailer,sku);
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
    """)
    for p in kept:
        db.execute("INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
            "ALCAMPO", p.product_id, p.sku, p.name, p.brand, p.pack_size,
            json.dumps(p.category_path,ensure_ascii=False), None if p.alcohol is None else int(p.alcohol),
            None if p.available is None else int(p.available), p.image_url, p.product_url, p.price_eur,
            p.unit_price_eur, p.unit_price_unit, json.dumps(p.source_roots,ensure_ascii=False), p.evidence_endpoint))
    built=datetime.now(timezone.utc).isoformat()
    for k,v in {"source":BASE,"catalogue_endpoint":CATALOGUE_ENDPOINT,"importer_version":VERSION,"built_at":built,"third_party_product_data":"false"}.items():
        db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)",(k,v))
    db.commit(); db.close()
    summary={
        "retailer":"ALCAMPO","source":BASE,"catalogue_endpoint":CATALOGUE_ENDPOINT,"importer_version":VERSION,"built_at":built,
        "roots":roots_meta,
        "counts":{
            "unique_products_before_filter":before,"food_products":len(kept),"excluded_alcohol":excluded,
            "with_sku":sum(bool(p.sku) for p in kept),"with_name":sum(bool(p.name) for p in kept),"with_brand":sum(bool(p.brand) for p in kept),
            "with_pack_size":sum(bool(p.pack_size) for p in kept),"with_image":sum(bool(p.image_url) for p in kept),"with_product_url":sum(bool(p.product_url) for p in kept),
            "available":sum(p.available is True for p in kept),
        },
        "third_party_product_data":False,
    }
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return summary


def run(out: Path, only_root: str|None, max_pages: int, workers: int):
    roots=FOOD_ROOTS
    if only_root:
        roots=[x for x in FOOD_ROOTS if x[1]==only_root or x[0].lower()==only_root.lower()]
        if not roots and only_root.startswith("OC"): roots=[(only_root,only_root)]
    all_products: dict[str,Product]={}; roots_meta=[]
    def job(x): return x, collect_root(x[0],x[1],max_pages)
    with cf.ThreadPoolExecutor(max_workers=max(1,min(workers,len(roots) or 1))) as ex:
        for (_root,(plist,meta)) in ex.map(job,roots):
            roots_meta.append(meta)
            for p in plist:
                if p.product_id in all_products: all_products[p.product_id]=merge(all_products[p.product_id],p)
                else: all_products[p.product_id]=p
    return write_outputs(out,list(all_products.values()),roots_meta)


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--out",default="alcampo-direct-v6-output"); ap.add_argument("--only-root"); ap.add_argument("--max-pages",type=int,default=0); ap.add_argument("--workers",type=int,default=2); ap.add_argument("--min-products",type=int,default=1)
    a=ap.parse_args(); summary=run(Path(a.out),a.only_root,a.max_pages,a.workers)
    return 0 if summary["counts"]["food_products"]>=a.min_products else 2

if __name__=="__main__": raise SystemExit(main())
