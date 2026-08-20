from __future__ import annotations

import argparse
import json
from pathlib import Path

import carrefour_first_party_inventory as base
import carrefour_first_party_browser_inventory as browser
from sanitize_carrefour_first_party_output import sanitize_row


FIELDS = [
    "gtin", "name", "brand", "image_url", "category_path", "price_eur", "unit_price_text", "availability",
    "legal_name", "ingredients", "allergens", "net_content", "storage_conditions", "preparation_instructions",
    "operator_address", "manufacturer_packer_importer", "mandatory_mentions", "nutriscore", "attributes",
]
NUTRITION_FIELDS = [
    "energy_kj", "calories_kcal", "fat_g", "saturates_g", "carbohydrate_g", "sugars_g", "fiber_g",
    "protein_g", "salt_g",
]
DEFAULT_CANDIDATE_SUMMARY = Path("fixtures/carrefour_candidate_urls_radarsuper.summary.json")


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--sqlite", required=True)
    ap.add_argument("--candidate-summary", default=str(DEFAULT_CANDIDATE_SUMMARY))
    args = ap.parse_args()

    rows = [sanitize_row(row) for row in read_jsonl(Path(args.products)) if not row.get("fetch_error")]
    evidence = read_jsonl(Path(args.evidence))
    by_sku = {row.get("retailer_sku"): row for row in rows}
    clean_evidence = []
    for item in evidence:
        row = by_sku.get(item.get("retailer_sku"))
        if not row:
            continue
        field = item.get("field")
        if field == "nutriscore" and not row.get("nutriscore"):
            continue
        if field == "attributes" and not row.get("attributes"):
            continue
        if field in {"nutriscore", "attributes"}:
            item = dict(item)
            item["value"] = row.get(field)
        clean_evidence.append(item)

    rows.sort(key=lambda r: r.get("retailer_sku") or "")
    complete = sum(row.get("nutrition_status") == "DECLARED_COMPLETE" for row in rows)
    partial = sum(row.get("nutrition_status") == "DECLARED_PARTIAL" for row in rows)
    no_nutrition = sum(row.get("nutrition_status") == "NOT_FOUND" for row in rows)

    candidate_summary = read_json(Path(args.candidate_summary))
    external_candidate_urls = candidate_summary.get("unique_carrefour_urls")
    if not isinstance(external_candidate_urls, int):
        external_candidate_urls = candidate_summary.get("rows")
    if not isinstance(external_candidate_urls, int):
        external_candidate_urls = 0

    report = {
        "retailer": "CARREFOUR",
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "source": "https://www.carrefour.es",
        "built_at": base.now_iso(),
        "classification_performed": "false",
        "inventory_complete": False,
        "counts": {
            "products": len(rows),
            "nutrition_complete": complete,
            "nutrition_partial": partial,
            "nutrition_not_found": no_nutrition,
            "evidence_rows": len(clean_evidence),
            "external_candidate_identity_urls_not_counted_as_first_party": external_candidate_urls,
        },
        "coverage": {field: base.coverage(rows, field) for field in FIELDS},
        "nutrition_field_coverage": {field: base.coverage(rows, field) for field in NUTRITION_FIELDS},
        "sample": rows[:20],
        "provenance_note": "Every populated product field counted here was observed directly on carrefour.es. Candidate URLs from third-party mirrors are discovery inputs only and are not counted as Carrefour evidence.",
        "candidate_identity_note": "The external candidate URL count is reported only to measure the pending verification pool; it is not Carrefour first-party coverage.",
        "quality_note": "Nutri-Score is retained only as a single A-E grade; demonstrably generic marketplace/page chrome is excluded from product attributes.",
    }

    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    sqlite_path = Path(args.sqlite)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    browser.write_sqlite(sqlite_path, rows, clean_evidence)
    print(json.dumps(report["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())