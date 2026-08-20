from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

BASE = "https://www.carrefour.es"
SOURCE = "CARREFOUR_FIRST_PARTY"
VERSION = "carrefour-first-party-1.0"
DEFAULT_ROOTS = [
    "https://www.carrefour.es/supermercado/frescos/cat20002/c",
    "https://www.carrefour.es/supermercado/la-despensa/cat20001/c",
    "https://www.carrefour.es/supermercado/bebidas/cat20003/c",
    "https://www.carrefour.es/supermercado/congelados/cat21449123/c",
]
PRODUCT_RE = re.compile(r"https?://(?:www\.)?carrefour\.es/supermercado/[^\"'<>\s]+/R-[^/\"'<>\s]+/p/?", re.I)
REL_PRODUCT_RE = re.compile(r"(?:href|canonical)[=:\s]+[\"']([^\"']*/supermercado/[^\"']+/R-[^/\"']+/p/?)[\"']", re.I)
ALCOHOL_RE = re.compile(r"\b(vino|vinos|cerveza|cervezas|licor|licores|whisky|whiskey|ron|ginebra|vodka|brandy|cognac|champagne|cava|sidra)\b", re.I)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
    "Cache-Control": "no-cache",
}


def now_iso(): return datetime.now(timezone.utc).isoformat()

def clean(value):
    if value is None: return None
    value = html_lib.unescape(str(value))
    value = re.sub(r"\s+", " ", value).strip(" :-\n\t")
    return value or None

def norm_number(value):
    if value is None: return None
    m = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value).replace("\xa0", " "))
    if not m: return None
    try: return float(m.group(0).replace(",", "."))
    except ValueError: return None

def fetch(url, timeout=35, attempts=3):
    last = None
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=timeout) as response:
                raw = response.read()
                return response.status, response.geturl(), raw.decode("utf-8", "replace")
        except Exception as exc:
            last = exc
            if attempt + 1 < attempts: time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {type(last).__name__}:{last}")

def html_to_text(raw):
    raw = re.sub(r"<(?:br|/p|/li|/div|/tr|/h\d)\b[^>]*>", "\n", raw, flags=re.I)
    raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html_lib.unescape(raw).replace("\xa0", " ")
    raw = re.sub(r"[ \t\r]+", " ", raw)
    return re.sub(r"\n\s*\n+", "\n", raw).strip()

def json_ld_objects(raw):
    out = []
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', raw, re.I | re.S):
        try: obj = json.loads(html_lib.unescape(m.group(1)).strip())
        except Exception: continue
        out.extend(obj if isinstance(obj, list) else [obj])
    return out

