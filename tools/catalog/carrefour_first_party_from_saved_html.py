from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import carrefour_first_party_inventory as base
import carrefour_first_party_browser_inventory as browser

VERSION = "carrefour-first-party-saved-html-1.3"

# Product-specific labels observed on Carrefour product pages. Values are kept
# verbatim as Carrefour declarations; they are not Rumbo roles/classification.
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
    "lactose_free": ["Sin lactosa"],
    "halal": ["Halal"],
    "vegetarian": ["Vegetariano"],
    "conservation_mode": ["Modo conservación", "Modo conservacion"],
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
    "milk_type": ["Tipo de leche tratada"],
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

# Extra nutrients that Carrefour sometimes declares in addition to the EU core
# panel. They remain an open map so we do not have to widen the stable SQLite
# nutrition table for every micronutrient.
EXTRA_NUTRIENTS = {
    "monounsaturated_fat_g": (["Grasas monoinsaturadas", "Ácidos grasos monoinsaturados", "Acidos grasos monoinsaturados"], "g"),
    "polyunsaturated_fat_g": (["Grasas poliinsaturadas", "Ácidos grasos poliinsaturados", "Acidos grasos poliinsaturados"], "g"),
    "omega3_g": (["Omega 3", "Omega-3"], "g"),
    "omega6_g": (["Omega 6", "Omega-6"], "g"),
    "cholesterol_mg": (["Colesterol"], "mg"),
    "calcium_mg": (["Calcio"], "mg"),
    "phosphorus_mg": (["Fósforo", "Fosforo"], "mg"),
    "magnesium_mg": (["Magnesio"], "mg"),
    "iron_mg": (["Hierro"], "mg"),
    "zinc_mg": (["Zinc"], "mg"),
    "potassium_mg": (["Potasio"], "mg"),
    "sodium_mg": (["Sodio"], "mg"),
    "vitamin_a_ug": (["Vitamina A", "Vit. A"], "µg"),
    "vitamin_d_ug": (["Vitamina D", "Vit. D"], "µg"),
    "vitamin_e_mg": (["Vitamina E", "Vit. E"], "mg"),
    "vitamin_c_mg": (["Vitamina C", "Vit. C"], "mg"),
    "thiamin_mg": (["Tiamina", "Vitamina B1", "Vit. B1"], "mg"),
    "riboflavin_mg": (["Riboflavina", "Vitamina B2", "Vit. B2"], "mg"),
    "niacin_mg": (["Niacina", "Vitamina B3", "Vit. B3"], "mg"),
    "vitamin_b6_mg": (["Vitamina B6", "Vit. B6"], "mg"),
    "folic_acid_ug": (["Ácido fólico", "Acido folico", "Vitamina B9", "Vit. B9"], "µg"),
    "vitamin_b12_ug": (["Vitamina B12", "Vit. B12"], "µg"),
}


def nonempty(value):
    return value not in (None, "", [], {})


def normalized_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().rstrip(":")).casefold()


def exact_labelled_value(text: str, labels: list[str]):
    """Read a Carrefour label only when the whole line is that label.

    Carrefour renders many characteristics as an exact label line followed by a
    value line. Requiring an exact line avoids prefix corruption such as parsing
    ``Tipo de leche tratada / Entera`` as ``Tipo de leche -> tratada``.
    A same-line ``Label: value`` form is also accepted.
    """
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    targets = {normalized_label(label) for label in labels}
    for index, line in enumerate(lines):
        if not line:
            continue
        if normalized_label(line) in targets:
            for candidate in lines[index + 1:]:
                if candidate:
                    return candidate
            return None
        for label in labels:
            match = re.fullmatch(re.escape(label) + r"\s*:\s*(.+)", line, re.I)
            if match:
                return base.clean(match.group(1))
    return None


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


def parse_extra_nutrition(text: str) -> dict:
    nutrition = base.section(
        text,
        ["Información nutricional", "Informacion nutricional"],
        ["Ingredientes", "Alérgenos", "Alergenos", "Más información", "Mas informacion", "Datos del producto"],
    ) or ""
    result = {}
    for key, (labels, unit) in EXTRA_NUTRIENTS.items():
        for label in labels:
            unit_pattern = r"(?:µg|μg|ug|mcg)" if unit == "µg" else re.escape(unit)
            match = re.search(
                re.escape(label) + r"(?:\s*\([^)]*\))?\s*[:]?\s*(-?\d+(?:[.,]\d+)?)\s*" + unit_pattern + r"\b",
                nutrition,
                re.I,
            )
            if match:
                value = base.norm_number(match.group(1))
                if value is not None:
                    result[key] = value
                    break
    return result


def augment_declared_fields(row: dict, evidence: list[dict], text: str) -> None:
    attributes = dict(row.get("attributes") or {})
    # Drop the legacy generic page-chrome key before adding exact declarations.
    product_type = attributes.get("product_type")
    if product_type and re.search(r"vendidos?\s+por\s+terceros|marketplace", str(product_type), re.I):
        attributes.pop("product_type", None)
    for key, labels in ATTRIBUTE_LABELS.items():
        value = exact_labelled_value(text, labels)
        if nonempty(value):
            attributes[key] = value
    row["attributes"] = attributes
    replace_evidence(evidence, row, "attributes", attributes)

    if not row.get("mandatory_mentions"):
        row["mandatory_mentions"] = exact_labelled_value(text, MANDATORY_MENTION_LABELS)
    replace_evidence(evidence, row, "mandatory_mentions", row.get("mandatory_mentions"))

    extra = parse_extra_nutrition(text)
    row["nutrition_extra"] = extra
    replace_evidence(evidence, row, "nutrition_extra", extra)


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
        "nutrition_extra",
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
            "nutrition_extra_products": sum(bool(r.get("nutrition_extra")) for r in rows),
            "evidence_rows": len(evidence),
        },
        "coverage": {field: base.coverage(rows, field) for field in fields},
        "nutrition_field_coverage": {field: base.coverage(rows, field) for field in nutrition_fields},
        "sample": rows[:10],
        "declared_attribute_keys": sorted(ATTRIBUTE_LABELS),
        "declared_extra_nutrient_keys": sorted(EXTRA_NUTRIENTS),
        "provenance_note": (
            "Every populated field was parsed offline from HTML captured directly from a successful Carrefour product-page "
            "response in Playwright. Characteristics require exact Carrefour label lines and are retained as raw declarations, "
            "not Rumbo classifications. Extra micronutrients remain a declared open map. No third-party field is copied into this dataset."
        ),
    }
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())