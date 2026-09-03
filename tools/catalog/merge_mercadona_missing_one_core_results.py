from __future__ import annotations

import argparse
from collections import Counter
import glob
import json
from pathlib import Path
import shutil
from typing import Any

FIELDS = ("calories", "protein_g", "carbohydrate_g", "fat_g")
ALLOWED_STATUSES = {"DECLARED", "REVIEW", "NO_VISUAL_REGION", "ERROR"}


def close(field: str, a: float, b: float) -> bool:
    a, b = float(a), float(b)
    tolerance = (
        max(5.0, 0.04 * max(abs(a), abs(b), 1.0))
        if field == "calories"
        else max(0.6, 0.10 * max(abs(a), abs(b), 1.0))
    )
    return abs(a - b) <= tolerance


def energy_coherent(nutrition: dict[str, Any]) -> bool:
    if any(not isinstance(nutrition.get(field), (int, float)) for field in FIELDS):
        return False
    calories = float(nutrition["calories"])
    protein = float(nutrition["protein_g"])
    carbohydrate = float(nutrition["carbohydrate_g"])
    fat = float(nutrition["fat_g"])
    if not (
        0 <= calories <= 1000
        and 0 <= protein <= 100
        and 0 <= carbohydrate <= 100
        and 0 <= fat <= 100
    ):
        return False
    estimated = 9 * fat + 4 * carbohydrate + 4 * protein
    tolerance = max(8.0, calories * 0.10)
    return abs(estimated - calories) <= tolerance


def _accepted_declared_ensemble(row: dict[str, Any]) -> dict[str, Any]:
    return next(
        (
            (attempt.get("ensemble") or {})
            for attempt in (row.get("attempts") or [])
            if (attempt.get("ensemble") or {}).get("status") == "DECLARED"
        ),
        {},
    )


