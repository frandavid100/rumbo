from __future__ import annotations

import argparse, concurrent.futures as cf, html, json, re, sqlite3, time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from urllib.request import Request, urlopen

from nutrition_validation import validate_nutrition

BASE = "https://www.compraonline.alcampo.es"
ROOT = BASE + "/categories"
VERSION = "alcampo-direct-v3.0"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36"
FOOD_TERMS = ("frescos","leche","huevos","lacte","yogur","bebidas vegetales","alimentaci","desayuno","merienda","congelados","comida preparada","ecol","sin gluten","sin lactosa","nutrici","funcional","vegan")
DENY = re.compile(r"\b(vino|vinos|cerveza|cervezas|licor|licores|whisky|whiskey|ron|ginebra|vodka|brandy|cognac|champagne|cava|sidra|vermut|vermouth|sangr[ií]a|alcohol|espirituosas)\b", re.I)

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self._href=None; self._text=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=="a": self._href=dict(attrs).get("href"); self._text=[]
    def handle_data(self,data):
        if self._href is not None: self._text.append(data)
    def handle_endtag(self,tag):
        if tag.lower()=="a" and self._href is not None:
            self.links.append((" ".join(self._text).strip(), self._href)); self._href=None; self._text=[]

def fetch(url, timeout=35):
    req=Request(url,headers={"User-Agent":UA,"Accept-Language":"es-ES,es;q=0.9","Accept":"text/html,application/xhtml+xml"})
    with urlopen(req,timeout=timeout) as r: return r.read().decode("utf-8",errors="replace")

def links(raw, base):
    p=Links(); p.feed(raw); out=[]
    for text,href in p.links:
        u=urljoin(base,html.unescape(href)).split("#")[0]
        if urlparse(u).netloc==urlparse(BASE).netloc: out.append((re.sub(r"\s+"," ",html.unescape(text)).strip(),u))
    return out

def clean(s): return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",s or ""))).strip(" :-\n\t") or None

def discover(max_categories=900):
    raw=fetch(ROOT); root_links=links(raw,ROOT)
    seeds=[]
    for text,u in root_links:
        if "/categories/" not in u: continue
        hay=unquote((text+" "+u).lower())
        if any(t in hay for t in FOOD_TERMS) and not DENY.search(hay): seeds.append((u.split("?")[0],text or u))
    # stable first-party fallback observed 2026-08-19
    if not seeds: seeds=[(BASE+"/categories/alimentaci%C3%B3n/OCC10","Alimentación"),(BASE+"/categories/frescos/OC2112","Frescos")]
    q=list(dict.fromkeys(seeds)); seen={}; products={}; errors=[]
    while q and len(seen)<max_categories:
        url,label=q.pop(0); url=url.split("?")[0]
        if url in seen: continue
        hay=unquote((label+" "+url).lower())
        if DENY.search(hay): continue
        seen[url]=label
        try: raw=fetch(url)
        except Exception as e: errors.append([url,f"{type(e).__name__}:{e}"]); continue
        for text,u in links(raw,url):
            u0=u.split("?")[0].rstrip("/"); ctx=unquote((text+" "+u0).lower())
            if DENY.search(ctx): continue
            if re.search(r"/products/.+/\d+$",u0): products.setdefault(u0,label)
            elif "/categories/" in u0 and u0 not in seen: q.append((u0,text or label))
        if len(seen)%25==0: print(f"discovery categories={len(seen)} products={len(products)} queue={len(q)}",flush=True)
        time.sleep(.03)
    refs=sorted(products.items())
    return refs,{"root":ROOT,"seed_categories":len(seeds),"categories_visited":len(seen),"products_discovered":len(refs),"category_fetch_errors":len(errors),"examples":refs[:5],"version":VERSION}

@dataclass
class Obs:
    url:str; sku:str; name:str|None; brand:str|None; gtin:str|None; legal_name:str|None; ingredients:str|None; category:str|None
    calories:float|None; protein_g:float|None; carbohydrate_g:float|None; fat_g:float|None; fiber_g:float|None; salt_g:float|None; nutrition_status:str; error:str|None=None

def val(pattern,text):
    m=re.search(pattern,text,re.I|re.S)
    return clean(m.group(1)) if m else None

def num(pattern,text):
    m=re.search(pattern,text,re.I)
    return float(m.group(1).replace(",",".")) if m else None

