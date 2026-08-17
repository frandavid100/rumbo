from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIX = BASE / "fixtures"
SAMPLE_SIZE = 300
MIN_OBSERVED = 80  # 33 OFF + 10 Tesseract + 32 PP-OCRv6 + 5 GENERIC.
DECLARED_PATTERN = "pilot_300_declared_label_evidence*.json"


def load(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def load_declared_evidence() -> tuple[list[dict], list[str]]:
    files = sorted(FIX.glob(DECLARED_PATTERN))
    if not files:
        raise AssertionError(f"No DECLARED evidence files matching {DECLARED_PATTERN}")
    rows: list[dict] = []
    for path in files:
        rows.extend(json.loads(path.read_text(encoding="utf-8")))
    return rows, [path.name for path in files]


def main() -> int:
    structured = load("pilot_300_structured_resolved.json")
    declared, declared_files = load_declared_evidence()
    generic = load("generic_fdc_accepted_mappings.json")

    declared_id_list = [str(x["product_id"]) for x in declared]
    duplicate_declared = sorted(
        product_id for product_id, count in Counter(declared_id_list).items() if count > 1
    )
    if duplicate_declared:
        raise AssertionError(f"Duplicate DECLARED product_ids: {duplicate_declared}")

    wrong_levels = sorted(
        str(x["product_id"]) for x in declared if x.get("evidence_level") != "DECLARED"
    )
    if wrong_levels:
        raise AssertionError(f"Non-DECLARED rows in DECLARED evidence: {wrong_levels}")

    declared_tesseract = {
        str(x["product_id"]) for x in declared if x.get("reader") == "Tesseract-screen"
    }
    declared_ppocr = {
        str(x["product_id"]) for x in declared if x.get("reader") == "PP-OCRv6"
    }
    declared_known = declared_tesseract | declared_ppocr
    declared_all = set(declared_id_list)
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
        "nutritionally_usable": len(all_ids),
        "nutrition_observed_rate": round(len(all_ids) / SAMPLE_SIZE, 4),
        "source_counts": {key: len(value) for key, value in groups.items()},
        "declared_evidence_files": declared_files,
        "definition": "lower bound from persisted, non-overlapping evidence only",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report["nutrition_observed"] < MIN_OBSERVED:
        raise AssertionError(f"Observed nutrition coverage regressed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
