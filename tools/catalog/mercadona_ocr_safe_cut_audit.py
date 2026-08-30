from __future__ import annotations

"""Build a conservative cumulative Mercadona OCR safety audit.

This audit never downloads images and never runs OCR. It checks the stored OCR
text from the validated main and secondary cohorts against the current narrow
Mercadona row-order safety guard, verifies that the trusted main DECLARED set is
unaffected, proves the two cohorts are disjoint, and emits one cumulative cut.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from mercadona_nutrition_label_reader import read_nutrition_label

EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"
SOURCE = "MERCADONA_FIRST_PARTY/label image"
AMBIGUITY_PREFIX = "AMBIGUOUS_VALUE_BEFORE_LABEL:"


def _rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _id(row: dict[str, Any]) -> str:
    return str(row.get("product_id") or "")


def _ambiguity_hits(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for row in rows:
        reasons: set[str] = set()
        for attempt in row.get("attempts") or ():
            if not isinstance(attempt, dict):
                continue
            for payload in (attempt.get("engines") or {}).values():
                if not isinstance(payload, dict):
                    continue
                text = str(payload.get("normalized_ocr_text") or "")
                if not text:
                    continue
                parsed = read_nutrition_label(
                    text, extraction_confidence=float(payload.get("confidence") or 0.0)
                )
                reasons.update(
                    reason for reason in parsed.reasons if reason.startswith(AMBIGUITY_PREFIX)
                )
        if reasons:
            hits[_id(row)] = sorted(reasons)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--main-results", required=True)
    ap.add_argument("--secondary-safe-results", required=True)
    ap.add_argument("--promotion-audit", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    main_rows = _rows(Path(args.main_results))
    secondary_rows = _rows(Path(args.secondary_safe_results))
    promotion_doc = json.loads(Path(args.promotion_audit).read_text(encoding="utf-8"))

    if len(main_rows) != 2630:
        raise SystemExit(f"expected 2630 main rows, got {len(main_rows)}")
    if len(secondary_rows) != 121:
        raise SystemExit(f"expected 121 secondary rows, got {len(secondary_rows)}")

    main_ids = {_id(row) for row in main_rows}
    secondary_ids = {_id(row) for row in secondary_rows}
    overlap = sorted(main_ids & secondary_ids)
    if overlap:
        raise SystemExit(f"main/secondary cohorts overlap: {overlap[:20]}")

    old_main_counts = Counter(str(row.get("status") or "UNRESOLVED") for row in main_rows)
    if old_main_counts != Counter({"REVIEW": 2508, "DECLARED": 122}):
        raise SystemExit(f"unexpected main baseline counts: {old_main_counts}")

    promotion_ids = {
        str(pid)
        for pid in promotion_doc["independent_promotion_audit"]["includes_product_ids"]
    }
    if len(promotion_ids) != 8 or promotion_doc["independent_promotion_audit"]["safe_promotions"] != 8:
        raise SystemExit("trusted promotion audit is not the expected 8/8 safe cut")
    if not promotion_ids <= main_ids:
        raise SystemExit(f"promotion ids missing from main cohort: {sorted(promotion_ids - main_ids)}")

    original_declared_ids = {_id(row) for row in main_rows if row.get("status") == "DECLARED"}
    if promotion_ids & original_declared_ids:
        raise SystemExit("promotion IDs unexpectedly overlap original DECLARED set")
    trusted_main_declared_ids = original_declared_ids | promotion_ids
    if len(trusted_main_declared_ids) != 130:
        raise SystemExit(f"trusted main DECLARED cardinality is {len(trusted_main_declared_ids)}, expected 130")

    ambiguity_hits = _ambiguity_hits(main_rows)
    ambiguity_ids = set(ambiguity_hits)
    unsafe_trusted = sorted(ambiguity_ids & trusted_main_declared_ids)
    if unsafe_trusted:
        raise SystemExit(f"row-order ambiguity touches trusted DECLARED IDs: {unsafe_trusted}")

    secondary_counts = Counter()
    secondary_declared: list[dict[str, Any]] = []
    for row in secondary_rows:
        replay = row.get("replay") or {}
        status = str(replay.get("status") or "UNRESOLVED")
        secondary_counts[status] += 1
        if status == "DECLARED":
            secondary_declared.append({
                "product_id": _id(row),
                "ean": row.get("ean"),
                "name": row.get("name"),
                "nutrition": replay.get("nutrition"),
                "basis": replay.get("basis"),
            })
    if secondary_counts != Counter({"REVIEW": 118, "DECLARED": 3}):
        raise SystemExit(f"unexpected secondary safe counts: {secondary_counts}")

    cumulative_processed = len(main_rows) + len(secondary_rows)
    cumulative_declared = len(trusted_main_declared_ids) + secondary_counts["DECLARED"]
    cumulative_review = (len(main_rows) - len(trusted_main_declared_ids)) + secondary_counts["REVIEW"]
    if cumulative_processed != 2751 or cumulative_declared != 133 or cumulative_review != 2618:
        raise SystemExit("cumulative arithmetic invariant failed")

    out = {
        "kind": "MERCADONA_OCR_CUMULATIVE_SAFE_CUT_AUDIT",
        "date": "2026-08-30",
        "branch": "agent/catalog-phase1",
        "catalog_universe": 4280,
        "main_prioritized_cohort": {
            "processed": 2630,
            "trusted_DECLARED": 130,
            "REVIEW": 2500,
            "baseline_DECLARED": 122,
            "independently_audited_promotions": 8,
            "promotion_product_ids": sorted(promotion_ids),
            "row_order_ambiguity_hits": len(ambiguity_ids),
            "row_order_ambiguity_product_ids": sorted(ambiguity_ids),
            "ambiguity_hits_among_original_122_DECLARED": len(ambiguity_ids & original_declared_ids),
            "ambiguity_hits_among_8_promotions": len(ambiguity_ids & promotion_ids),
            "ambiguity_hits_among_trusted_130_DECLARED": len(unsafe_trusted),
        },
        "secondary_food_signal_cohort": {
            "processed": 121,
            "DECLARED": secondary_counts["DECLARED"],
            "REVIEW": secondary_counts["REVIEW"],
            "NO_VISUAL_REGION": 0,
            "ERROR": 0,
            "declared_products": sorted(secondary_declared, key=lambda row: row["product_id"]),
            "known_safety_demotion": {
                "product_id": "29130",
                "reason": "AMBIGUOUS_VALUE_BEFORE_LABEL:protein_g",
                "old_unsafe_protein_g": 0.01,
                "status": "REVIEW",
                "nutrition_usable": False,
            },
        },
        "cohort_disjointness": {
            "main_ids": len(main_ids),
            "secondary_ids": len(secondary_ids),
            "overlap": 0,
        },
        "cumulative_safe_cut": {
            "processed": cumulative_processed,
            "DECLARED": cumulative_declared,
            "REVIEW": cumulative_review,
            "NO_VISUAL_REGION": 0,
            "ERROR": 0,
            "macro_complete_DECLARED": cumulative_declared,
            "coverage_of_4280_percent": round(cumulative_declared / 4280 * 100, 4),
            "DECLARED_yield_of_processed_percent": round(cumulative_declared / cumulative_processed * 100, 4),
        },
        "provenance_invariants": {
            "evidence": EVIDENCE,
            "source": SOURCE,
            "redistribution_allowed": False,
            "images_persisted": False,
            "missing_values_inferred": False,
            "CLASSIFIED": 0,
            "MENU_ELIGIBLE": 0,
        },
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
