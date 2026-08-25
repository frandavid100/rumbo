from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SOURCE = "CARREFOUR_FIRST_PARTY"
EMPTY = (None, "", [], {})

PRODUCT_FIELDS = [
    "gtin", "name", "brand", "image_url", "category_path", "price_eur", "price_currency",
    "unit_price_text", "availability", "legal_name", "ingredients", "allergens", "net_content",
    "storage_conditions", "preparation_instructions", "operator_address", "manufacturer_packer_importer",
    "mandatory_mentions", "nutriscore", "attributes", "nutrition_basis", "nutrition_status", "energy_kj",
    "calories_kcal", "fat_g", "saturates_g", "carbohydrate_g", "sugars_g", "fiber_g", "protein_g",
    "salt_g",
]
NUTRITION_FIELDS = [
    "energy_kj", "calories_kcal", "fat_g", "saturates_g", "carbohydrate_g", "sugars_g",
    "fiber_g", "protein_g", "salt_g",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def nonempty(value) -> bool:
    return value not in EMPTY


def merge_value(old, new):
    if not nonempty(new):
        return old
    if isinstance(old, dict) and isinstance(new, dict):
        merged = dict(old)
        for key, value in new.items():
            if nonempty(value):
                merged[key] = value
        return merged
    return new


def merge_product(old: dict | None, new: dict) -> dict:
    if old is None:
        return dict(new)
    merged = dict(old)
    for key, value in new.items():
        merged[key] = merge_value(merged.get(key), value)
    merged["retailer"] = "CARREFOUR"
    merged["source"] = SOURCE
    return merged


def evidence_key(row: dict) -> tuple:
    # Keep observations append-only. observed_at is deliberately part of the key so a fresh declaration
    # never destroys an older direct Carrefour observation of the same field.
    return (
        row.get("retailer_sku"), row.get("field"), row.get("source"), row.get("source_url"),
        row.get("observed_at"), json.dumps(row.get("value"), ensure_ascii=False, sort_keys=True),
    )


def coverage(rows: list[dict], field: str) -> dict:
    count = sum(nonempty(row.get(field)) for row in rows)
    total = len(rows)
    return {"count": count, "pct": round(100.0 * count / total, 2) if total else 0.0}


def sqlite_text(value):
    """Preserve structured first-party declarations in TEXT columns without losing information."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def sqlite_number(value):
    """Store only actual numeric values in numeric SQLite columns; JSONL/evidence remains lossless."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        raw = value.strip().replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def build_sqlite(path: Path, rows: list[dict], evidence: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE products(
          retailer_sku TEXT PRIMARY KEY, gtin TEXT, name TEXT, brand TEXT, canonical_url TEXT,
          image_url TEXT, category_path_json TEXT, price_eur REAL, price_currency TEXT,
          unit_price_text TEXT, availability TEXT, legal_name TEXT, ingredients TEXT, allergens TEXT,
          net_content TEXT, storage_conditions TEXT, preparation_instructions TEXT, operator_address TEXT,
          manufacturer_packer_importer TEXT, observed_at TEXT, nutrition_status TEXT, source TEXT
        );
        CREATE TABLE nutrition(
          retailer_sku TEXT PRIMARY KEY, nutrition_basis TEXT, energy_kj REAL, calories_kcal REAL,
          fat_g REAL, saturates_g REAL, carbohydrate_g REAL, sugars_g REAL, fiber_g REAL,
          protein_g REAL, salt_g REAL, nutrition_status TEXT, source TEXT, evidence_type TEXT
        );
        CREATE TABLE field_evidence(
          retailer_sku TEXT, field TEXT, source TEXT, evidence_type TEXT, value_json TEXT,
          source_url TEXT, observed_at TEXT
        );
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT);
        """
    )
    for r in rows:
        db.execute(
            "INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                sqlite_text(r.get("retailer_sku")), sqlite_text(r.get("gtin")), sqlite_text(r.get("name")),
                sqlite_text(r.get("brand")), sqlite_text(r.get("canonical_url")), sqlite_text(r.get("image_url")),
                json.dumps(r.get("category_path") or [], ensure_ascii=False, sort_keys=True),
                sqlite_number(r.get("price_eur")), sqlite_text(r.get("price_currency")),
                sqlite_text(r.get("unit_price_text")), sqlite_text(r.get("availability")),
                sqlite_text(r.get("legal_name")), sqlite_text(r.get("ingredients")), sqlite_text(r.get("allergens")),
                sqlite_text(r.get("net_content")), sqlite_text(r.get("storage_conditions")),
                sqlite_text(r.get("preparation_instructions")), sqlite_text(r.get("operator_address")),
                sqlite_text(r.get("manufacturer_packer_importer")), sqlite_text(r.get("observed_at")),
                sqlite_text(r.get("nutrition_status")), SOURCE,
            ),
        )
        db.execute(
            "INSERT OR REPLACE INTO nutrition VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                sqlite_text(r.get("retailer_sku")), sqlite_text(r.get("nutrition_basis")),
                sqlite_number(r.get("energy_kj")), sqlite_number(r.get("calories_kcal")),
                sqlite_number(r.get("fat_g")), sqlite_number(r.get("saturates_g")),
                sqlite_number(r.get("carbohydrate_g")), sqlite_number(r.get("sugars_g")),
                sqlite_number(r.get("fiber_g")), sqlite_number(r.get("protein_g")), sqlite_number(r.get("salt_g")),
                sqlite_text(r.get("nutrition_status")), SOURCE, "DECLARED",
            ),
        )
    for e in evidence:
        db.execute(
            "INSERT INTO field_evidence VALUES(?,?,?,?,?,?,?)",
            (
                e.get("retailer_sku"), e.get("field"), e.get("source"), e.get("evidence_type"),
                json.dumps(e.get("value"), ensure_ascii=False), e.get("source_url"), e.get("observed_at"),
            ),
        )
    metadata = {
        "retailer": "CARREFOUR",
        "source": SOURCE,
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "classification_performed": "false",
        "built_at": now_iso(),
    }
    db.executemany("INSERT INTO metadata VALUES(?,?)", metadata.items())
    db.commit()
    db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", default="fixtures")
    ap.add_argument("--fresh", default="carrefour-first-party-fresh-inventory")
    ap.add_argument("--frontier", default="carrefour-first-party-category-frontier")
    ap.add_argument("--sqlite", default="carrefour-first-party-cumulative/carrefour_first_party.sqlite")
    args = ap.parse_args()

    fixtures = Path(args.fixtures)
    fresh = Path(args.fresh)
    frontier = Path(args.frontier)
    products_path = fixtures / "carrefour_first_party_products_cumulative.jsonl"
    evidence_path = fixtures / "carrefour_first_party_field_evidence_cumulative.jsonl"
    summary_path = fixtures / "carrefour_first_party_cumulative_summary.json"

    products: dict[str, dict] = {}
    for row in read_jsonl(products_path):
        sku = row.get("retailer_sku")
        if sku and row.get("source") == SOURCE:
            products[sku] = merge_product(products.get(sku), row)

    # Product URLs/SKUs discovered on official Carrefour category pages are valid first-party identity evidence.
    # Keep them even if the product detail page is later blocked; do not infer a name from the URL slug.
    frontier_rows = read_jsonl(frontier / "product_candidates.jsonl")
    for row in frontier_rows:
        sku = row.get("retailer_sku")
        if not sku or row.get("source") != SOURCE:
            continue
        minimal = {
            "retailer": "CARREFOUR",
            "retailer_sku": sku,
            "canonical_url": row.get("url"),
            "source": SOURCE,
            "observed_at": row.get("observed_at"),
            "listing_only_observed": True,
            "nutrition_status": "NOT_FETCHED",
        }
        products[sku] = merge_product(products.get(sku), minimal)

    fresh_rows = read_jsonl(fresh / "products.jsonl")
    for row in fresh_rows:
        sku = row.get("retailer_sku")
        if not sku or row.get("source") != SOURCE or row.get("fetch_error"):
            continue
        row = dict(row)
        row["listing_only_observed"] = False
        products[sku] = merge_product(products.get(sku), row)

    evidence_map: dict[tuple, dict] = {}
    for row in read_jsonl(evidence_path) + read_jsonl(fresh / "field_evidence.jsonl") + frontier_rows:
        if row.get("source") != SOURCE:
            continue
        # Frontier candidate rows are identity observations, not product field declarations.
        if "field" not in row:
            sku = row.get("retailer_sku")
            if not sku:
                continue
            row = {
                "retailer_sku": sku,
                "field": "canonical_url",
                "value": row.get("url"),
                "source": SOURCE,
                "evidence_type": "OBSERVED_LISTING",
                "source_url": row.get("source_url"),
                "observed_at": row.get("observed_at"),
            }
        evidence_map[evidence_key(row)] = row
    evidence = sorted(evidence_map.values(), key=lambda e: (
        str(e.get("retailer_sku") or ""), str(e.get("field") or ""), str(e.get("observed_at") or ""),
    ))

    # Recover scalar fields that may have disappeared from a newer composite row while their direct evidence
    # remains in the append-only evidence ledger. Newest direct observation wins only when the composite is empty.
    latest_by_field: dict[tuple[str, str], dict] = {}
    for item in evidence:
        sku, field = item.get("retailer_sku"), item.get("field")
        if sku and field and nonempty(item.get("value")):
            latest_by_field[(sku, field)] = item
    for sku, row in products.items():
        for field in PRODUCT_FIELDS:
            if nonempty(row.get(field)):
                continue
            item = latest_by_field.get((sku, field))
            if item:
                row[field] = item.get("value")

    rows = [products[k] for k in sorted(products)]
    write_jsonl(products_path, rows)
    write_jsonl(evidence_path, evidence)

    status_counts = Counter(str(r.get("nutrition_status") or "UNKNOWN") for r in rows)
    evidence_type_counts = Counter(str(e.get("evidence_type") or "UNKNOWN") for e in evidence)
    field_counts = Counter(str(e.get("field") or "UNKNOWN") for e in evidence)
    first_party_detail = [r for r in rows if not r.get("listing_only_observed")]
    summary = {
        "retailer": "CARREFOUR",
        "source": SOURCE,
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "classification_performed": False,
        "built_at": now_iso(),
        "counts": {
            "products_total": len(rows),
            "products_detail_observed": len(first_party_detail),
            "products_listing_only": sum(bool(r.get("listing_only_observed")) for r in rows),
            "evidence_rows": len(evidence),
            "nutrition_status": dict(sorted(status_counts.items())),
            "evidence_types": dict(sorted(evidence_type_counts.items())),
        },
        "coverage": {field: coverage(rows, field) for field in PRODUCT_FIELDS},
        "nutrition_field_coverage": {field: coverage(rows, field) for field in NUTRITION_FIELDS},
        "evidence_field_counts": dict(sorted(field_counts.items())),
        "sample": rows[:12],
        "notes": [
            "Only direct carrefour.es observations are counted as Carrefour evidence.",
            "Third-party datasets may seed product URLs but are never copied into this cumulative first-party dataset.",
            "Category-listing identities are retained even when product detail retrieval is blocked.",
            "Field evidence is append-only by observation timestamp; newer sparse pages do not erase older direct observations.",
            "No Rumbo nutritional or culinary classification is performed here.",
        ],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    build_sqlite(Path(args.sqlite), rows, evidence)
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())