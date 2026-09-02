from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
from typing import Any

from merge_mercadona_p9_alternative_wave import close, discover_input_paths

FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")
EXPECTED_ELIGIBLE = {"4": 2, "7": 2}
EXPECTED_BASELINE = 2459


def _accepted_ensemble(row: dict[str, Any]) -> dict[str, Any]:
    for attempt in row.get("attempts") or []:
        ensemble = attempt.get("ensemble") or {}
        if ensemble.get("status") == "DECLARED":
            return ensemble
    return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    input_dir = Path(args.input)
    out = Path(args.out)
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for path in discover_input_paths(input_dir, "results-*.jsonl"):
        rows.extend(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    for path in discover_input_paths(input_dir, "summary-*.json"):
        summaries.append(json.loads(path.read_text(encoding="utf-8")))

    observed_eligible = {
        str(summary.get("required_perspective")): int(summary.get("eligible_products", -1))
        for summary in summaries
    }
    census_errors = [
        f"p{perspective}:{observed_eligible.get(perspective)}!={expected}"
        for perspective, expected in EXPECTED_ELIGIBLE.items()
        if observed_eligible.get(perspective) != expected
    ]
    baseline_counts = {
        int(summary.get("baseline_still_review_products", -1)) for summary in summaries
    }
    baseline_summary_errors = [] if baseline_counts == {EXPECTED_BASELINE} else [
        f"baseline summaries={sorted(baseline_counts)} expected={EXPECTED_BASELINE}"
    ]

    keys = [
        (str(row.get("product_id") or ""), str(row.get("perspective") or ""))
        for row in rows
    ]
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    status_counts = Counter(str(row.get("status") or "UNKNOWN") for row in rows)
    processed_by_perspective = Counter(str(row.get("perspective") or "") for row in rows)
    expected_processed = EXPECTED_ELIGIBLE
    coverage_errors = [
        f"p{perspective}:{processed_by_perspective.get(perspective, 0)}!={expected}"
        for perspective, expected in expected_processed.items()
        if processed_by_perspective.get(perspective, 0) != expected
    ]

    provenance_errors: list[str] = []
    baseline_membership_errors: list[str] = []
    invalid_declared: list[str] = []
    p9_conflicts: list[dict[str, Any]] = []
    promotion_observations: list[dict[str, Any]] = []

    for row in rows:
        pid = str(row.get("product_id") or "")
        perspective = str(row.get("perspective") or "")
        key = f"{pid}:p{perspective}"
        if (
            perspective not in EXPECTED_ELIGIBLE
            or str(row.get("required_perspective")) != perspective
            or row.get("evidence_level") != "OCR_DERIVED_FROM_MERCADONA_IMAGE"
            or row.get("source") != "MERCADONA_FIRST_PARTY"
            or row.get("source_record_kind") != "label image"
            or row.get("redistribution_allowed") is not False
        ):
            provenance_errors.append(key)
        if row.get("p9_baseline_status") != "REVIEW" or row.get("p9_replay_status") != "REVIEW":
            baseline_membership_errors.append(key)
        if row.get("status") != "DECLARED":
            continue

        ensemble = _accepted_ensemble(row)
        nutrition = row.get("nutrition") or {}
        if (
            int(ensemble.get("independent_engine_families") or 0) < 2
            or int(ensemble.get("corroborated_fields") or 0) < 4
            or any(nutrition.get(field) is None for field in FIELDS)
        ):
            invalid_declared.append(key)
            continue

        conflicts: list[str] = []
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
            p9_conflicts.append({"product_id": pid, "perspective": perspective, "conflicts": conflicts})
            continue

        promotion_observations.append(
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

    by_product: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in promotion_observations:
        by_product[observation["product_id"]].append(observation)
    cross_alternative_conflicts: list[dict[str, Any]] = []
    for pid, observations in by_product.items():
        if len(observations) < 2:
            continue
        reference = observations[0]
        for other in observations[1:]:
            fields = []
            if reference.get("basis") != other.get("basis"):
                fields.append("basis")
            for field in FIELDS:
                if not close(field, reference["nutrition"][field], other["nutrition"][field]):
                    fields.append(field)
            if fields:
                cross_alternative_conflicts.append({"product_id": pid, "fields": fields})

    conflicted_ids = {item["product_id"] for item in cross_alternative_conflicts}
    safe_promotions = [
        observation
        for observation in promotion_observations
        if observation["product_id"] not in conflicted_ids
    ]
    safe_product_ids = sorted({item["product_id"] for item in safe_promotions})

    audit_errors = (
        census_errors
        + baseline_summary_errors
        + coverage_errors
        + [f"duplicate:{pid}:p{perspective}" for pid, perspective in duplicates]
        + [f"provenance:{value}" for value in provenance_errors]
        + [f"baseline:{value}" for value in baseline_membership_errors]
        + [f"invalid_declared:{value}" for value in invalid_declared]
    )

    summary = {
        "inventory_products": 4280,
        "baseline_p9_still_review_products": EXPECTED_BASELINE,
        "perspectives": ["4", "7"],
        "expected_eligible_by_perspective": EXPECTED_ELIGIBLE,
        "observed_eligible_by_perspective": observed_eligible,
        "processed": len(rows),
        "distinct_products_processed": len({str(row.get("product_id") or "") for row in rows}),
        "processed_by_perspective": dict(sorted(processed_by_perspective.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "safe_new_promotion_observations": len(safe_promotions),
        "safe_new_promotion_products": len(safe_product_ids),
        "safe_new_promotion_product_ids": safe_product_ids,
        "p9_partial_conflicts": p9_conflicts,
        "cross_alternative_conflicts": cross_alternative_conflicts,
        "audit_errors": audit_errors,
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
        json.dumps(safe_promotions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
                    str(row.get("perspective") or ""),
                    str(row.get("status") or "UNKNOWN"),
                    nutrition.get("calories"),
                    nutrition.get("protein_g"),
                    nutrition.get("carbohydrate_g"),
                    nutrition.get("fat_g"),
                    str(row.get("evidence_level") or ""),
                    str(row.get("source") or ""),
                    0,
                    json.dumps(row, ensure_ascii=False, sort_keys=True),
                ),
            )
        db.commit()
    finally:
        db.close()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 2 if audit_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