def walk_json(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values(): yield from walk_json(value)
    elif isinstance(obj, list):
        for value in obj: yield from walk_json(value)

def first_product_ld(raw):
    for top in json_ld_objects(raw):
        for obj in walk_json(top):
            if not isinstance(obj, dict): continue
            typ = obj.get("@type")
            if "Product" in (typ if isinstance(typ, list) else [typ]): return obj
    return {}

def breadcrumb_path(raw):
    for top in json_ld_objects(raw):
        for obj in walk_json(top):
            if not isinstance(obj, dict) or obj.get("@type") != "BreadcrumbList": continue
            values = []
            for item in obj.get("itemListElement") or []:
                if not isinstance(item, dict): continue
                name = item.get("name")
                if not name and isinstance(item.get("item"), dict): name = item["item"].get("name")
                if clean(name): values.append(clean(name))
            if values: return values
    return []
def section(text, starts, ends):
    m = re.search(rf"(?:{'|'.join(re.escape(x) for x in starts)})\s*:?\s*(.+?)(?=\n\s*(?:{'|'.join(re.escape(x) for x in ends)})\s*:?|$)", text, re.I | re.S)
    return clean(m.group(1)) if m else None

def labelled_value(text, labels):
    for label in labels:
        m = re.search(rf"(?:^|\n)\s*{re.escape(label)}\s*:?\s*([^\n]+)", text, re.I)
        if m:
            value = clean(m.group(1))
            if value and value.lower() != label.lower(): return value
    return None

def product_urls_from_html(raw):
    found = set(PRODUCT_RE.findall(raw))
    for rel in REL_PRODUCT_RE.findall(raw): found.add(urljoin(BASE, html_lib.unescape(rel)))
    found.update(PRODUCT_RE.findall(raw.replace("\\/", "/")))
    return sorted(u.split("?")[0].rstrip("/") for u in found if not ALCOHOL_RE.search(u))
def discover_from_roots(roots, max_pages):
    urls, diagnostics = set(), []
    for root in roots:
        for page_no in range(1, max_pages + 1):
            candidates = [root] if page_no == 1 else [f"{root}?page={page_no}", f"{root}?pagination={page_no}"]
            page_urls, page_diag = set(), None
            for candidate in candidates:
                try:
                    status, _, raw = fetch(candidate)
                    page_urls = set(product_urls_from_html(raw))
                    page_diag = {"root":root,"page":page_no,"url":candidate,"status":status,"products":len(page_urls),"bytes":len(raw.encode())}
                    if page_urls: break
                except Exception as exc:
                    page_diag = {"root":root,"page":page_no,"url":candidate,"error":f"{type(exc).__name__}:{exc}","products":0}
            diagnostics.append(page_diag)
            before = len(urls); urls.update(page_urls)
            if page_no > 1 and (not page_urls or len(urls) == before): break
    return sorted(urls), diagnostics

def read_seed_jsonl(path):
    urls = set()
    path = Path(path)
    if not path.exists(): return []
    for line in path.read_text(encoding="utf-8").splitlines():
        try: row = json.loads(line)
        except Exception: continue
        for key in ("carrefour_url","source_product_url","product_url","url"):
            value = row.get(key)
            if isinstance(value, str) and "carrefour.es/supermercado/" in value and "/R-" in value and "/p" in value:
                urls.add(value.split("?")[0].rstrip("/")); break
    return sorted(urls)

def parse_product(url):
    observed_at = now_iso()
    m = re.search(r"/R-([^/]+)/p/?$", url, re.I)
    sku = m.group(1) if m else hashlib.sha256(url.encode()).hexdigest()[:20]
    row = {"retailer":"CARREFOUR","retailer_sku":sku,"canonical_url":url,"observed_at":observed_at,"source":SOURCE}
    evidence = []
    try:
        status, final_url, raw = fetch(url)
        row.update(http_status=status, canonical_url=final_url.split("?")[0], page_sha256=hashlib.sha256(raw.encode()).hexdigest())
        text, product, breadcrumbs = html_to_text(raw), first_product_ld(raw), breadcrumb_path(raw)
        name = clean(product.get("name"))
        if not name:
            hm = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.I | re.S); name = clean(html_to_text(hm.group(1))) if hm else None
        b = product.get("brand"); brand = clean(b.get("name")) if isinstance(b, dict) else clean(b)
        gtin = None
        for key in ("gtin14","gtin13","gtin12","gtin8","gtin","ean"):
            value = product.get(key)
            if value and re.fullmatch(r"\d{8,14}", str(value)): gtin = str(value); break
        if not gtin:
            gm = re.search(r'"(?:gtin(?:13|14|12|8)?|ean)"\s*:\s*"(\d{8,14})"', raw, re.I); gtin = gm.group(1) if gm else None
        image = product.get("image")
        if isinstance(image, list): image = image[0] if image else None
        if isinstance(image, dict): image = image.get("url") or image.get("contentUrl")
        offers = product.get("offers"); offers = offers[0] if isinstance(offers, list) and offers else offers
        offers = offers if isinstance(offers, dict) else {}
        price, currency, availability = norm_number(offers.get("price")), clean(offers.get("priceCurrency")), clean(offers.get("availability"))
        if availability and "/" in availability: availability = availability.rsplit("/",1)[-1]
        if price is None:
            pm = re.search(r"\b(\d{1,4}[.,]\d{2})\s*€", text); price = norm_number(pm.group(1)) if pm else None
        um = re.search(r"\b(\d{1,4}[.,]\d{1,3})\s*€\s*/\s*(kg|l|ud|100\s*ml|100\s*g)\b", text, re.I)
        unit_price = None
        if um:
            unit = re.sub(r"\s+", "", um.group(2)); unit_price = f"{um.group(1)} €/{unit}"
        if not availability:
            if re.search(r"Agotado temporalmente", text, re.I): availability = "OutOfStock"
            elif re.search(r"\bAñadir\b", text, re.I): availability = "InStock"
        nutrition_text = section(text,["Información nutricional","Informacion nutricional"],["Ingredientes","Alérgenos","Más información","Datos del producto","Características producto","Otra información obligatoria"])
        ingredients = section(text,["Ingredientes"],["Alérgenos","Más información","Datos del producto","Características producto","Otra información obligatoria","Información nutricional"])
        allergens = section(text,["Alérgenos","Alergenos"],["Más información","Datos del producto","Características producto","Otra información obligatoria","Información nutricional","Ingredientes"])
        legal_name = labelled_value(text,["Denominación legal","Denominacion legal"])
        net_content = labelled_value(text,["Contenido neto"])
        storage = labelled_value(text,["Condiciones de conservación","Condiciones de conservacion","Modo conservación","Modo conservacion"])
        preparation = labelled_value(text,["Modo de empleo","Instrucciones"])
        operator = labelled_value(text,["Dirección del operador de la empresa alimentaria","Direccion del operador de la empresa alimentaria"])
        manufacturer = labelled_value(text,["Razón social fabricante/envasador/importador","Razon social fabricante/envasador/importador"])
        ntext = nutrition_text or ""
        bm = re.search(r"(?:por|cada|Valores medios por)\s+100\s*(g|ml)", ntext or text, re.I); basis = "100 " + bm.group(1).lower() if bm else None
        km = re.search(r"(\d+(?:[.,]\d+)?)\s*Kcal", ntext, re.I); kcal = norm_number(km.group(1)) if km else None
        jm = re.search(r"(\d+(?:[.,]\d+)?)\s*KJ", ntext, re.I); kj = norm_number(jm.group(1)) if jm else None
        def grams(label):
            mm = re.search(label + r"[^0-9]{0,35}(\d+(?:[.,]\d+)?)\s*g", ntext, re.I)
            return norm_number(mm.group(1)) if mm else None
        vals = {
            "energy_kj":kj,"calories_kcal":kcal,
            "fat_g":grams(r"Grasas?(?:\s*\(g\))?"),"saturates_g":grams(r"(?:de las cuales\s+)?Saturadas?(?:\s*\(g\))?"),
            "carbohydrate_g":grams(r"Hidratos?\s+de\s+carbono(?:\s*\(g\))?"),"sugars_g":grams(r"(?:de los cuales\s+|de las cuales\s+)?Az[uú]cares?(?:\s*\(g\))?"),
            "fiber_g":grams(r"Fibra(?:\s+alimentaria)?(?:\s*\(g\))?"),"protein_g":grams(r"Prote[ií]nas?(?:\s*\(g\))?"),"salt_g":grams(r"Sal(?:\s*\(g\))?")}
        core = sum(vals[x] is not None for x in ("calories_kcal","fat_g","carbohydrate_g","protein_g"))
        nstatus = "DECLARED_COMPLETE" if core == 4 else ("DECLARED_PARTIAL" if any(v is not None for v in vals.values()) else "NOT_FOUND")
        row.update(name=name,brand=brand,gtin=gtin,image_url=clean(image),category_path=breadcrumbs,price_eur=price,price_currency=currency or ("EUR" if price is not None else None),unit_price_text=unit_price,availability=availability,legal_name=legal_name,ingredients=ingredients,allergens=allergens,net_content=net_content,storage_conditions=storage,preparation_instructions=preparation,operator_address=operator,manufacturer_packer_importer=manufacturer,nutrition_basis=basis,nutrition_status=nstatus,fetch_error=None,**vals)
        declared = ["name","brand","gtin","image_url","category_path","legal_name","ingredients","allergens","net_content","storage_conditions","preparation_instructions","operator_address","manufacturer_packer_importer","nutrition_basis","energy_kj","calories_kcal","fat_g","saturates_g","carbohydrate_g","sugars_g","fiber_g","protein_g","salt_g"]
        observed = ["price_eur","price_currency","unit_price_text","availability","canonical_url"]
        for field in declared + observed:
            value = row.get(field)
            if value in (None,"",[]): continue
            evidence.append({"retailer_sku":sku,"field":field,"value":value,"source":SOURCE,"evidence_type":"DECLARED" if field in declared else "OBSERVED_LISTING","source_url":row["canonical_url"],"observed_at":observed_at})
    except Exception as exc:
        row.update(fetch_error=f"{type(exc).__name__}:{exc}",nutrition_status="FETCH_ERROR")
    return row, evidence

