from __future__ import annotations

import json
import os
from pathlib import Path

from fooddata_central_adapter import search_foods

BASE = Path(__file__).resolve().parent
PROPOSALS = BASE / "fixtures" / "generic_fdc_mapping_proposals.json"
OUT = BASE / "generic-fdc-proposals-output"


def main() -> int:
    api_key = os.environ.get("FDC_API_KEY", "DEMO_KEY")
    proposals = json.loads(PROPOSALS.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in proposals:
        row = dict(item)
        try:
            foods = search_foods(item["fdc_query"], api_key=api_key, page_size=8)
            row["candidates"] = [
                {
                    "fdcId": food.get("fdcId"),
                    "description": food.get("description"),
                    "dataType": food.get("dataType"),
                    "score": food.get("score"),
                }
                for food in foods
            ]
            row["status"] = "CANDIDATES_FOUND" if foods else "NO_CANDIDATE"
        except Exception as exc:
            row["status"] = "ERROR"
            row["error"] = f"{type(exc).__name__}:{exc}"
        rows.append(row)
        print(f"{item['product_id']} {row['status']}", flush=True)
    report = {"source":"USDA FoodData Central", "accepted_automatically":0, "items":rows}
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
