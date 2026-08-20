from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .classify import Classification


SCHEMA_VERSION = "rumbo-catalog-1"
CATALOG_FORMAT = "es.rumbo.catalog.sqlite"
CATALOG_FORMAT_VERSION = "1"
IMPORTER_VERSION = "bedca-2"
CLASSIFIER_VERSION = "bedca-rules-1"


DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE products(
 product_id TEXT PRIMARY KEY, gtin TEXT, name TEXT NOT NULL, name_en TEXT, brand TEXT,
 legal_name TEXT, ingredients TEXT, family TEXT, subcategory TEXT, source_page TEXT,
 source_food_id TEXT NOT NULL UNIQUE, source_group_id TEXT NOT NULL, source_origin TEXT,
 langual TEXT, description TEXT, edible_portion REAL, raw_sha256 TEXT NOT NULL
);
CREATE TABLE retailer_listings(
 retailer TEXT NOT NULL, retailer_sku TEXT NOT NULL, product_id TEXT NOT NULL REFERENCES products,
 url TEXT, price_eur REAL, observed_at TEXT, status TEXT,
 PRIMARY KEY(retailer, retailer_sku)
);
CREATE TABLE nutrition(
 product_id TEXT PRIMARY KEY REFERENCES products, calories REAL, protein_g REAL,
 carbohydrate_g REAL, fat_g REAL, fiber_g REAL, salt_g REAL, sodium_g REAL,
 calories_derived INTEGER NOT NULL,
 evidence_level TEXT NOT NULL, source TEXT NOT NULL, observed_at TEXT, basis_quantity REAL NOT NULL,
 basis_unit TEXT NOT NULL
);
CREATE TABLE nutrient_evidence(
 product_id TEXT NOT NULL REFERENCES products, component_id TEXT NOT NULL, eur_name TEXT,
 component_name TEXT, value REAL, raw_value TEXT, unit TEXT, value_type TEXT, method TEXT,
 citation TEXT, evidence_json TEXT NOT NULL, PRIMARY KEY(product_id, component_id)
);
CREATE TABLE source_records(
 product_id TEXT NOT NULL REFERENCES products, source_food_id TEXT NOT NULL,
 source_origin TEXT, raw_sha256 TEXT NOT NULL, selected INTEGER NOT NULL,
 PRIMARY KEY(product_id, source_food_id)
);
CREATE TABLE classifications(
 product_id TEXT PRIMARY KEY REFERENCES products, classifier_version TEXT NOT NULL,
 classified INTEGER NOT NULL, status TEXT NOT NULL, food_family TEXT,
 food_family_confidence REAL, portion_basis_grams REAL NOT NULL,
 portion_confidence REAL NOT NULL, portion_rule_id TEXT NOT NULL
);
CREATE TABLE classification_roles(
 product_id TEXT NOT NULL REFERENCES products, axis TEXT NOT NULL, role TEXT NOT NULL,
 confidence REAL NOT NULL, rule_id TEXT NOT NULL, evidence TEXT NOT NULL,
 PRIMARY KEY(product_id, axis, role)
);
CREATE INDEX products_name_idx ON products(name);
CREATE INDEX products_family_idx ON products(family);
CREATE INDEX classification_status_idx ON classifications(status);
CREATE INDEX classification_role_idx ON classification_roles(axis, role);
"""


def create(path: Path, records: list[dict]) -> None:
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        connection.executescript(DDL)
        built_at = datetime.now(timezone.utc).isoformat()
        metadata = {
            "catalog_format": CATALOG_FORMAT, "catalog_format_version": CATALOG_FORMAT_VERSION,
            "catalog_id": "bedca-development", "catalog_name": "BEDCA · Alimentos genéricos",
            "catalog_version": "2", "product_id_namespace": "bedca",
            "schema_version": SCHEMA_VERSION, "importer_version": IMPORTER_VERSION,
            "classifier_version": CLASSIFIER_VERSION, "catalog_identity_source": "BEDCA",
            "nutrition_source": "BEDCA", "evidence_level": "GENERIC",
            "built_at": built_at, "redistribution_status": "DEVELOPMENT_ONLY_UNRESOLVED_RIGHTS",
            "product_count": str(len(records)),
        }
        connection.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", metadata.items())
        for record in records:
            _insert(connection, record, built_at)
        connection.commit()
        connection.execute("PRAGMA integrity_check").fetchone()
    finally:
        connection.close()


def _insert(db: sqlite3.Connection, record: dict, observed_at: str) -> None:
    item, detail, nutrition = record["index"], record["detail"], record["nutrition"]
    classification: Classification = record["classification"]
    product_id = f'bedca:{record.get("stable_source_id", item.id)}'
    db.execute("""INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        product_id, None, item.name_es, item.name_en, None, None, None,
        classification.food_family, record["group_name"], "https://www.bedca.net/bdpub/",
        item.id, item.group_id, item.origin, item.langual, detail.get("f_des_esp"),
        _float(detail.get("edible_portion")), detail["raw_sha256"],
    ))
    db.execute("""INSERT INTO nutrition VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        product_id, nutrition["calories"], nutrition["protein_g"], nutrition["carbohydrate_g"],
        nutrition["fat_g"], nutrition["fiber_g"], nutrition["salt_g"], nutrition["sodium_g"],
        int(nutrition.get("calories_derived", False)), "GENERIC", "BEDCA", observed_at,
        100.0, "g edible portion",
    ))
    for source_record in record.get("source_records", [{
        "source_food_id": item.id, "source_origin": item.origin,
        "raw_sha256": detail["raw_sha256"], "selected": True,
    }]):
        db.execute("INSERT INTO source_records VALUES (?,?,?,?,?)", (
            product_id, source_record["source_food_id"], source_record["source_origin"],
            source_record["raw_sha256"], int(source_record["selected"]),
        ))
    for component in detail["components"]:
        component_id = component.get("c_id")
        if not component_id:
            continue
        db.execute("""INSERT OR REPLACE INTO nutrient_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
            product_id, component_id, component.get("eur_name"), component.get("c_ori_name"),
            _float(component.get("best_location")), component.get("best_location"),
            component.get("v_unit"), component.get("value_type"), component.get("m_descripcion"),
            component.get("citation"), json.dumps(component, ensure_ascii=False, sort_keys=True),
        ))
    db.execute("""INSERT INTO classifications VALUES (?,?,?,?,?,?,?,?,?)""", (
        product_id, CLASSIFIER_VERSION, int(classification.status == "MENU_ELIGIBLE"),
        classification.status, classification.food_family,
        classification.confidence if classification.food_family else None,
        classification.portion_basis_grams, classification.confidence, classification.rule_ids[0],
    ))
    for axis, roles in (("NUTRITIONAL", classification.nutritional_roles), ("CULINARY", classification.culinary_roles)):
        for role in roles:
            db.execute("INSERT INTO classification_roles VALUES (?,?,?,?,?,?)", (
                product_id, axis, role, classification.confidence,
                classification.rule_ids[-1] if axis == "NUTRITIONAL" else classification.rule_ids[1],
                f"BEDCA group {item.group_id}; portion {classification.portion_basis_grams:g} g",
            ))


def _float(value: str | None) -> float | None:
    try: return float(value) if value is not None else None
    except ValueError: return None
