from __future__ import annotations

import argparse
import json
from pathlib import Path

import carrefour_first_party_inventory as base
import carrefour_first_party_browser_inventory as browser

VERSION = "carrefour-first-party-saved-html-1.2"

# Conservative whitelist of product-specific labels observed on Carrefour product
# pages. These remain raw declared characteristics; they are not Rumbo roles or
# classifications. Unknown labels are deliberately not guessed.
ATTRIBUTE_LABELS = {
    "health_characteristic": ["Característica salud", "Caracteristica salud"],
    "elaboration": ["Elaboración", "Elaboracion"],
    "packaging": ["Envase"],
    "format": ["Formato"],
    "origin": ["Origen", "País de origen", "Pais de origen", "País de origen o procedencia", "Pais de origen o procedencia"],
    "variety": ["Variedad"],
    "caliber": ["Calibre"],
    "sanitary_registration": ["Nº Registro sanitario del fabricante/envasador", "N° Registro sanitario del fabricante/envasador"],
    "gluten_free": ["Sin gluten"],
    "vegetarian": ["Vegetariano"],
    "refrigerated": ["Refrigerado"],
    "oil_type": ["Tipo de aceite", "Tipo de aceite(Mayonesas)", "Tipo de aceite (Mayonesas)"],
    "container_presentation": ["Presentación del envase", "Presentacion del envase"],
    "container_format": ["Formato del envase"],
    "bread_format": ["Formato de pan"],
    "pasta_type": ["Tipo pasta"],
    "pasta_base": ["Base de la pasta"],
    "sauce_type": ["Tipo salsas"],
    "cheese_curing": ["Curación queso", "Curacion queso"],
    "cheese_format": ["Formato quesos"],
    "cheese_variety": ["Variedad de queso"],
    "yogurt_type": ["Tipo de yogur"],
    "yogurt_milk_origin": ["Origen leche del yogur"],
    "milk_type": ["Tipo de leche"],
    "milk_treatment": ["Tratamiento de la leche"],
    "meat_breed": ["Raza"],
}
MANDATORY_MENTION_LABELS = [
    "Menciones obligatorias",
    "Menciones Obligatorias",
    "Otras Menciones Obligatorias",
    "Otra información obligatoria",
    "Otra informacion obligatoria",
]


def nonempty(value):
    return value not in (None, "", [], {})


def replace_evidence(evidence: list[dict], row: dict, field: str, value, evidence_type: str = "DECLARED") -> None:
    evidence[:] = [item for item in evidence if item.get("field") != field]
    if nonempty(value):
        evidence.append({
            "retailer_sku": row.get("retailer_sku"),
            "field": field,
            "value": value,
            "source": base.SOURCE,
            "evidence_type": evidence_type,
            "source_url": row.get("canonical_url"),
            "observed_at": row.get("observed_at"),
        })


def augment_declared_fields(row: dict, evidence: list[dict], text: str) -> None:
    attributes = dict(row.get("attributes") or {})
    for key, labels in ATTRIBUTE_LABELS.items():
        value = base.labelled_value(text, labels)
        if nonempty(value):
            attributes[key] = value
    row["attributes"] = attributes
    replace_evidence(evidence, row, "attributes", attributes)

    if not row.get("mandatory_mentions"):
        row["mandatory_mentions"] = base.labelled_value(text, MANDATORY_MENTION_LABELS)
    replace_evidence(evidence, row, "mandatory_mentions", row.get("mandatory_mentions"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe-dir", required=True)
    ap.add_argument("--out", default="carrefour-first-party-saved-html")
    args = ap.parse_args()

    probe = Path(args.probe_dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = probe / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    rows = []
    evidence = []
    for item in summary.get("rows") or []:
        saved = item.get("saved_html")
        if not saved or not item.get("ok"):
            continue
        raw = (probe / saved).read_text(encoding="utf-8")
        url = item.get("url")
        final_url = item.get("final_url") or url
        status = item.get("status")
        text = base.html_to_text(raw)
        row, ev = browser.extract_from_html(url, final_url, status, raw, text)
        augment_declared_fields(row, ev, text)
        row["capture_method"] = "PLAYWRIGHT_SAVED_HTML"
        row["capture_probe_version"] = summary.get("version")
        rows.append(row)
        evidence.extend(ev)

    rows.sort(key=lambda r: r["retailer_sku"])
    with (out / "products.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out / "field_evidence.jsonl").open("w", encoding="utf-8") as f:
        for item in evidence:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    browser.write_sqlite(out / "carrefour_first_party.sqlite", rows, evidence)

    fields = [
        "gtin", "name", "brand", "image_url", "category_path", "price_eur", "unit_price_text", "availability",
        "legal_name", "ingredients", "allergens", "net_content", "storage_conditions", "preparation_instructions",
        "operator_address", "manufacturer_packer_importer", "mandatory_mentions", "nutriscore", "attributes",
    ]
    nutrition_fields = [
        "energy_kj", "calories_kcal", "fat_g", "saturates_g", "carbohydrate_g", "sugars_g", "fiber_g",
        "protein_g", "salt_g",
    ]
    report = {
        "retailer": "CARREFOUR",
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "source": "https://www.carrefour.es",
        "extractor_version": VERSION,
        "built_at": base.now_iso(),
        "classification_performed": "false",
        "counts": {
            "probe_requested": summary.get("counts", {}).get("requested", 0),
            "probe_usable_pages": summary.get("counts", {}).get("usable_pages", 0),
            "saved_html_pages": summary.get("counts", {}).get("saved_html_pages", 0),
            "extracted_products": len(rows),
            "nutrition_complete": sum(r.get("nutrition_status") == "DECLARED_COMPLETE" for r in rows),
            "nutrition_partial": sum(r.get("nutrition_status") == "DECLARED_PARTIAL" for r in rows),
            "nutrition_not_found": sum(r.get("nutrition_status") == "NOT_FOUND" for r in rows),
            "evidence_rows": len(evidence),
        },
        "coverage": {field: base.coverage(rows, field) for field in fields},
        "nutrition_field_coverage": {field: base.coverage(rows, field) for field in nutrition_fields},
        "sample": rows[:10],
        "declared_attribute_keys": sorted(ATTRIBUTE_LABELS),
        "provenance_note": (
            "Every populated field was parsed offline from HTML captured directly from a successful Carrefour product-page "
            "response in Playwright. Product characteristics are retained as raw declared attributes, not Rumbo classifications. "
            "No third-party field is copied into this dataset."
        ),
    }
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())