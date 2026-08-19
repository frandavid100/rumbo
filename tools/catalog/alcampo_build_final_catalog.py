from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 5
BUILDER_VERSION = "alcampo-first-party-final-v1.2"

SCHEMA = """
CREATE TABLE catalog_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE products(id INTEGER PRIMARY KEY,gtin TEXT,canonical_name TEXT NOT NULL,brand TEXT,legal_name TEXT,ingredients TEXT);
CREATE TABLE retailer_listings(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL,retailer TEXT NOT NULL,retailer_sku TEXT NOT NULL,context TEXT NOT NULL,display_name TEXT NOT NULL,url TEXT,availability TEXT NOT NULL,observed_at TEXT NOT NULL,UNIQUE(retailer,retailer_sku,context));
CREATE TABLE nutrition(product_id INTEGER PRIMARY KEY,basis TEXT NOT NULL,calories REAL,fat_g REAL,carbohydrate_g REAL,protein_g REAL,fiber_g REAL,saturated_fat_g REAL,sugar_g REAL,salt_g REAL,source TEXT NOT NULL,evidence_level TEXT NOT NULL,confidence REAL NOT NULL);
CREATE TABLE classifications(product_id INTEGER PRIMARY KEY,nutritional_role TEXT NOT NULL,culinary_type TEXT NOT NULL,confidence REAL NOT NULL,classifier_version TEXT NOT NULL);
CREATE TABLE eligibility(product_id INTEGER PRIMARY KEY,discoverable INTEGER NOT NULL,identified INTEGER NOT NULL,nutritionally_usable INTEGER NOT NULL,classified INTEGER NOT NULL,menu_eligible INTEGER NOT NULL,reason TEXT);
CREATE TABLE evidence(id INTEGER PRIMARY KEY,product_id INTEGER,source TEXT NOT NULL,source_record_id TEXT NOT NULL,observed_at TEXT NOT NULL,raw_path TEXT NOT NULL,raw_sha256 TEXT NOT NULL,adapter_version TEXT NOT NULL,evidence_kind TEXT NOT NULL);
CREATE TABLE product_images(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL,kind TEXT NOT NULL,url TEXT NOT NULL,source TEXT NOT NULL,source_record_id TEXT,license TEXT,attribution TEXT,redistributable INTEGER NOT NULL DEFAULT 0,width INTEGER,height INTEGER,is_primary INTEGER NOT NULL DEFAULT 0,observed_at TEXT NOT NULL,UNIQUE(product_id,kind,url));
CREATE INDEX idx_listing_retailer ON retailer_listings(retailer);
CREATE INDEX idx_product_gtin ON products(gtin);
CREATE INDEX idx_product_images_product ON product_images(product_id);
CREATE INDEX idx_evidence_product ON evidence(product_id);
"""


def stable_id(sku: str) -> int:
    return int.from_bytes(hashlib.sha256(f"alcampo-sku:{sku}".encode()).digest()[:7], "big")


