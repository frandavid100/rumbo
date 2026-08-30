#!/usr/bin/env python3
"""Merge and conservatively audit one Mercadona non-p9 OCR wave.

This keeps alternative-view OCR separate from the historical perspective=9
baseline. A row can only be staged as a safe promotion when its OCR ensemble is
DECLARED with all four core macros corroborated by at least two independent OCR
families and it does not conflict with any partial p9 evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import glob
import json
from pathlib import Path
import sqlite3

FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")
EXPECTED_ELIGIBLE = {"1": 1034, "2": 1367, "3": 122, "10": 51}
EXPECTED_BASELINE = 2459
PERSPECTIVES = ("1", "2", "3", "10")


def close(field: str, a: float, b: float) -> bool:
    a = float(a)
    b = float(b)
    if field == "calories":
        tolerance = max(5.0, 0.04 * max(abs(a), abs(b), 1.0))
    else:
        tolerance = max(0.6, 0.10 * max(abs(a), abs(b), 1.0))
    return abs(a - b) <= tolerance


def expected_sample_count(eligible: int, skip_first: int, limit: int) -> int:
    """Return the bounded sample size after deterministically skipping a prefix."""
    remaining = max(0, eligible - skip_first)
    return min(limit, remaining)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="input")
    parser.add_argument("--out", default="merged")
    parser.add_argument("--skip-first", type=int, required=True)
    parser.add_argument("--limit", type=int, required=True)
    parser.add_argument("--previous-completed", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input)
    out = Path(args.out)

    rows = []
    summaries = []
    for path in sorted(glob.glob(str(input_dir / "results-*.jsonl"))):
        rows.extend(
            json.loads(line)
            for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    for path in sorted(glob.glob(str(input_dir / "summary-*.json"))):
        summaries.append(json.loads(Path(path).read_text(encoding="utf-8")))

    observed_eligible = {
        str(s.get("required_perspective")): int(s.get("eligible_products", -1))
        for s in summaries
    }
    observed_baselines = {
        int(s.get("baseline_still_review_products", -1)) for s in summaries
    }
    observed_skip_first = {int(s.get("skip_first", -1)) for s in summaries}
    by_perspective = Counter(str(row.get("perspective")) for row in rows)
    statuses = Counter(str(row.get("status") or "UNKNOWN") for row in rows)
    keys = [
        (str(row.get("product_id") or ""), str(row.get("perspective")))
        for row in rows
    ]
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)

    provenance_errors = []
    baseline_errors = []
    invalid_declared = []
    p9_conflicts = []
    safe_promotions = []

    for row in rows:
        pid = str(row.get("product_id") or "")
        perspective = str(row.get("perspective"))
        if (
            row.get("evidence_level") != "OCR_DERIVED_FROM_MERCADONA_IMAGE"
            or row.get("source") != "MERCADONA_FIRST_PARTY"
            or row.get("source_record_kind") != "label image"
            or row.get("redistribution_allowed") is not False
            or perspective == "9"
            or perspective != str(row.get("required_perspective"))
        ):
            provenance_errors.append(f"{pid}:p{perspective}")

        if row.get("p9_baseline_status") != "REVIEW" or row.get("p9_replay_status") != "REVIEW":
            baseline_errors.append(f"{pid}:p{perspective}")

        if row.get("status") != "DECLARED":
            continue

        accepted = next(
            (
                attempt
                for attempt in row.get("attempts") or []
                if (attempt.get("ensemble") or {}).get("status") == "DECLARED"
            ),
            None,
        )
        ensemble = (accepted or {}).get("ensemble") or {}
        nutrition = row.get("nutrition") or {}
        if (
            int(ensemble.get("independent_engine_families") or 0) < 2
            or int(ensemble.get("corroborated_fields") or 0) < 4
            or any(nutrition.get(field) is None for field in FIELDS)
        ):
            invalid_declared.append(f"{pid}:p{perspective}")
            continue

        conflicts = []
        old_basis = row.get("p9_replay_basis")
        new_basis = row.get("basis")
        if old_basis and new_basis and old_basis != new_basis:
            conflicts.append(f"basis:{old_basis}!={new_basis}")
        old_nutrition = row.get("p9_replay_nutrition") or {}
        for field in FIELDS:
            old_value = old_nutrition.get(field)
            new_value = nutrition.get(field)
            if old_value is not None and new_value is not None and not close(field, old_value, new_value):
                conflicts.append(f"{field}:{old_value}!~{new_value}")

        if conflicts:
            p9_conflicts.append(
                {
                    "product_id": pid,
                    "perspective": perspective,
                    "conflicts": conflicts,
                    "p9_replay_basis": old_basis,
                    "p9_replay_nutrition": old_nutrition,
                    "alternative_basis": new_basis,
                    "alternative_nutrition": nutrition,
                }
            )
            continue

        safe_promotions.append(
            {
                "product_id": pid,
                "ean": row.get("ean"),
                "name": row.get("name"),
                "alternative_perspective": perspective,
                "basis": new_basis,
                "nutrition": nutrition,
                "independent_engine_families": ensemble.get("independent_engine_families"),
                "corroborated_fields": ensemble.get("corroborated_fields"),
                "source": "MERCADONA_FIRST_PARTY/label image",
                "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
                "redistribution_allowed": False,
            }
        )

    promotion_values = defaultdict(list)
    for promo in safe_promotions:
        promotion_values[promo["product_id"]].append(promo)

    cross_alt_conflicts = []
    for pid, observations in promotion_values.items():
        if len(observations) < 2:
            continue
        first = observations[0]
        for other in observations[1:]:
            bad = []
            if first.get("basis") != other.get("basis"):
                bad.append("basis")
            for field in FIELDS:
                if not close(field, first["nutrition"][field], other["nutrition"][field]):
                    bad.append(field)
            if bad:
                cross_alt_conflicts.append({"product_id": pid, "fields": bad})

    conflicted_ids = {item["product_id"] for item in cross_alt_conflicts}
    safe_promotions = [p for p in safe_promotions if p["product_id"] not in conflicted_ids]
    safe_product_ids = sorted({p["product_id"] for p in safe_promotions})

    start = args.skip_first + 1
    end = args.skip_first + args.limit
    expected_by_perspective = {
        perspective: expected_sample_count(
            EXPECTED_ELIGIBLE[perspective], args.skip_first, args.limit
        )
        for perspective in PERSPECTIVES
    }
    summary = {
        "inventory_products": 4280,
        "baseline_p9_still_review_products": EXPECTED_BASELINE,
        "pilot": "official alternative views for products that remain REVIEW in both original p9 OCR and current safe replay",
        "sample_order": f"SHA256_PRODUCT_ID_EAN; positions {start}-{end} independently per perspective stratum; positions {args.previous_completed} completed previously",
        "perspectives": list(PERSPECTIVES),
        "expected_eligible_by_perspective": EXPECTED_ELIGIBLE,
        "observed_eligible_by_perspective": observed_eligible,
        "expected_processed_by_perspective": expected_by_perspective,
        "processed": len(rows),
        "distinct_products_processed": len({str(row.get("product_id") or "") for row in rows}),
        "processed_by_perspective": dict(sorted(by_perspective.items())),
        "status_counts": dict(sorted(statuses.items())),
        "raw_alternative_DECLARED": statuses.get("DECLARED", 0),
        "safe_new_promotion_observations": len(safe_promotions),
        "safe_new_promotion_products": len(safe_product_ids),
        "safe_new_promotion_product_ids": safe_product_ids,
        "p9_partial_conflicts": p9_conflicts,
        "cross_alternative_conflicts": cross_alt_conflicts,
        "duplicate_product_perspective_keys": duplicates,
        "provenance_errors": provenance_errors,
        "baseline_membership_errors": baseline_errors,
        "invalid_declared": invalid_declared,
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "source": "MERCADONA_FIRST_PARTY/label image",
        "redistribution_allowed": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }

    out.mkdir(parents=True, exist_ok=True)
    (out / "results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (out / "safe-promotions.json").write_text(
        json.dumps(safe_promotions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    db = sqlite3.connect(out / "staging.sqlite")
    try:
        db.execute(
            "CREATE TABLE ocr_result (product_id TEXT NOT NULL, perspective TEXT NOT NULL, status TEXT NOT NULL, calories REAL, protein_g REAL, carbohydrate_g REAL, fat_g REAL, evidence_level TEXT NOT NULL, source TEXT NOT NULL, redistribution_allowed INTEGER NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(product_id, perspective))"
        )
        for row in rows:
            nutrition = row.get("nutrition") or {}
            db.execute(
                "INSERT INTO ocr_result VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(row.get("product_id") or ""),
                    str(row.get("perspective")),
                    row.get("status"),
                    nutrition.get("calories"),
                    nutrition.get("protein_g"),
                    nutrition.get("carbohydrate_g"),
                    nutrition.get("fat_g"),
                    row.get("evidence_level"),
                    row.get("source"),
                    0,
                    json.dumps(row, ensure_ascii=False, sort_keys=True),
                ),
            )
        db.commit()
    finally:
        db.close()

    print("P9_ALTERNATIVE_WAVE_SUMMARY=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))

    expected_total = sum(expected_by_perspective.values())
    failures = []
    if observed_eligible != EXPECTED_ELIGIBLE:
        failures.append(f"eligible census mismatch: {observed_eligible}")
    if observed_baselines != {EXPECTED_BASELINE}:
        failures.append(f"baseline count mismatch: {observed_baselines}")
    if observed_skip_first != {args.skip_first}:
        failures.append(f"skip-first mismatch: {observed_skip_first}")
    if len(rows) != expected_total:
        failures.append(f"processed {len(rows)} != {expected_total}")
    if any(by_perspective.get(p, 0) != expected_by_perspective[p] for p in PERSPECTIVES):
        failures.append(
            f"perspective sample mismatch: observed={by_perspective} expected={expected_by_perspective}"
        )
    if duplicates:
        failures.append("duplicate product/perspective keys")
    if provenance_errors:
        failures.append("provenance/perspective errors")
    if baseline_errors:
        failures.append("non-REVIEW baseline rows entered pilot")
    if invalid_declared:
        failures.append("unsafe raw DECLARED rows")
    if statuses.get("ERROR", 0):
        failures.append("product-level OCR errors")
    if cross_alt_conflicts:
        failures.append("conflicting DECLARED alternative views")
    if failures:
        raise SystemExit("; ".join(failures))


if __name__ == "__main__":
    main()
