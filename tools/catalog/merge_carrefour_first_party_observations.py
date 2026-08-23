from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import carrefour_first_party_inventory as base
import carrefour_first_party_browser_inventory as browser
from sanitize_carrefour_first_party_output import sanitize_row

SOURCE = "CARREFOUR_FIRST_PARTY"
EMPTY = (None, "", [], {})
CORRECTION_CLEAR_FIELDS_KEY = "_clear_fields"

DECLARED_FIELDS = {
    "gtin", "brand", "legal_name", "ingredients", "allergens", "net_content",
    "storage_conditions", "preparation_instructions", "operator_address",
    "manufacturer_packer_importer", "mandatory_mentions", "nutriscore", "attributes",
    "nutrition_basis", "nutrition_extra", "energy_kj", "calories_kcal", "fat_g",
    "saturates_g", "carbohydrate_g", "sugars_g", "fiber_g", "protein_g", "salt_g",
}
OBSERVED_FIELDS = {
    "retailer_sku", "canonical_url", "name", "image_url", "category_path",
    "price_eur", "price_currency", "unit_price_text", "availability",
}
# Correction batches may retract previously merged evidence when a later audit proves
# that a captured field was generic, truncated or otherwise invalid. Identity keys are
# deliberately excluded: a correction must never silently turn one product into another.
CORRECTABLE_FIELDS = ((DECLARED_FIELDS | OBSERVED_FIELDS) - {"retailer_sku", "canonical_url", "name"}) | {"nutrition_status"}
COVERAGE_FIELDS = [
    "retailer_sku", "canonical_url", "gtin", "name", "brand", "image_url", "category_path", "price_eur", "unit_price_text",
    "availability", "legal_name", "ingredients", "allergens", "net_content",
    "storage_conditions", "preparation_instructions", "operator_address",
    "manufacturer_packer_importer", "mandatory_mentions", "nutriscore", "attributes",
    "nutrition_extra",
]
NUTRITION_FIELDS = [
    "energy_kj", "calories_kcal", "fat_g", "saturates_g", "carbohydrate_g",
    "sugars_g", "fiber_g", "protein_g", "salt_g",
]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object")
        rows.append(value)
    return rows


def nonempty(value: Any) -> bool:
    return value not in EMPTY


def apply_field_corrections(row: dict) -> dict:
    """Apply explicit, auditable field retractions and strip correction metadata."""
    corrected = dict(row)
    requested = corrected.pop(CORRECTION_CLEAR_FIELDS_KEY, [])
    if requested in EMPTY:
        return corrected
    if not isinstance(requested, list) or not all(isinstance(field, str) for field in requested):
        raise ValueError(f"{CORRECTION_CLEAR_FIELDS_KEY} must be a list of field names")
    invalid = sorted(set(requested) - CORRECTABLE_FIELDS)
    if invalid:
        raise ValueError(f"Unsupported first-party field retraction(s): {', '.join(invalid)}")
    for field in requested:
        corrected[field] = None
    return corrected


def merge_product(old: dict, new: dict) -> dict:
    """Merge two direct Carrefour observations without letting nulls erase evidence.

    The sole exception is an explicit `_clear_fields` correction. This is required so
    a later audit can retract demonstrably bad evidence from the recursively persisted
    cumulative staging dataset instead of letting a stale value survive forever.
    """
    merged = dict(old)
    requested_clear = new.get(CORRECTION_CLEAR_FIELDS_KEY, [])
    if requested_clear not in EMPTY:
        if not isinstance(requested_clear, list) or not all(isinstance(field, str) for field in requested_clear):
            raise ValueError(f"{CORRECTION_CLEAR_FIELDS_KEY} must be a list of field names")
        invalid = sorted(set(requested_clear) - CORRECTABLE_FIELDS)
        if invalid:
            raise ValueError(f"Unsupported first-party field retraction(s): {', '.join(invalid)}")
        for field in requested_clear:
            merged[field] = None
    for key, value in new.items():
        if key == CORRECTION_CLEAR_FIELDS_KEY or not nonempty(value):
            continue
        if key == "attributes" and isinstance(value, dict):
            attrs = dict(merged.get("attributes") or {})
            attrs.update(value)
            merged[key] = attrs
        elif key == "nutrition_extra" and isinstance(value, dict):
            extra = dict(merged.get("nutrition_extra") or {})
            extra.update(value)
            merged[key] = extra
        else:
            merged[key] = value
    merged.pop(CORRECTION_CLEAR_FIELDS_KEY, None)
    return sanitize_row(merged)


def product_key(row: dict) -> str | None:
    sku = row.get("retailer_sku")
    if nonempty(sku):
        return f"sku:{sku}"
    url = row.get("canonical_url")
    if nonempty(url):
        return f"url:{str(url).split('?', 1)[0]}"
    return None


