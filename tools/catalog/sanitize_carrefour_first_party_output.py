from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import carrefour_first_party_inventory as base
import carrefour_first_party_browser_inventory as browser


GENERIC_PRODUCT_TYPE = re.compile(r"vendidos?\s+por\s+terceros|marketplace", re.I)
# Legacy extractor versions used prefix matching for `Tipo de leche` and could
# turn the real Carrefour label `Tipo de leche tratada / Entera` into the bogus
# value `tratada`. Keep this explicit and narrow so real declared values remain.
INVALID_LEGACY_MILK_TYPE = {"tratada"}


def valid_nutriscore(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text if re.fullmatch(r"[A-E]", text) else None


def sanitize_row(row: dict) -> dict:
    row = dict(row)
    # Product-field names are schema identifiers and can never contain '='.
    # Dropping such keys makes the cumulative staging resilient to accidental
    # JSONL transcription typos without manufacturing or altering a real field.
    for key in list(row):
        if "=" in str(key):
            row.pop(key, None)
    row["nutriscore"] = valid_nutriscore(row.get("nutriscore"))
    attributes = row.get("attributes")
    if isinstance(attributes, dict):
        attributes = dict(attributes)
        product_type = attributes.get("product_type")
        if product_type and GENERIC_PRODUCT_TYPE.search(str(product_type)):
            attributes.pop("product_type", None)
        milk_type = attributes.get("milk_type")
        if milk_type and str(milk_type).strip().casefold() in INVALID_LEGACY_MILK_TYPE:
            attributes.pop("milk_type", None)
        row["attributes"] = attributes
    extra = row.get("nutrition_extra")
    if extra is not None and not isinstance(extra, dict):
        row["nutrition_extra"] = {}
    return row


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Remove demonstrably generic or legacy-parser Carrefour artifacts from first-party fields.")
    ap.add_argument("directory")
    args = ap.parse_args()

    directory = Path(args.directory)
    products_path = directory / "products.jsonl"
    evidence_path = directory / "field_evidence.jsonl"
    rows = [sanitize_row(row) for row in read_jsonl(products_path)]

    by_sku = {row.get("retailer_sku"): row for row in rows}
    evidence = []
    for item in read_jsonl(evidence_path):
        row = by_sku.get(item.get("retailer_sku"), {})
        field = item.get("field")
        if field == "nutriscore" and not row.get("nutriscore"):
            continue
        if field == "attributes" and not row.get("attributes"):
            continue
        if field == "nutrition_extra" and not row.get("nutrition_extra"):
            continue
        if field in {"nutriscore", "attributes", "nutrition_extra"}:
            item = dict(item)
            item["value"] = row.get(field)
        evidence.append(item)

    write_jsonl(products_path, rows)
    write_jsonl(evidence_path, evidence)
    browser.write_sqlite(directory / "carrefour_first_party.sqlite", rows, evidence)

    summary_path = directory / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        coverage = summary.setdefault("coverage", {})
        coverage["nutriscore"] = base.coverage(rows, "nutriscore")
        coverage["attributes"] = base.coverage(rows, "attributes")
        coverage["nutrition_extra"] = base.coverage(rows, "nutrition_extra")
        summary.setdefault("counts", {})["evidence_rows"] = len(evidence)
        summary.setdefault("counts", {})["nutrition_extra_products"] = sum(bool(row.get("nutrition_extra")) for row in rows)
        summary["sample"] = [row for row in rows if not row.get("fetch_error")][:10]
        summary["quality_note"] = (
            "Nutri-Score is retained only when the extracted product value is a single grade A-E. "
            "Generic marketplace/page-chrome text, malformed schema keys and the known legacy milk-label prefix artifact are removed from product attributes. "
            "Raw captured HTML remains the audit source."
        )
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"products": len(rows), "evidence_rows": len(evidence)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