def load_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def sha(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def nutrition_basis(detail: dict, product: dict) -> tuple[str | None, float, str | None]:
    del product
    basis = str(detail.get("nutrition_basis") or "").lower()
    if basis in {"100_g", "100_ml"}:
        return basis, 0.99, "detail.explicit_basis"
    # Pack size and unit-price units do not establish the basis of the nutrition
    # declaration. If Alcampo's own nutrition table does not expose a comparable basis,
    # keep the product out of NUTRITIONALLY_USABLE rather than infer one.
    return None, 0.0, None


def complete_detail_nutrition(d: dict) -> bool:
    return d.get("nutrition_status") == "DECLARED_VALID" and all(
        isinstance(d.get(k), (int, float)) for k in ("calories", "fat_g", "carbohydrate_g", "protein_g")
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--products", type=Path, required=True)
    p.add_argument("--details", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--context", default="Alcampo online España")
    a = p.parse_args()

    products = load_jsonl(a.products)
    details = {str(r.get("sku")): r for r in load_jsonl(a.details) if r.get("sku") is not None}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.unlink(missing_ok=True)
    con = sqlite3.connect(a.output)
    con.executescript(SCHEMA)
    now = datetime.now(timezone.utc).isoformat()
    metadata = {
        "schema_version": str(SCHEMA_VERSION),
        "builder_version": BUILDER_VERSION,
        "retailer": "Alcampo",
        "source": "https://www.compraonline.alcampo.es",
        "context": a.context,
        "built_at": now,
        "product_identity_source_policy": "FIRST_PARTY_ALCAMPO_ONLY",
        "nutrition_source_policy": "FIRST_PARTY_ALCAMPO_DECLARED_ONLY",
        "nutrition_basis_policy": "EXPLICIT_ALCAMPO_DETAIL_ONLY",
        "listing_evidence_stream": str(a.products),
        "detail_evidence_stream": str(a.details),
    }
    for k, v in metadata.items():
        con.execute("INSERT INTO catalog_metadata VALUES(?,?)", (k, v))

    counts = {
        "products_input": len(products), "identified": 0, "detail_rows": 0, "declared_valid_raw": 0,
        "nutrition_basis_resolved": 0, "nutritionally_usable": 0, "detail_fetch_errors": 0,
        "with_ingredients": 0, "with_legal_name": 0, "with_gtin": 0,
    }
    for product in products:
        sku = str(product.get("sku") or "").strip()
        name = str(product.get("name") or "").strip()
        if not sku or not name:
            continue
        pid = stable_id(sku)
        d = details.get(sku) or {}
        if d: counts["detail_rows"] += 1
        if d.get("error"): counts["detail_fetch_errors"] += 1
        if complete_detail_nutrition(d): counts["declared_valid_raw"] += 1
        canonical_name = str(d.get("name") or name).strip()
        legal = d.get("legal_name") or None
        ingredients = d.get("ingredients") or None
        gtin = str(d.get("gtin") or "").strip() or None
        brand = product.get("brand") or None
        if legal: counts["with_legal_name"] += 1
        if ingredients: counts["with_ingredients"] += 1
        if gtin: counts["with_gtin"] += 1
        counts["identified"] += 1

        con.execute("INSERT INTO products VALUES(?,?,?,?,?,?)", (pid, gtin, canonical_name, brand, legal, ingredients))
        url = d.get("canonical_url") or d.get("requested_url") or f"https://www.compraonline.alcampo.es/products/x/{sku}"
        availability = "ACTIVE" if bool(product.get("available", True)) else "UNAVAILABLE"
        con.execute(
            "INSERT INTO retailer_listings(product_id,retailer,retailer_sku,context,display_name,url,availability,observed_at) VALUES(?,?,?,?,?,?,?,?)",
            (pid, "Alcampo", sku, a.context, name, url, availability, now),
        )
        image = product.get("image_url")
        if image:
            con.execute(
                "INSERT OR IGNORE INTO product_images(product_id,kind,url,source,source_record_id,license,attribution,redistributable,width,height,is_primary,observed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (pid, "front", image, "Alcampo", sku, None, None, 0, None, None, 1, now),
            )

        con.execute(
            "INSERT INTO evidence(product_id,source,source_record_id,observed_at,raw_path,raw_sha256,adapter_version,evidence_kind) VALUES(?,?,?,?,?,?,?,?)",
            (pid, "Alcampo", sku, now, f"{a.products.name}#sku={sku}", sha(product), "alcampo-webproductpagews-v6", "LISTING"),
        )
        if d:
            con.execute(
                "INSERT INTO evidence(product_id,source,source_record_id,observed_at,raw_path,raw_sha256,adapter_version,evidence_kind) VALUES(?,?,?,?,?,?,?,?)",
                (pid, "Alcampo", sku, now, f"{a.details.name}#sku={sku}", sha(d), "alcampo-detail-http-v2.1", "PRODUCT_DETAIL"),
            )

        usable = False
        reason = None
        if complete_detail_nutrition(d):
            basis, confidence, basis_rule = nutrition_basis(d, product)
            if basis:
                counts["nutrition_basis_resolved"] += 1
                usable = True
                con.execute(
                    "INSERT INTO nutrition VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (pid, basis, float(d["calories"]), float(d["fat_g"]), float(d["carbohydrate_g"]), float(d["protein_g"]),
                     float(d["fiber_g"]) if isinstance(d.get("fiber_g"), (int, float)) else None, None, None,
                     float(d["salt_g"]) if isinstance(d.get("salt_g"), (int, float)) else None,
                     "Alcampo product detail", "DECLARED", confidence),
                )
                con.execute("INSERT OR REPLACE INTO catalog_metadata(key,value) VALUES(?,?)", (f"nutrition_basis_rule:{sku}", basis_rule or ""))
            else:
                reason = "Base nutricional declarada no resuelta"
        elif d.get("error"):
            reason = "Ficha Alcampo no recuperada"
        else:
            reason = "Falta nutrición declarada comparable"
        if usable: counts["nutritionally_usable"] += 1
        con.execute("INSERT INTO classifications VALUES(?,?,?,?,?)", (pid, "OTHER", "UNKNOWN", 0.0, "pending"))
        con.execute("INSERT INTO eligibility VALUES(?,?,?,?,?,?,?)", (pid, 1, 1, int(usable), 0, 0, reason))

    for k, v in counts.items():
        con.execute("INSERT OR REPLACE INTO catalog_metadata(key,value) VALUES(?,?)", (f"build_count:{k}", str(v)))
    con.commit()
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