def parse(ref):
    url,category=ref; sku=url.rstrip("/").split("/")[-1]
    try:
        raw=fetch(url); text=clean(raw) or ""
        name=val(r"<h1[^>]*>(.*?)</h1>",raw) or val(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',raw)
        brand=val(r"(?:##\s*)?Marca\s+([^#\n]+)",text) or val(r'"brand"\s*:\s*"([^"]+)"',raw)
        gtin=val(r'"(?:gtin13|gtin|ean)"\s*:\s*"(\d{8,14})"',raw)
        legal=val(r"Denominaci[oó]n legal del alimento\s*[|:]?\s*([^|#\n]+)",text)
        ing=val(r"Ingredientes\s*(?:Ingredientes:)?\s*(.+?)(?=Caracter[ií]sticas|Datos nutricionales|Al[eé]rgenos|Almacenamiento|Productos relacionados|$)",text)
        nutrition=val(r"Datos nutricionales\s*(.+?)(?=Productos similares|Opiniones de los clientes|$)",text) or ""
        kcal=num(r"Valor energ[eé]tico \(Kcal\)\s*[|:]?\s*([0-9]+(?:[.,][0-9]+)?)",nutrition)
        fat=num(r"Grasas(?! saturadas)\s*[|:]?\s*([0-9]+(?:[.,][0-9]+)?)\s*g",nutrition)
        carb=num(r"Hidratos de carbono\s*[|:]?\s*([0-9]+(?:[.,][0-9]+)?)\s*g",nutrition)
        protein=num(r"Prote[ií]nas\s*[|:]?\s*([0-9]+(?:[.,][0-9]+)?)\s*g",nutrition)
        fiber=num(r"Fibra(?: alimentaria)?\s*[|:]?\s*([0-9]+(?:[.,][0-9]+)?)\s*g",nutrition)
        salt=num(r"Sal\s*[|:]?\s*([0-9]+(?:[.,][0-9]+)?)\s*g",nutrition)
        if all(x is not None for x in (kcal,protein,carb,fat)):
            vr=validate_nutrition(kcal,protein,carb,fat,fiber,salt); status="DECLARED_VALID" if vr.valid else "DECLARED_INVALID:"+",".join(vr.reasons)
        else: status="DECLARED_INCOMPLETE"
        return Obs(url,sku,name,brand,gtin,legal,ing,category,kcal,protein,carb,fat,fiber,salt,status)
    except Exception as e: return Obs(url,sku,None,None,None,None,None,category,None,None,None,None,None,None,"FETCH_ERROR",f"{type(e).__name__}:{e}")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",default="alcampo-direct-v3-output"); ap.add_argument("--workers",type=int,default=20); ap.add_argument("--max-products",type=int,default=0); ap.add_argument("--min-discovered",type=int,default=1); a=ap.parse_args()
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True); refs,disc=discover(); refs=refs[:a.max_products] if a.max_products else refs; print(f"discovered_unique={len(refs)}",flush=True)
    obs=[]
    with cf.ThreadPoolExecutor(max_workers=max(1,a.workers)) as ex:
        for i,o in enumerate(ex.map(parse,refs),1):
            obs.append(o)
            if i%100==0 or i==len(refs): print(f"progress={i}/{len(refs)} valid={sum(x.nutrition_status=='DECLARED_VALID' for x in obs)} errors={sum(x.error is not None for x in obs)}",flush=True)
    with (out/"observations.jsonl").open("w",encoding="utf-8") as f:
        for o in obs: f.write(json.dumps(asdict(o),ensure_ascii=False)+"\n")
    db=sqlite3.connect(out/"alcampo_food_catalog.sqlite"); db.executescript("CREATE TABLE IF NOT EXISTS products(retailer TEXT,sku TEXT,url TEXT,name TEXT,brand TEXT,gtin TEXT,legal_name TEXT,ingredients TEXT,category TEXT,PRIMARY KEY(retailer,sku)); CREATE TABLE IF NOT EXISTS nutrition(retailer TEXT,sku TEXT,calories REAL,protein_g REAL,carbohydrate_g REAL,fat_g REAL,fiber_g REAL,salt_g REAL,evidence_level TEXT,status TEXT,PRIMARY KEY(retailer,sku)); CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);")
    for o in obs:
        db.execute("INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?,?,?,?)",("ALCAMPO",o.sku,o.url,o.name,o.brand,o.gtin,o.legal_name,o.ingredients,o.category)); db.execute("INSERT OR REPLACE INTO nutrition VALUES(?,?,?,?,?,?,?,?,?,?)",("ALCAMPO",o.sku,o.calories,o.protein_g,o.carbohydrate_g,o.fat_g,o.fiber_g,o.salt_g,"DECLARED" if o.nutrition_status.startswith("DECLARED_") else None,o.nutrition_status))
    for k,v in {"source":BASE,"importer_version":VERSION,"built_at":datetime.now(timezone.utc).isoformat(),"third_party_product_data":"false"}.items(): db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)",(k,v))
    db.commit();db.close()
    counts={"discovered":len(refs),"fetched":sum(o.error is None for o in obs),"fetch_errors":sum(o.error is not None for o in obs),"with_name":sum(bool(o.name) for o in obs),"with_gtin":sum(bool(o.gtin) for o in obs),"with_ingredients":sum(bool(o.ingredients) for o in obs),"with_legal_name":sum(bool(o.legal_name) for o in obs),"declared_valid_nutrition":sum(o.nutrition_status=="DECLARED_VALID" for o in obs),"declared_incomplete_nutrition":sum(o.nutrition_status=="DECLARED_INCOMPLETE" for o in obs),"declared_invalid_nutrition":sum(o.nutrition_status.startswith("DECLARED_INVALID") for o in obs)}
    summary={"retailer":"ALCAMPO","source":BASE,"importer_version":VERSION,"built_at":datetime.now(timezone.utc).isoformat(),"discovery":disc,"counts":counts,"third_party_product_data":False}; (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return 0 if len(refs)>=a.min_discovered else 2

if __name__=="__main__": raise SystemExit(main())