def merge(
    *,
    result_paths: list[Path],
    selection_paths: list[Path],
    baseline_path: Path,
    out: Path,
    expected_universe: int,
    expected_selected: int,
) -> dict[str, Any]:
    if not result_paths:
        raise ValueError("no result files")
    if not selection_paths:
        raise ValueError("no selection manifests")

    rows: list[dict[str, Any]] = []
    for path in result_paths:
        rows.extend(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    selections = [json.loads(path.read_text(encoding="utf-8")) for path in selection_paths]
    selection = selections[0]
    if any(candidate != selection for candidate in selections[1:]):
        raise ValueError("shard selection manifests disagree")
    expected_ids = set(map(str, selection.get("product_ids") or []))
    if len(expected_ids) != expected_selected:
        raise ValueError(
            f"selection mismatch expected={expected_selected} got={len(expected_ids)}"
        )

    all_baseline = {
        str(row["product_id"]): row
        for row in (
            json.loads(line)
            for line in baseline_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    if len(all_baseline) != expected_universe:
        raise ValueError(
            f"baseline universe mismatch expected={expected_universe} got={len(all_baseline)}"
        )
    baseline = {pid: all_baseline[pid] for pid in expected_ids if pid in all_baseline}
    if len(baseline) != expected_selected:
        raise ValueError(
            f"selected baseline mismatch expected={expected_selected} got={len(baseline)}"
        )

    counts = Counter(str(row.get("status") or "UNKNOWN") for row in rows)
    ids = [str(row.get("product_id") or "") for row in rows]
    observed_ids = set(ids)
    duplicate_ids = sorted(pid for pid, count in Counter(ids).items() if count > 1)
    missing_ids = sorted(expected_ids - observed_ids)
    unexpected_ids = sorted(observed_ids - expected_ids)
    unexpected_statuses = sorted(set(counts) - ALLOWED_STATUSES)

    provenance_errors: list[str] = []
    unsafe_declared: list[dict[str, Any]] = []
    rejected_declared: list[dict[str, Any]] = []
    prior_support_disagreements: list[dict[str, Any]] = []
    safe_promotions: list[dict[str, Any]] = []

    for row in rows:
        pid = str(row.get("product_id") or "")
        prior = baseline.get(pid)
        if prior is None:
            provenance_errors.append(f"{pid}:not_in_baseline")
            continue
        provenance_bad = (
            row.get("evidence_level") != "OCR_DERIVED_FROM_MERCADONA_IMAGE"
            or row.get("source") != "MERCADONA_FIRST_PARTY"
            or row.get("source_record_kind") != "label image"
            or row.get("redistribution_allowed") is not False
            or str(row.get("perspective")) != "9"
        )
        if provenance_bad:
            provenance_errors.append(f"{pid}:provenance")
            continue

        if row.get("status") != "DECLARED":
            continue

        ensemble = _accepted_declared_ensemble(row)
        nutrition = row.get("nutrition") or {}
        if (
            int(ensemble.get("independent_engine_families") or 0) < 2
            or int(ensemble.get("corroborated_fields") or 0) < 4
            or any(nutrition.get(field) is None for field in FIELDS)
            or row.get("basis") not in {"100_g", "100_ml"}
            or not energy_coherent(nutrition)
        ):
            unsafe_declared.append(
                {"product_id": pid, "reason": "final_declared_contract"}
            )
            continue

        missing_field = str(prior.get("missing_core_field") or "")
        prior_nutrition = prior.get("nutrition") or {}
        conflicts: list[str] = []
        if missing_field not in FIELDS or prior_nutrition.get(missing_field) is not None:
            conflicts.append("baseline_missing_field_shape")
        if row.get("basis") != prior.get("basis"):
            conflicts.append(f"basis:{prior.get('basis')}!={row.get('basis')}")
        for field in FIELDS:
            if field == missing_field:
                continue
            prior_value = prior_nutrition.get(field)
            if prior_value is None or not close(field, nutrition[field], prior_value):
                conflicts.append(f"{field}:{prior_value}!~{nutrition[field]}")
        if conflicts:
            rejected_declared.append({"product_id": pid, "conflicts": conflicts})
            continue

        supports = prior.get("missing_field_support") or []
        agreeing_supports = [
            support
            for support in supports
            if isinstance(support.get("value"), (int, float))
            and close(missing_field, nutrition[missing_field], support["value"])
        ]
        if supports and not agreeing_supports:
            prior_support_disagreements.append(
                {
                    "product_id": pid,
                    "field": missing_field,
                    "recovered_value": nutrition[missing_field],
                    "prior_support_values": [support.get("value") for support in supports],
                }
            )

        safe_promotions.append(
            {
                "product_id": pid,
                "ean": row.get("ean"),
                "name": row.get("name"),
                "basis": row.get("basis"),
                "nutrition": nutrition,
                "newly_recovered_field": missing_field,
                "preexisting_independent_support": supports,
                "prior_support_agrees": bool(agreeing_supports),
                "independent_engine_families": ensemble.get(
                    "independent_engine_families"
                ),
                "corroborated_fields": ensemble.get("corroborated_fields"),
                "source": "MERCADONA_FIRST_PARTY/label image",
                "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
                "redistribution_allowed": False,
            }
        )

    structural_ok = (
        len(rows) == expected_selected
        and len(observed_ids) == expected_selected
        and not duplicate_ids
        and not missing_ids
        and not unexpected_ids
        and not unexpected_statuses
        and not provenance_errors
        and not unsafe_declared
    )
    summary = {
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "candidate_universe": len(all_baseline),
        "selected": len(expected_ids),
        "processed": len(rows),
        "distinct_products_processed": len(observed_ids),
        "status_counts": dict(sorted(counts.items())),
        "safe_promotion_products": len(safe_promotions),
        "safe_promotion_product_ids": sorted(
            item["product_id"] for item in safe_promotions
        ),
        "rejected_declared": rejected_declared,
        "prior_missing_field_support_disagreements": prior_support_disagreements,
        "unsafe_declared": unsafe_declared,
        "duplicate_product_ids": duplicate_ids,
        "missing_product_ids": missing_ids,
        "unexpected_product_ids": unexpected_ids,
        "unexpected_statuses": unexpected_statuses,
        "provenance_errors": provenance_errors,
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
        "safety_assessment": "VALIDATED" if structural_ok else "FAILED",
    }

    out.mkdir(parents=True, exist_ok=True)
    (out / "results.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in sorted(rows, key=lambda row: str(row.get("product_id") or ""))
        ),
        encoding="utf-8",
    )
    (out / "safe-promotions.json").write_text(
        json.dumps(safe_promotions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "selection.json").write_text(
        json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy2(baseline_path, out / "candidate-universe.jsonl")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-glob", required=True)
    parser.add_argument("--selection-glob", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--expected-universe", type=int, required=True)
    parser.add_argument("--expected-selected", type=int, required=True)
    args = parser.parse_args()

    summary = merge(
        result_paths=[Path(path) for path in sorted(glob.glob(args.results_glob, recursive=True))],
        selection_paths=[
            Path(path) for path in sorted(glob.glob(args.selection_glob, recursive=True))
        ],
        baseline_path=Path(args.baseline),
        out=Path(args.out),
        expected_universe=args.expected_universe,
        expected_selected=args.expected_selected,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["safety_assessment"] != "VALIDATED":
        raise SystemExit("missing-one-core merge safety contract failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
