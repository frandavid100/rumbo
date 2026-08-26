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
DETAIL_FIELDS = [
    "legal_name", "ingredients", "allergens", "net_content", "storage_conditions",
    "preparation_instructions", "operator_address", "manufacturer_packer_importer",
    "mandatory_mentions", "nutriscore", "nutrition_basis", *NUTRITION_FIELDS,
]
MANUAL_WEB_OBSERVED_FIELDS = {
    "retailer_sku", "canonical_url", "name", "brand", "image_url", "category_path",
    "price_eur", "price_currency", "unit_price_text", "availability",
}


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
        merged = dict(new)
        merged["retailer"] = "CARREFOUR"
        merged["source"] = SOURCE
        return merged
    merged = dict(old)
    for key, value in new.items():
        if key == "listing_only_observed":
            if value is False or merged.get(key) is False:
                merged[key] = False
            elif key not in merged and value is True:
                merged[key] = True
            continue
        merged[key] = merge_value(merged.get(key), value)
    merged["retailer"] = "CARREFOUR"
    merged["source"] = SOURCE
    return merged


def merge_product_fill_missing(old: dict | None, new: dict) -> dict:
    """Merge an archived official observation without letting it overwrite newer cumulative values."""
    if old is None:
        return merge_product(None, new)
    merged = dict(old)
    was_listing_only = merged.get("listing_only_observed") is True
    for key, value in new.items():
        if key == "listing_only_observed":
            continue
        old_value = merged.get(key)
        if isinstance(old_value, dict) and isinstance(value, dict):
            combined = dict(old_value)
            for subkey, subvalue in value.items():
                if subkey not in combined and nonempty(subvalue):
                    combined[subkey] = subvalue
            merged[key] = combined
        elif not nonempty(old_value) and nonempty(value):
            merged[key] = value
    if new.get("listing_only_observed") is False:
        merged["listing_only_observed"] = False
        if was_listing_only and nonempty(new.get("observed_at")):
            merged["observed_at"] = new.get("observed_at")
    elif "listing_only_observed" not in merged and new.get("listing_only_observed") is True:
        merged["listing_only_observed"] = True
    merged["retailer"] = "CARREFOUR"
    merged["source"] = SOURCE
    return merged


def read_manual_first_party_rows(fixtures: Path) -> list[dict]:
    """Load archived agent observations verified on official Carrefour PDPs or category listings.

    Direct PDP observations may predate listing_only_observed. Official category-listing observations
    are retained as listing-only and may never supply detail-only declarations.
    """
    rows: list[dict] = []
    for path in sorted(fixtures.glob("carrefour_first_party_agent_web_products_*.jsonl")):
        for original in read_jsonl(path):
            row = dict(original)
            url = str(row.get("canonical_url") or "")
            official_url = url.startswith("https://www.carrefour.es/") or url.startswith("https://carrefour.es/")
            direct = row.get("direct_page_observed") is True
            listing = (
                row.get("direct_page_observed") is False
                and str(row.get("capture_method") or "").startswith("OPENAI_WEB_OFFICIAL_CATEGORY")
            )
            valid = (
                row.get("retailer") == "CARREFOUR"
                and row.get("source") == SOURCE
                and bool(row.get("retailer_sku"))
                and official_url
                and (direct or listing)
            )
            if direct and row.get("listing_only_observed") is True:
                valid = False
            if not valid:
                raise SystemExit(f"unsafe Carrefour manual first-party row in {path.name}: {row.get('retailer_sku')!r}")
            row["listing_only_observed"] = not direct
            if listing and any(nonempty(row.get(field)) for field in DETAIL_FIELDS):
                raise SystemExit(
                    f"listing-only Carrefour row contains detail fields in {path.name}: {row.get('retailer_sku')!r}"
                )
            rows.append(row)
    return rows


def manual_first_party_evidence(rows: list[dict]) -> list[dict]:
    evidence: list[dict] = []
    fields = ["retailer_sku", "canonical_url", *PRODUCT_FIELDS]
    for row in rows:
        sku = row.get("retailer_sku")
        source_url = row.get("canonical_url")
        is_listing = row.get("listing_only_observed") is True
        for field in fields:
            if field == "nutrition_status":
                continue
            value = row.get(field)
            if not nonempty(value):
                continue
            if is_listing:
                evidence_type = "OBSERVED_LISTING"
            else:
                evidence_type = "OBSERVED_PRODUCT_PAGE" if field in MANUAL_WEB_OBSERVED_FIELDS else "DECLARED"
            evidence.append({
                "retailer_sku": sku,
                "field": field,
                "value": value,
                "source": SOURCE,
                "evidence_type": evidence_type,
                "source_url": source_url,
                "observed_at": row.get("observed_at"),
                "capture_method": row.get("capture_method"),
                "discovery_source": row.get("discovery_source"),
            })
    return evidence


