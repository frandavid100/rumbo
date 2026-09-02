from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

CORE_FIELDS = ("calories", "protein_g", "carbohydrate_g", "fat_g")
EXPECTED_ROWS = 2630
EXPECTED_STILL_REVIEW = 2459


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def replay_ensemble(row: dict[str, Any]) -> dict[str, Any]:
    replay = row.get("replay") or {}
    ensembles = replay.get("attempt_ensembles") or []
    if not ensembles:
        return {}
    return max(
        ensembles,
        key=lambda ensemble: (
            int(ensemble.get("corroborated_fields") or 0),
            int(ensemble.get("independent_engine_families") or 0),
            float(ensemble.get("confidence") or 0.0),
        ),
    )


def is_hard_conflict(ensemble: dict[str, Any]) -> bool:
    return any(
        str(reason).startswith("OCR_FIELD_CONFLICT")
        or str(reason).startswith("OCR_SAME_ENGINE_CONFLICT")
        or str(reason) == "OCR_BASIS_CONFLICT"
        for reason in (ensemble.get("reasons") or [])
    )


def has_energy_mismatch(ensemble: dict[str, Any]) -> bool:
    return any(str(reason).startswith("ENERGY_MACRO_MISMATCH") for reason in (ensemble.get("reasons") or []))


def core_present(nutrition: dict[str, Any]) -> int:
    return sum(nutrition.get(field) is not None for field in CORE_FIELDS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-results", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows = load_jsonl(Path(args.replay_results))
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} replay rows, got {len(rows)}")

    reviews = [
        row
        for row in rows
        if row.get("status") == "REVIEW"
        and (row.get("replay") or {}).get("status") == "REVIEW"
    ]
    if len(reviews) != EXPECTED_STILL_REVIEW:
        raise ValueError(
            f"expected {EXPECTED_STILL_REVIEW} original+replay REVIEW rows, got {len(reviews)}"
        )

    field_coverage = Counter()
    corroboration = Counter()
    reason_counts = Counter()
    target_candidates: list[dict[str, Any]] = []
    lower_priority_candidates: list[dict[str, Any]] = []

    for row in reviews:
        replay = row.get("replay") or {}
        nutrition = replay.get("nutrition") or {}
        ensemble = replay_ensemble(row)
        present = core_present(nutrition)
        corroborated = int(ensemble.get("corroborated_fields") or 0)
        families = int(ensemble.get("independent_engine_families") or 0)
        field_coverage[present] += 1
        corroboration[(corroborated, families)] += 1
        for reason in ensemble.get("reasons") or []:
            reason_counts[str(reason).split(":", 1)[0]] += 1

        payload = {
            "product_id": str(row.get("product_id") or ""),
            "ean": row.get("ean"),
            "name": row.get("name"),
            "category_id": row.get("category_id"),
            "category_name": row.get("category_name"),
            "image_url": row.get("image_url"),
            "perspective": row.get("perspective"),
            "basis": ensemble.get("basis") or replay.get("basis"),
            "nutrition": ensemble.get("nutrition") or nutrition,
            "corroborated_fields": corroborated,
            "independent_engine_families": families,
            "reasons": ensemble.get("reasons") or [],
            "source": "MERCADONA_FIRST_PARTY/label image",
            "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
            "redistribution_allowed": False,
        }

        safe_shape = (
            present == 4
            and payload["basis"] in {"100_g", "100_ml"}
            and families >= 2
            and not is_hard_conflict(ensemble)
            and not has_energy_mismatch(ensemble)
        )
        if safe_shape and corroborated == 3:
            target_candidates.append(payload)
        elif safe_shape and corroborated == 2:
            lower_priority_candidates.append(payload)

    target_candidates.sort(key=lambda row: str(row["product_id"]))
    lower_priority_candidates.sort(key=lambda row: str(row["product_id"]))
    summary = {
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "replay_rows": len(rows),
        "stable_original_and_replay_review_rows": len(reviews),
        "core_field_coverage_counts": {str(k): v for k, v in sorted(field_coverage.items())},
        "corroboration_by_fields_and_families": {
            f"fields={fields};families={families}": count
            for (fields, families), count in sorted(corroboration.items())
        },
        "reason_prefix_counts": dict(sorted(reason_counts.items())),
        "priority_near_complete_candidates": len(target_candidates),
        "priority_policy": "stable original+replay REVIEW + 4 core values + explicit 100g/100ml basis + >=2 OCR families + exactly 3 corroborated core fields + no OCR hard conflict + no energy/macro mismatch",
        "secondary_two_field_candidates": len(lower_priority_candidates),
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "priority-near-complete.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in target_candidates),
        encoding="utf-8",
    )
    (out / "secondary-two-field.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in lower_priority_candidates),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
