#!/usr/bin/env python3
import argparse, hashlib, json, sqlite3, time
from pathlib import Path

SCHEMA_VERSION=3
CLASSIFIER_VERSION="3"
SCHEMA="""
CREATE TABLE catalog_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE products(id INTEGER PRIMARY KEY,gtin TEXT UNIQUE,canonical_name TEXT NOT NULL,brand TEXT,legal_name TEXT,ingredients TEXT);
CREATE TABLE retailer_listings(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL,retailer TEXT NOT NULL,retailer_sku TEXT NOT NULL,context TEXT NOT NULL,display_name TEXT NOT NULL,url TEXT,availability TEXT NOT NULL,observed_at TEXT NOT NULL,UNIQUE(retailer,retailer_sku,context));
CREATE TABLE nutrition(product_id INTEGER PRIMARY KEY,basis TEXT NOT NULL,calories REAL,fat_g REAL,carbohydrate_g REAL,protein_g REAL,fiber_g REAL,saturated_fat_g REAL,sugar_g REAL,salt_g REAL,source TEXT NOT NULL,evidence_level TEXT NOT NULL,confidence REAL NOT NULL);
CREATE TABLE classifications(product_id INTEGER PRIMARY KEY,nutritional_role TEXT NOT NULL,culinary_type TEXT NOT NULL,confidence REAL NOT NULL,classifier_version TEXT NOT NULL);
CREATE TABLE eligibility(product_id INTEGER PRIMARY KEY,discoverable INTEGER NOT NULL,identified INTEGER NOT NULL,nutritionally_usable INTEGER NOT NULL,classified INTEGER NOT NULL,menu_eligible INTEGER NOT NULL,reason TEXT);
CREATE TABLE evidence(id INTEGER PRIMARY KEY,source TEXT NOT NULL,source_record_id TEXT NOT NULL,observed_at TEXT NOT NULL,raw_path TEXT NOT NULL,raw_sha256 TEXT NOT NULL,adapter_version TEXT NOT NULL);
CREATE INDEX idx_listing_retailer ON retailer_listings(retailer);
CREATE INDEX idx_product_gtin ON products(gtin);
"""
ACCEPTED={"DECLARED","MATCHED","CORROBORATED","GENERIC"}

def stable_id(ns,key): return int.from_bytes(hashlib.sha256(f"{ns}:{key}".encode()).digest()[:7],"big")
def nval(n,k):
    v=n.get(k); return float(v) if isinstance(v,(int,float)) else None
def complete(n): return all(nval(n,k) is not None for k in ("energy-kcal_100g","fat_100g","carbohydrates_100g","proteins_100g"))
def classify(name):
    t=name.lower()
    if "arroz" in t:return "CARBOHYDRATE","DRY_RICE",.99
    if "macarr" in t or "pasta" in t:return "CARBOHYDRATE","DRY_PASTA",.99
    if t.startswith("pan") or "pan de " in t:return "CARBOHYDRATE","BREAD",.98
    if "yogur" in t:return "PROTEIN","CREAMY_BASE",.97
    if "leche" in t:return "PROTEIN","MILK_BASE",.95
    if "aceite" in t:return "FAT","CULINARY_OIL",.99
    if "tomate frito" in t:return "FAT","SAUCE",.98
    if "huevo" in t:return "PROTEIN","MAIN_EGG",.99
    if "salmón" in t or "salmon" in t:return "PROTEIN","MAIN_FISH",.99
    if "pollo" in t or "pavo" in t:return "PROTEIN","MAIN_MEAT",.99
    if "tomate" in t:return "VEGETABLE","VEGETABLE",.99
    if "nuez" in t:return "FAT","FAT_COMPLEMENT",.98
    return "OTHER","UNKNOWN",.4

def evidence(base,source,record,payload,ts):
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True).encode(); sha=hashlib.sha256(raw).hexdigest()
    p=base/source/ts.replace(":","-")/(record+".json"); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(raw)
    return str(p),sha

def choose(gtin,sku,offs,secondary,generic):
    if gtin and gtin in offs:
        x=offs[gtin]; n=x.get("product",{}).get("nutriments",{})
        if complete(n): return n,"Open Food Facts","MATCHED",.90,[("openfoodfacts",gtin,x,"api-v2")],x.get("product",{})
    if gtin and gtin in secondary:
        x=secondary[gtin]; n=x.get("nutriments",{}); sources=x.get("sources",[])
        if complete(n):
            level="CORROBORATED" if len(sources)>=2 else "MATCHED"; conf=.85 if level=="CORROBORATED" else .75
            return n," + ".join(s.get("name","fuente secundaria") for s in sources),level,conf,[("secondary",gtin,x,"fixture-v2")],{"ingredients_text_es":x.get("ingredients")}
    if sku in generic:
        x=generic[sku]; n=x.get("nutriments",{})
        if complete(n): return n,x.get("source","composición genérica"),"GENERIC",.70,[("generic",sku,x,"fixture-v1")],{"generic_name_es":x.get("generic_name")}
    return None