def merge_products(paths: list[Path]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for path in paths:
        for raw in read_jsonl(path):
            if raw.get("source") != SOURCE:
                continue
            if raw.get("fetch_error"):
                continue
            key = product_key(raw)
            if not key:
                continue
            row = sanitize_row(raw)
            if key in by_key:
                by_key[key] = merge_product(by_key[key], row)
            else:
                by_key[key] = sanitize_row(apply_field_corrections(row))
    return sorted(by_key.values(), key=lambda row: str(row.get("retailer_sku") or row.get("canonical_url") or ""))


def evidence_signature(item: dict) -> tuple[str, str, str]:
    value = json.dumps(item.get("value"), ensure_ascii=False, sort_keys=True, default=str)
    return str(item.get("retailer_sku")), str(item.get("field")), value


def generated_evidence(rows: list[dict]) -> list[dict]:
    evidence: list[dict] = []
    for row in rows:
        sku = row.get("retailer_sku")
        url = row.get("canonical_url")
        observed_at = row.get("observed_at")
        if not sku or not url:
            continue
        observed_evidence_type = (
            "OBSERVED_PRODUCT_PAGE" if row.get("direct_page_observed") else "OBSERVED_LISTING"
        )
        for field in sorted(DECLARED_FIELDS | OBSERVED_FIELDS):
            value = row.get(field)
            if not nonempty(value):
                continue
            evidence.append({
                "retailer_sku": sku,
                "field": field,
                "value": value,
                "source": SOURCE,
                "evidence_type": "DECLARED" if field in DECLARED_FIELDS else observed_evidence_type,
                "source_url": url,
                "source_host": row.get("source_host"),
                "observed_at": observed_at,
                "capture_method": row.get("capture_method"),
                "direct_page_observed": bool(row.get("direct_page_observed")),
                "listing_only_observed": bool(row.get("listing_only_observed")),
                "retrieval_freshness": row.get("retrieval_freshness"),
            })
    return evidence


def merge_evidence(rows: list[dict], evidence_paths: list[Path]) -> list[dict]:
    rows_by_sku = {row.get("retailer_sku"): row for row in rows if row.get("retailer_sku")}
    valid_skus = set(rows_by_sku)
    merged: dict[tuple[str, str, str], dict] = {}
    for path in evidence_paths:
        for item in read_jsonl(path):
            sku = item.get("retailer_sku")
            field = item.get("field")
            if item.get("source") != SOURCE or sku not in valid_skus:
                continue
            # A corrected cumulative product is authoritative for whether a field still
            # exists. Do not retain stale evidence rows for an explicitly retracted value.
            if field in DECLARED_FIELDS | OBSERVED_FIELDS and not nonempty(rows_by_sku[sku].get(field)):
                continue
            merged[evidence_signature(item)] = item
    for item in generated_evidence(rows):
        merged.setdefault(evidence_signature(item), item)
    return sorted(merged.values(), key=lambda item: (str(item.get("retailer_sku")), str(item.get("field"))))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def read_candidate_count(path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    for key in ("unique_carrefour_urls", "rows", "candidate_urls"):
        count = value.get(key) if isinstance(value, dict) else None
        if isinstance(count, int):
            return count
    return 0


def build_summary(rows: list[dict], evidence: list[dict], candidate_count: int) -> dict:
    methods: dict[str, int] = {}
    for row in rows:
        method = str(row.get("capture_method") or "UNSPECIFIED_DIRECT_CAPTURE")
        methods[method] = methods.get(method, 0) + 1
    complete = sum(row.get("nutrition_status") == "DECLARED_COMPLETE" for row in rows)
    partial = sum(row.get("nutrition_status") == "DECLARED_PARTIAL" for row in rows)
    return {
        "retailer": "CARREFOUR",
        "source": "https://www.carrefour.es",
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "built_at": base.now_iso(),
        "inventory_complete": False,
        "classification_performed": False,
        "counts": {
            "verified_direct_products": len(rows),
            "nutrition_complete": complete,
            "nutrition_partial": partial,
            "nutrition_not_found": len(rows) - complete - partial,
            "evidence_rows": len(evidence),
            "external_candidate_identity_urls_not_counted_as_first_party": candidate_count,
        },
        "capture_methods": methods,
        "coverage": {field: base.coverage(rows, field) for field in COVERAGE_FIELDS},
        "nutrition_field_coverage": {field: base.coverage(rows, field) for field in NUTRITION_FIELDS},
        "sample": rows[:20],
        "provenance_note": (
            "Only fields observed directly on official carrefour.es pages are merged. Third-party catalogs may seed candidate URLs, "
            "but their product facts are never promoted to CARREFOUR_FIRST_PARTY."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge auditable direct Carrefour observations from multiple capture methods.")
    ap.add_argument("--products", nargs="+", required=True, help="One or more CARREFOUR_FIRST_PARTY JSONL product files")
    ap.add_argument("--evidence", nargs="*", default=[], help="Optional existing field-evidence JSONL files")
    ap.add_argument("--candidate-summary")
    ap.add_argument("--out-products", required=True)
    ap.add_argument("--out-evidence", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--sqlite", required=True)
    args = ap.parse_args()

    rows = merge_products([Path(p) for p in args.products])
    evidence = merge_evidence(rows, [Path(p) for p in args.evidence])
    candidate_count = read_candidate_count(Path(args.candidate_summary) if args.candidate_summary else None)

    write_jsonl(Path(args.out_products), rows)
    write_jsonl(Path(args.out_evidence), evidence)
    summary = build_summary(rows, evidence, candidate_count)
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    sqlite_path = Path(args.sqlite)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    browser.write_sqlite(sqlite_path, rows, evidence)
    print(json.dumps(summary["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())