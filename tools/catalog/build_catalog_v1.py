#!/usr/bin/env python3
import argparse, hashlib, json, sqlite3, time
from pathlib import Path

SCHEMA_VERSION = 2
CLASSIFIER_VERSION = "2"
SCHEMA = """
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

ACCEPTED_NUTRITION_LEVELS = {"DECLARED", "MATCHED", "CORROBORATED", "GENERIC"}


def stable_id(ns, key):
    return int.from_bytes(hashlib.sha256(f"{ns}:{key}".encode()).digest()[:7], "big")


def classify(name):
    t = name.lower()
    if "arroz" in t:
        return "CARBOHYDRATE", "DRY_RICE", .99
    if "leche" in t:
        return "PROTEIN", "MILK_BASE", .95
    if "aceite" in t:
        return "FAT", "CULINARY_OIL", .99
    return "OTHER", "UNKNOWN", .4


def save_evidence(base, source, record, payload, ts):
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    sha = hashlib.sha256(raw).hexdigest()
    p = base / source / ts.replace(":", "-") / (record + ".json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)
    return str(p), sha


def nutriment_value(nutriments, key):
    value = nutriments.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def complete_core_nutrition(nutriments):
    return all(
        nutriment_value(nutriments, key) is not None
        for key in ["energy-kcal_100g", "fat_100g", "carbohydrates_100g", "proteins_100g"]
    )


def choose_nutrition(gtin, off_by_gtin, secondary_by_gtin):
    off = off_by_gtin.get(gtin)
    if off:
        nutriments = off.get("product", {}).get("nutriments", {})
        if complete_core_nutrition(nutriments):
            return {
                "nutriments": nutriments,
                "source": "Open Food Facts",
                "evidence_level": "MATCHED",
                "confidence": .90,
                "evidence_payloads": [("openfoodfacts", gtin, off, "api-v2")],
                "product": off.get("product", {}),
            }

    secondary = secondary_by_gtin.get(gtin)
    if secondary and complete_core_nutrition(secondary.get("nutriments", {})):
        sources = secondary.get("sources", [])
        level = "CORROBORATED" if len(sources) >= 2 else "MATCHED"
        confidence = .85 if level == "CORROBORATED" else .75
        source_names = " + ".join(source.get("name", "fuente secundaria") for source in sources)
        return {
            "nutriments": secondary["nutriments"],
            "source": source_names,
            "evidence_level": level,
            "confidence": confidence,
            "evidence_payloads": [("secondary", gtin, secondary, "fixture-v1")],
            "product": {"ingredients_text_es": secondary.get("ingredients")},
        }
    return None


def build(args):
    merc = json.loads(Path(args.mercadona_fixture).read_text())
    offs = {str(x["code"]): x for x in json.loads(Path(args.off_fixture).read_text())}
    secondary = {
        str(x["code"]): x
        for x in json.loads(Path(args.secondary_fixture).read_text())
    } if args.secondary_fixture else {}

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    evidence_dir = Path(args.evidence_dir)
    con = sqlite3.connect(out)
    con.executescript(SCHEMA)
    for k, v in {
        "schema_version": str(SCHEMA_VERSION),
        "classifier_version": CLASSIFIER_VERSION,
        "context": args.context,
        "built_at": ts,
    }.items():
        con.execute("INSERT INTO catalog_metadata VALUES(?,?)", (k, v))

    for listing in merc:
        sku = str(listing["sku"])
        gtin = listing.get("gtin")
        pid = stable_id("gtin", gtin) if gtin else stable_id("mercadona-sku", sku)
        p, sha = save_evidence(evidence_dir, "mercadona", sku, listing, ts)
        con.execute(
            "INSERT INTO evidence(source,source_record_id,observed_at,raw_path,raw_sha256,adapter_version) VALUES(?,?,?,?,?,?)",
            ("mercadona", sku, ts, p, sha, "fixture-v1"),
        )

        chosen = choose_nutrition(gtin, offs, secondary) if gtin else None
        product_data = (chosen or {}).get("product", {})
        con.execute(
            "INSERT INTO products VALUES(?,?,?,?,?,?)",
            (
                pid,
                gtin,
                listing["name"],
                listing.get("brand") or product_data.get("brands"),
                product_data.get("generic_name_es"),
                product_data.get("ingredients_text_es"),
            ),
        )
        con.execute(
            "INSERT INTO retailer_listings(product_id,retailer,retailer_sku,context,display_name,url,availability,observed_at) VALUES(?,?,?,?,?,?,?,?)",
            (pid, "Mercadona", sku, args.context, listing["name"], listing.get("url"), listing.get("availability", "ACTIVE"), ts),
        )

        usable = False
        if chosen:
            for source, record, payload, adapter_version in chosen["evidence_payloads"]:
                p2, sha2 = save_evidence(evidence_dir, source, record, payload, ts)
                con.execute(
                    "INSERT INTO evidence(source,source_record_id,observed_at,raw_path,raw_sha256,adapter_version) VALUES(?,?,?,?,?,?)",
                    (source, record, ts, p2, sha2, adapter_version),
                )
            n = chosen["nutriments"]
            usable = chosen["evidence_level"] in ACCEPTED_NUTRITION_LEVELS and complete_core_nutrition(n)
            con.execute(
                "INSERT INTO nutrition VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    pid,
                    "100_g",
                    nutriment_value(n, "energy-kcal_100g"),
                    nutriment_value(n, "fat_100g"),
                    nutriment_value(n, "carbohydrates_100g"),
                    nutriment_value(n, "proteins_100g"),
                    nutriment_value(n, "fiber_100g"),
                    nutriment_value(n, "saturated-fat_100g"),
                    nutriment_value(n, "sugars_100g"),
                    nutriment_value(n, "salt_100g"),
                    chosen["source"],
                    chosen["evidence_level"],
                    chosen["confidence"],
                ),
            )

        role, ctype, conf = classify(listing["name"])
        classified = ctype != "UNKNOWN"
        con.execute("INSERT INTO classifications VALUES(?,?,?,?,?)", (pid, role, ctype, conf, CLASSIFIER_VERSION))
        reason = None if usable and classified else ("Falta nutrición comparable" if not usable else "Clasificación insuficiente")
        con.execute(
            "INSERT INTO eligibility VALUES(?,?,?,?,?,?,?)",
            (pid, 1, 1, int(usable), int(classified), int(usable and classified), reason),
        )

    con.commit()
    report = {
        "products": con.execute("select count(*) from products").fetchone()[0],
        "menu_eligible": con.execute("select count(*) from eligibility where menu_eligible=1").fetchone()[0],
        "nutrition_by_evidence": dict(con.execute("select evidence_level,count(*) from nutrition group by evidence_level").fetchall()),
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    con.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mercadona-fixture", required=True)
    p.add_argument("--off-fixture", required=True)
    p.add_argument("--secondary-fixture")
    p.add_argument("--output", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--evidence-dir", required=True)
    p.add_argument("--context", default="Valencia")
    build(p.parse_args())
