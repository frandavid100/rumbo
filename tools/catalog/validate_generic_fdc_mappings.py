from __future__ import annotations

import json
import os
from pathlib import Path

from fooddata_central_adapter import GenericMapping, fetch_food, to_generic_candidate
from mercadona_weekly_catalog_adapter import fetch_product
from nutrition_resolver import ProductIdentity

BASE = Path(__file__).resolve().parent
MAPPINGS = BASE / "fixtures" / "generic_fdc_accepted_mappings.json"
OUT = BASE / "generic-fdc-accepted-output"


def main() -> int:
    api_key = os.environ.get("FDC_API_KEY", "DEMO_KEY")
    mappings = json.loads(MAPPINGS.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in mappings:
        row = dict(item)
        try:
            product = fetch_product(item["product_id"])
            food = fetch_food(item["fdc_id"], api_key=api_key)
            mapping = GenericMapping(
                target_name=item["target_name"],
                fdc_id=item["fdc_id"],
                fdc_description=item["fdc_description"],
                rationale=item["rationale"],
            )
            candidate = to_generic_candidate(
                ProductIdentity(
                    name=product.name, brand=product.brand, gtin=product.ean,
                    ingredients=product.ingredients,
                ), mapping, food,
            )
            row.update({
                "status":"GENERIC_VALIDATED",
                "nutrition":candidate.nutrition,
                "evidence_level":candidate.evidence_level,
                "source":candidate.source,
                "source_record_id":candidate.source_record_id,
                "redistribution_allowed":candidate.redistribution_allowed,
                "upstream_license":candidate.upstream_license,
            })
        except Exception as exc:
            row["status"] = "ERROR"
            row["error"] = f"{type(exc).__name__}:{exc}"
        rows.append(row)
        print(f"{item['product_id']} {row['status']}", flush=True)
    ok = sum(r["status"] == "GENERIC_VALIDATED" for r in rows)
    report = {"mappings":len(rows), "validated":ok, "items":rows}
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if ok == len(rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
