from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIX = BASE / "fixtures"
SAMPLE_SIZE = 300
MIN_OBSERVED = 60  # 33 OFF + 10 Tesseract + 12 PP-OCRv6 + 5 GENERIC, before wave2 neural persistence.


def load(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def main() -> int:
    structured = load("pilot_300_structured_resolved.json")
    declared = load("pilot_300_declared_label_evidence.json")
    generic = load("generic_fdc_accepted_mappings.json")

    declared_tesseract = {
        str(x["product_id"]) for x in declared if x.get("reader") == "Tesseract-screen"
    }
    declared_ppocr = {
        str(x["product_id"]) for x in declared if x.get("reader") == "PP-OCRv6"
    }
    declared_known = declared_tesseract | declared_ppocr
    declared_all = {str(x["product_id"]) for x in declared}
    if declared_known != declared_all:
        unknown = sorted(declared_all - declared_known)
        raise AssertionError(f"Unknown DECLARED reader for product_ids: {unknown}")

    groups = {
        "MATCHED_OFF": {str(x["product_id"]) for x in structured},
        "DECLARED_TESSERACT": declared_tesseract,
        "DECLARED_PP_OCRV6": declared_ppocr,
        "GENERIC_FDC": {str(x["product_id"]) for x in generic},
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

    report = {
        "sample_size": SAMPLE_SIZE,
        "nutrition_observed": len(all_ids),
        "nutrition_observed_rate": round(len(all_ids) / SAMPLE_SIZE, 4),
        "source_counts": {key: len(value) for key, value in groups.items()},
        "definition": "lower bound from persisted, non-overlapping evidence only",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report["nutrition_observed"] < MIN_OBSERVED:
        raise AssertionError(f"Observed nutrition coverage regressed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