def init_db(path):
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS products(retailer_sku TEXT PRIMARY KEY,gtin TEXT,name TEXT,brand TEXT,canonical_url TEXT,image_url TEXT,category_path_json TEXT,price_eur REAL,price_currency TEXT,unit_price_text TEXT,availability TEXT,legal_name TEXT,ingredients TEXT,allergens TEXT,net_content TEXT,storage_conditions TEXT,preparation_instructions TEXT,operator_address TEXT,manufacturer_packer_importer TEXT,observed_at TEXT,page_sha256 TEXT,http_status INTEGER,fetch_error TEXT,source TEXT);
    CREATE TABLE IF NOT EXISTS nutrition(retailer_sku TEXT PRIMARY KEY,basis TEXT,energy_kj REAL,calories_kcal REAL,fat_g REAL,saturates_g REAL,carbohydrate_g REAL,sugars_g REAL,fiber_g REAL,protein_g REAL,salt_g REAL,status TEXT,source TEXT,evidence_type TEXT);
    CREATE TABLE IF NOT EXISTS field_evidence(retailer_sku TEXT,field TEXT,source TEXT,evidence_type TEXT,value_json TEXT,source_url TEXT,observed_at TEXT,PRIMARY KEY(retailer_sku,field,source,source_url));
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
    """)
    return db

def coverage(rows, field):
    count = sum(1 for r in rows if r.get(field) not in (None,"",[]))
    return {"count":count,"pct":round(100*count/len(rows),2) if rows else 0.0}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",default="carrefour-first-party"); ap.add_argument("--seed-jsonl",action="append",default=[]); ap.add_argument("--seed-url",action="append",default=[]); ap.add_argument("--root",action="append",default=[]); ap.add_argument("--max-pages",type=int,default=3); ap.add_argument("--max-products",type=int,default=0); ap.add_argument("--workers",type=int,default=6); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    discovered,diag=discover_from_roots(args.root or DEFAULT_ROOTS,args.max_pages); urls=set(discovered)
    for path in args.seed_jsonl: urls.update(read_seed_jsonl(path))
    urls.update(u.split("?")[0].rstrip("/") for u in args.seed_url if "carrefour.es/supermercado/" in u)
    urls=sorted(urls); urls=urls[:args.max_products] if args.max_products>0 else urls
    rows=[]; evidence=[]
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as pool:
        futures=[pool.submit(parse_product,u) for u in urls]
        for i,fut in enumerate(as_completed(futures),1):
            row,ev=fut.result(); rows.append(row); evidence.extend(ev)
            if i%25==0 or i==len(futures): print(f"processed={i}/{len(futures)} fetched={sum(not r.get('fetch_error') for r in rows)}")
    rows.sort(key=lambda r:r["retailer_sku"])
    with (out/"products.jsonl").open("w",encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")
    with (out/"field_evidence.jsonl").open("w",encoding="utf-8") as f:
        for e in evidence: f.write(json.dumps(e,ensure_ascii=False)+"\n")
    db=init_db(out/"carrefour_first_party.sqlite")
    for r in rows:
        db.execute("INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(r.get("retailer_sku"),r.get("gtin"),r.get("name"),r.get("brand"),r.get("canonical_url"),r.get("image_url"),json.dumps(r.get("category_path") or [],ensure_ascii=False),r.get("price_eur"),r.get("price_currency"),r.get("unit_price_text"),r.get("availability"),r.get("legal_name"),r.get("ingredients"),r.get("allergens"),r.get("net_content"),r.get("storage_conditions"),r.get("preparation_instructions"),r.get("operator_address"),r.get("manufacturer_packer_importer"),r.get("observed_at"),r.get("page_sha256"),r.get("http_status"),r.get("fetch_error"),SOURCE))
        db.execute("INSERT OR REPLACE INTO nutrition VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(r.get("retailer_sku"),r.get("nutrition_basis"),r.get("energy_kj"),r.get("calories_kcal"),r.get("fat_g"),r.get("saturates_g"),r.get("carbohydrate_g"),r.get("sugars_g"),r.get("fiber_g"),r.get("protein_g"),r.get("salt_g"),r.get("nutrition_status"),SOURCE,"DECLARED"))
    for e in evidence: db.execute("INSERT OR REPLACE INTO field_evidence VALUES(?,?,?,?,?,?,?)",(e["retailer_sku"],e["field"],e["source"],e["evidence_type"],json.dumps(e["value"],ensure_ascii=False),e["source_url"],e["observed_at"]))
    metadata={"retailer":"CARREFOUR","source_policy":"FIRST_PARTY_CARREFOUR_ONLY","source":BASE,"extractor_version":VERSION,"built_at":now_iso(),"classification_performed":"false"}
    for k,v in metadata.items(): db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)",(k,str(v)))
    db.commit(); db.close()
    fields=["gtin","name","brand","image_url","category_path","price_eur","unit_price_text","availability","legal_name","ingredients","allergens","net_content","storage_conditions","preparation_instructions","operator_address","manufacturer_packer_importer"]
    summary={**metadata,"counts":{"candidate_urls":len(urls),"direct_discovered_urls":len(discovered),"fetched":sum(not r.get("fetch_error") for r in rows),"fetch_errors":sum(bool(r.get("fetch_error")) for r in rows),"nutrition_complete":sum(r.get("nutrition_status")=="DECLARED_COMPLETE" for r in rows),"nutrition_partial":sum(r.get("nutrition_status")=="DECLARED_PARTIAL" for r in rows),"nutrition_not_found":sum(r.get("nutrition_status")=="NOT_FOUND" for r in rows),"evidence_rows":len(evidence)},"coverage":{x:coverage(rows,x) for x in fields},"nutrition_field_coverage":{x:coverage(rows,x) for x in ["energy_kj","calories_kcal","fat_g","saturates_g","carbohydrate_g","sugars_g","fiber_g","protein_g","salt_g"]},"discovery_diagnostics":diag,"sample":rows[:10],"provenance_note":"All stored product fields are fetched from carrefour.es. Third-party/RadarSuper data may only be used as candidate URL input and is never copied into this dataset."}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(summary["counts"],ensure_ascii=False,indent=2))
    return 0 if summary["counts"]["fetched"] else 2

if __name__=="__main__": raise SystemExit(main())