def evidence_key(row: dict) -> tuple:
    return (
        row.get("retailer_sku"), row.get("field"), row.get("source"), row.get("source_url"),
        row.get("observed_at"), json.dumps(row.get("value"), ensure_ascii=False, sort_keys=True),
    )


def coverage(rows: list[dict], field: str) -> dict:
    count = sum(nonempty(row.get(field)) for row in rows)
    total = len(rows)
    return {"count": count, "pct": round(100.0 * count / total, 2) if total else 0.0}


def sqlite_text(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def sqlite_number(value):
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


def repair_observation_strength(row: dict) -> None:
    if any(nonempty(row.get(field)) for field in DETAIL_FIELDS):
        row["listing_only_observed"] = False
    if row.get("nutrition_status") == "NOT_FETCHED":
        core = [row.get("calories_kcal"), row.get("fat_g"), row.get("carbohydrate_g"), row.get("protein_g")]
        if all(nonempty(value) for value in core):
            row["nutrition_status"] = "DECLARED_COMPLETE"
        elif any(nonempty(row.get(field)) for field in NUTRITION_FIELDS):
            row["nutrition_status"] = "DECLARED_PARTIAL"


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

    frontier_rows = read_jsonl(frontier / "product_candidates.jsonl")
    for row in frontier_rows:
        sku = row.get("retailer_sku")
        if not sku or row.get("source") != SOURCE:
            continue
        old = products.get(sku)
        minimal = {
            "retailer": "CARREFOUR",
            "retailer_sku": sku,
            "canonical_url": row.get("url"),
            "source": SOURCE,
            "observed_at": row.get("observed_at"),
            "listing_only_observed": True,
        }
        if old is None:
            minimal["nutrition_status"] = "NOT_FETCHED"
        products[sku] = merge_product(old, minimal)

    manual_rows = read_manual_first_party_rows(fixtures)
    for row in manual_rows:
        sku = row.get("retailer_sku")
        products[sku] = merge_product_fill_missing(products.get(sku), row)

    fresh_rows = read_jsonl(fresh / "products.jsonl")
    for row in fresh_rows:
        sku = row.get("retailer_sku")
        if not sku or row.get("source") != SOURCE or row.get("fetch_error"):
            continue
        row = dict(row)
        row["listing_only_observed"] = False
        products[sku] = merge_product(products.get(sku), row)

    manual_evidence = manual_first_party_evidence(manual_rows)
    evidence_map: dict[tuple, dict] = {}
    for row in read_jsonl(evidence_path) + read_jsonl(fresh / "field_evidence.jsonl") + frontier_rows + manual_evidence:
        if row.get("source") != SOURCE:
            continue
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
        repair_observation_strength(row)

    rows = [products[k] for k in sorted(products)]
    write_jsonl(products_path, rows)
    write_jsonl(evidence_path, evidence)

    status_counts = Counter(str(r.get("nutrition_status") or "UNKNOWN") for r in rows)
    evidence_type_counts = Counter(str(e.get("evidence_type") or "UNKNOWN") for e in evidence)
    field_counts = Counter(str(e.get("field") or "UNKNOWN") for e in evidence)
    first_party_detail = [r for r in rows if r.get("listing_only_observed") is not True]
    summary = {
        "retailer": "CARREFOUR",
        "source": SOURCE,
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "classification_performed": False,
        "built_at": now_iso(),
        "counts": {
            "products_total": len(rows),
            "products_detail_observed": len(first_party_detail),
            "products_listing_only": sum(r.get("listing_only_observed") is True for r in rows),
            "manual_first_party_fixture_rows": len(manual_rows),
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
            "Agent/web fixtures may contain official Carrefour PDP or category-listing observations; listing rows are explicitly retained as OBSERVED_LISTING and cannot contribute detail-only declarations.",
            "Legacy direct-web fixtures may omit listing_only_observed; direct_page_observed plus an official Carrefour canonical URL controls normalization.",
            "Category-listing identities are retained even when product detail retrieval is blocked.",
            "Field evidence is append-only by observation timestamp; newer sparse pages do not erase older direct observations.",
            "A later category listing cannot downgrade a previously observed product detail or its proved nutrition status.",
            "No Rumbo nutritional or culinary classification is performed here.",
        ],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    build_sqlite(Path(args.sqlite), rows, evidence)
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())