def build(a):
    merc=json.loads(Path(a.mercadona_fixture).read_text()); offs={str(x["code"]):x for x in json.loads(Path(a.off_fixture).read_text())}
    secondary={str(x["code"]):x for x in json.loads(Path(a.secondary_fixture).read_text())} if a.secondary_fixture else {}
    generic={str(x["sku"]):x for x in json.loads(Path(a.generic_fixture).read_text())} if a.generic_fixture else {}
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); out.unlink(missing_ok=True)
    ts=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()); evdir=Path(a.evidence_dir); con=sqlite3.connect(out); con.executescript(SCHEMA)
    for k,v in {"schema_version":str(SCHEMA_VERSION),"classifier_version":CLASSIFIER_VERSION,"context":a.context,"built_at":ts}.items(): con.execute("INSERT INTO catalog_metadata VALUES(?,?)",(k,v))
    for item in merc:
        sku=str(item["sku"]); gtin=item.get("gtin"); pid=stable_id("gtin",gtin) if gtin else stable_id("mercadona-sku",sku)
        p,sha=evidence(evdir,"mercadona",sku,item,ts); con.execute("INSERT INTO evidence(source,source_record_id,observed_at,raw_path,raw_sha256,adapter_version) VALUES(?,?,?,?,?,?)",("mercadona",sku,ts,p,sha,"fixture-v2"))
        chosen=choose(gtin,sku,offs,secondary,generic); product=(chosen[5] if chosen else {})
        con.execute("INSERT INTO products VALUES(?,?,?,?,?,?)",(pid,gtin,item["name"],item.get("brand") or product.get("brands"),product.get("generic_name_es"),product.get("ingredients_text_es")))
        con.execute("INSERT INTO retailer_listings(product_id,retailer,retailer_sku,context,display_name,url,availability,observed_at) VALUES(?,?,?,?,?,?,?,?)",(pid,"Mercadona",sku,a.context,item["name"],item.get("url"),item.get("availability","ACTIVE"),ts))
        usable=False
        if chosen:
            n,source,level,conf,payloads,_=chosen
            for es,record,payload,version in payloads:
                p2,sha2=evidence(evdir,es,record,payload,ts); con.execute("INSERT INTO evidence(source,source_record_id,observed_at,raw_path,raw_sha256,adapter_version) VALUES(?,?,?,?,?,?)",(es,record,ts,p2,sha2,version))
            usable=level in ACCEPTED and complete(n)
            con.execute("INSERT INTO nutrition VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,"100_g",nval(n,"energy-kcal_100g"),nval(n,"fat_100g"),nval(n,"carbohydrates_100g"),nval(n,"proteins_100g"),nval(n,"fiber_100g"),nval(n,"saturated-fat_100g"),nval(n,"sugars_100g"),nval(n,"salt_100g"),source,level,conf))
        role,ctype,cconf=classify(item["name"]); classified=ctype!="UNKNOWN"
        con.execute("INSERT INTO classifications VALUES(?,?,?,?,?)",(pid,role,ctype,cconf,CLASSIFIER_VERSION)); reason=None if usable and classified else ("Falta nutrición comparable" if not usable else "Clasificación insuficiente")
        con.execute("INSERT INTO eligibility VALUES(?,?,?,?,?,?,?)",(pid,1,1,int(usable),int(classified),int(usable and classified),reason))
    con.commit(); report={"products":con.execute("select count(*) from products").fetchone()[0],"menu_eligible":con.execute("select count(*) from eligibility where menu_eligible=1").fetchone()[0],"classified":con.execute("select count(*) from eligibility where classified=1").fetchone()[0],"nutrition_by_evidence":dict(con.execute("select evidence_level,count(*) from nutrition group by evidence_level").fetchall()),"unusable":[r[0] for r in con.execute("select p.canonical_name from products p join eligibility e on e.product_id=p.id where e.menu_eligible=0 order by p.canonical_name")]}; Path(a.report).parent.mkdir(parents=True,exist_ok=True); Path(a.report).write_text(json.dumps(report,indent=2,ensure_ascii=False)); con.close()

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--mercadona-fixture",required=True); p.add_argument("--off-fixture",required=True); p.add_argument("--secondary-fixture"); p.add_argument("--generic-fixture"); p.add_argument("--output",required=True); p.add_argument("--report",required=True); p.add_argument("--evidence-dir",required=True); p.add_argument("--context",default="Valencia"); build(p.parse_args())
