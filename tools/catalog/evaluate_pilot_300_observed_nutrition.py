from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIX = BASE / "fixtures"
SAMPLE_SIZE = 300


def load(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def main() -> int:
    structured = load("pilot_300_structured_resolved.json")
    declared = load("pilot_300_declared_label_evidence.json")
    generic = load("generic_fdc_accepted_mappings.json")

    groups = {
        "MATCHED_STRUCTURED": {str(x["product_id"]) for x in structured},
        "DECLARED_LABEL": {str(x["product_id"]) for x in declared},
        "GENERIC_ACCEPTED": {str(x["product_id"]) for x in generic},
    }
    all_ids = set().union(*groups.values())
    total_entries = sum(len(x) for x in groups.values())
    if len(all_ids) != total_entries:
        overlaps = []
        names = list(groups)
        for i, left in enumerate(names):
            for right in names[i + 1:]:
                common = sorted(groups[left] & groups[right])
                if common:
                    overlaps.append({"left": left, "right": right, "product_ids": common})
        raise AssertionError(f"Evidence groups overlap: {overlaps}")

    # These counts are the evidence actually observed and persisted for the
    # deterministic 300-product pilot. They are a lower bound, not an
    # extrapolation to products that have not gone through the expensive stages.
    report = {
        "sample_size": SAMPLE_SIZE,
        "nutrition_observed": len(all_ids),
        "nutrition_observed_rate": round(len(all_ids) / SAMPLE_SIZE, 4),
        "source_counts": {key: len(value) for key, value in groups.items()},
        "definition": "lower bound from persisted, non-overlapping evidence only",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # Regression floor: 33 OFF + 18 label + 5 explicitly accepted GENERIC.
    if report["nutrition_observed"] < 56:
        raise AssertionError(f"Observed nutrition coverage regressed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
