from __future__ import annotations

import io
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from aesan_2022_match_probe import _float, digits
from mercadona_weekly_catalog_adapter import fetch_product as fetch_mercadona_product
from openfoodfacts_adapter import fetch_product as fetch_off_product, to_candidate as off_to_candidate

BASE = Path(__file__).resolve().parent
FIX = BASE / "fixtures"
OUT = BASE / "aesan-2022-current-evidence-output"


def fetch_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "RumboCatalogValidation/1.0"})
    with urlopen(req, timeout=90) as response:
        return response.read()


def core(values: dict) -> dict[str, float | None]:
    return {
        "kcal": values.get("calories"),
        "fat": values.get("fat_g"),
        "carb": values.get("carbohydrate_g"),
        "protein": values.get("protein_g"),
    }


def load_declared() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(FIX.glob("pilot_300_declared_label_evidence*.json")):
        rows.extend(json.loads(path.read_text(encoding="utf-8")))
    return rows


def classify_delta(current: dict, historical: dict) -> tuple[str, dict]:
    diffs = {k: abs(float(current[k]) - float(historical[k])) for k in current}
    rel = {}
    for k in current:
        denom = max(abs(float(current[k])), abs(float(historical[k])), 0.5)
        rel[k] = diffs[k] / denom

    # Diagnostic bands only; not a publication policy.
    if diffs["kcal"] <= 2 and all(diffs[k] <= 0.2 for k in ("fat", "carb", "protein")):
        band = "ROUNDING_EQUIVALENT"
    elif diffs["kcal"] <= 10 and all(diffs[k] <= 1.0 for k in ("fat", "carb", "protein")):
        band = "CLOSE"
    else:
        band = "MATERIAL_DIFFERENCE"
    return band, {"absolute": {k: round(v, 3) for k, v in diffs.items()},
                  "relative": {k: round(v, 4) for k, v in rel.items()}}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    url = os.environ["AESAN_2022_EXCEL_URL"]
    df = pd.read_excel(io.BytesIO(fetch_bytes(url)), sheet_name="DATOS", header=1)
    cols = {
        "gtin": "EAN",
        "name": "Nombre comercial",
        "brand": "Marca",
        "kcal": "Energía \n(kCal/ 100g ó 100 ml)",
        "fat": "Grasa total \n(g/ 100 g ó 100 ml)",
        "carb": "Hidratos de carbono \n(g/ 100g ó 100 ml)",
        "protein": "Proteínas \n(g/100 g ó 100 ml)",
    }
    for col in cols.values():
        if col not in df.columns:
            raise RuntimeError(f"AESAN DATOS schema changed: missing {col!r}")

    by_gtin: dict[str, list[dict]] = defaultdict(list)
    for _, row in df.iterrows():
        gtin = digits(row.get(cols["gtin"]))
        if len(gtin) < 8:
            continue
        nutrition = {k: _float(row.get(cols[k])) for k in ("kcal", "fat", "carb", "protein")}
        if any(v is None for v in nutrition.values()):
            continue
        by_gtin[gtin].append({
            "name": str(row.get(cols["name"]) or ""),
            "brand": str(row.get(cols["brand"]) or ""),
            "nutrition": nutrition,
        })

    structured = json.loads((FIX / "pilot_300_structured_resolved.json").read_text(encoding="utf-8"))
    declared = load_declared()
    generic = json.loads((FIX / "generic_fdc_accepted_mappings.json").read_text(encoding="utf-8"))

    current_rows: list[dict] = []
    source_errors: list[dict] = []

    # Product-specific current evidence from OFF: refetch exact GTIN so the comparison
    # uses the current structured record rather than a stale local copy.
    for row in structured:
        try:
            fetched = fetch_off_product(str(row["ean"]), timeout=12.0)
            candidate = off_to_candidate(fetched)
            if not candidate:
                source_errors.append({"product_id": row["product_id"], "source": "OFF", "error": "not_found_now"})
                continue
            values = core(candidate.nutrition)
            if any(v is None for v in values.values()):
                source_errors.append({"product_id": row["product_id"], "source": "OFF", "error": "core_nutrition_incomplete"})
                continue
            current_rows.append({
                "product_id": str(row["product_id"]), "name": row["name"], "ean": str(row["ean"]),
                "source": "MATCHED_OFF", "nutrition": values,
            })
        except Exception as exc:
            source_errors.append({"product_id": row["product_id"], "source": "OFF", "error": f"{type(exc).__name__}:{exc}"})

    # Product-specific current evidence from Mercadona labels.
    for row in declared:
        try:
            product = fetch_mercadona_product(str(row["product_id"]), timeout=20.0)
            if not product.ean:
                source_errors.append({"product_id": row["product_id"], "source": "DECLARED", "error": "current_ean_missing"})
                continue
            current_rows.append({
                "product_id": str(row["product_id"]), "name": row["name"], "ean": product.ean,
                "source": "DECLARED_" + ("TESSERACT" if row.get("reader") == "Tesseract-screen" else "PP_OCRV6"),
                "nutrition": core(row["nutrition"]),
            })
        except Exception as exc:
            source_errors.append({"product_id": row["product_id"], "source": "DECLARED", "error": f"{type(exc).__name__}:{exc}"})

    comparisons = []
    no_aesan_match = []
    for row in current_rows:
        candidates = by_gtin.get(digits(row["ean"]), [])
        if not candidates:
            no_aesan_match.append({k: row[k] for k in ("product_id", "name", "ean", "source")})
            continue
        # Exact EAN is the identity criterion. If AESAN has duplicated rows for the same
        # EAN, compare with all and keep the closest historical nutrition, while reporting
        # duplicate count explicitly.
        scored = []
        for h in candidates:
            band, delta = classify_delta(row["nutrition"], h["nutrition"])
            total = delta["absolute"]["kcal"] / 10 + sum(delta["absolute"][k] for k in ("fat", "carb", "protein"))
            scored.append((total, band, delta, h))
        scored.sort(key=lambda x: x[0])
        _, band, delta, h = scored[0]
        comparisons.append({
            "product_id": row["product_id"], "current_name": row["name"], "ean": row["ean"],
            "current_source": row["source"], "current_nutrition": row["nutrition"],
            "aesan_name": h["name"], "aesan_brand": h["brand"], "aesan_nutrition": h["nutrition"],
            "aesan_rows_same_ean": len(candidates), "band": band, "delta": delta,
        })

    counts = Counter(x["band"] for x in comparisons)
    source_counts = defaultdict(Counter)
    for x in comparisons:
        source_counts[x["current_source"]][x["band"]] += 1
        source_counts[x["current_source"]]["TOTAL"] += 1

    material = [x for x in comparisons if x["band"] == "MATERIAL_DIFFERENCE"]
    material.sort(key=lambda x: x["delta"]["absolute"]["kcal"] + 10 * sum(x["delta"]["absolute"][k] for k in ("fat", "carb", "protein")), reverse=True)

    report = {
        "comparison_version": "1.0.0",
        "aesan_source": "AESAN 2022 archived official workbook",
        "aesan_excel_url": url,
        "current_product_specific_evidence_expected": len(structured) + len(declared),
        "current_product_specific_evidence_loaded": len(current_rows),
        "generic_fdc_excluded_from_reformulation_test": len(generic),
        "generic_exclusion_reason": "GENERIC FDC is food-composition evidence, not a current commercial formulation of the same EAN",
        "exact_ean_comparisons": len(comparisons),
        "no_aesan_exact_ean": len(no_aesan_match),
        "bands": dict(counts),
        "bands_definition": {
            "ROUNDING_EQUIVALENT": "<=2 kcal and <=0.2 g difference in each macro",
            "CLOSE": "<=10 kcal and <=1.0 g difference in each macro",
            "MATERIAL_DIFFERENCE": "outside the above diagnostic bands",
            "note": "Diagnostic only; not an automatic acceptance policy",
        },
        "by_current_source": {k: dict(v) for k, v in source_counts.items()},
        "source_errors": source_errors,
        "comparisons": comparisons,
        "material_differences": material,
        "no_aesan_match": no_aesan_match,
    }
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("comparisons", "material_differences", "no_aesan_match")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
