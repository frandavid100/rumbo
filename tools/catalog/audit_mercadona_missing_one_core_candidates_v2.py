from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

import audit_mercadona_missing_one_core_candidates as base

AUDIT_POLICY_VERSION = "1.1.0"
EXPECTED_CANDIDATES = 28
CORE_FIELDS = base.CORE_FIELDS
ENERGY_FACTORS = {
    "protein_g": 4.0,
    "carbohydrate_g": 4.0,
    "fat_g": 9.0,
}


def _support_energy_plausible(
    *, field: str, value: float, nutrition: dict[str, Any]
) -> bool:
    """Reject a support observation if that macro alone exceeds labelled energy.

    This is deliberately one-sided and conservative. It does not try to infer
    energy from macros; it only rejects physically impossible support values,
    such as OCR reading an ingredient percentage as fat grams.
    """
    factor = ENERGY_FACTORS.get(field)
    calories = nutrition.get("calories")
    if factor is None or calories is None:
        return True
    calories = float(calories)
    contribution = factor * float(value)
    tolerance = max(10.0, 0.10 * max(abs(calories), 1.0))
    return contribution <= calories + tolerance


def candidate_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("status") != "REVIEW" or (row.get("replay") or {}).get("status") != "REVIEW":
        return None

    replay = row.get("replay") or {}
    ensemble = base.replay_ensemble(row)
    nutrition = ensemble.get("nutrition") or replay.get("nutrition") or {}
    present = [field for field in CORE_FIELDS if nutrition.get(field) is not None]
    if len(present) != 3:
        return None

    basis = ensemble.get("basis") or replay.get("basis")
    families = int(ensemble.get("independent_engine_families") or 0)
    if (
        basis not in {"100_g", "100_ml"}
        or families < 2
        or base.is_hard_conflict(ensemble)
        or base.has_energy_mismatch(ensemble)
    ):
        return None

    missing_field = next(field for field in CORE_FIELDS if nutrition.get(field) is None)
    raw_support = base._support_observations(row, field=missing_field, basis=basis)
    support = [
        item
        for item in raw_support
        if _support_energy_plausible(
            field=missing_field,
            value=item["value"],
            nutrition=nutrition,
        )
    ]
    if not support:
        return None

    first_value = support[0]["value"]
    if any(not base._close(missing_field, first_value, item["value"]) for item in support[1:]):
        return None

    return {
        "product_id": str(row.get("product_id") or ""),
        "ean": row.get("ean"),
        "name": row.get("name"),
        "category_id": row.get("category_id"),
        "category_name": row.get("category_name"),
        "image_url": row.get("image_url"),
        "perspective": row.get("perspective"),
        "basis": basis,
        "nutrition": {field: nutrition.get(field) for field in CORE_FIELDS},
        "missing_core_field": missing_field,
        "missing_field_support": support,
        "discarded_energy_impossible_support": [
            item for item in raw_support if item not in support
        ],
        "corroborated_fields": int(ensemble.get("corroborated_fields") or 0),
        "independent_engine_families": families,
        "reasons": ensemble.get("reasons") or [],
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-results", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows = base.load_jsonl(Path(args.replay_results))
    if len(rows) != base.EXPECTED_ROWS:
        raise ValueError(f"expected {base.EXPECTED_ROWS} replay rows, got {len(rows)}")

    stable_review_count = sum(
        row.get("status") == "REVIEW" and (row.get("replay") or {}).get("status") == "REVIEW"
        for row in rows
    )
    if stable_review_count != base.EXPECTED_STILL_REVIEW:
        raise ValueError(
            f"expected {base.EXPECTED_STILL_REVIEW} original+replay REVIEW rows, got {stable_review_count}"
        )

    old_candidates = [
        payload for row in rows if (payload := base.candidate_payload(row)) is not None
    ]
    candidates = [payload for row in rows if (payload := candidate_payload(row)) is not None]
    candidates.sort(key=lambda row: str(row["product_id"]))
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CANDIDATES} candidates, got {len(candidates)}")

    kept_ids = {row["product_id"] for row in candidates}
    rejected_energy_support = [
        row for row in old_candidates if row["product_id"] not in kept_ids
    ]
    if len(old_candidates) != base.EXPECTED_CANDIDATES or len(rejected_energy_support) != 6:
        raise ValueError(
            "missing-one-core v2 audit baseline drift: "
            f"old={len(old_candidates)} rejected_energy={len(rejected_energy_support)}"
        )

    missing_fields = Counter(str(row["missing_core_field"]) for row in candidates)
    support_families = Counter(
        family
        for row in candidates
        for family in {item["engine_family"] for item in row["missing_field_support"]}
    )
    summary = {
        "audit_policy_version": AUDIT_POLICY_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "replay_rows": len(rows),
        "stable_original_and_replay_review_rows": stable_review_count,
        "prior_candidate_universe": len(old_candidates),
        "rejected_by_support_energy_sanity": len(rejected_energy_support),
        "rejected_product_ids": sorted(row["product_id"] for row in rejected_energy_support),
        "candidate_universe": len(candidates),
        "candidate_policy": (
            "stable original+replay REVIEW + exactly 3 fused core values + explicit 100g/100ml basis "
            "+ >=2 OCR families + no OCR hard conflict + no energy/macro mismatch + missing core field "
            "observed by non-Tesseract OCR on the same basis + support macro alone cannot exceed labelled "
            "energy beyond conservative rounding tolerance"
        ),
        "missing_core_field_counts": dict(sorted(missing_fields.items())),
        "support_family_counts": dict(sorted(support_families.items())),
        "all_perspective_9": all(str(row.get("perspective")) == "9" for row in candidates),
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "missing-one-core-supported.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in candidates),
        encoding="utf-8",
    )
    (out / "rejected-energy-impossible-support.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in sorted(rejected_energy_support, key=lambda row: str(row["product_id"]))
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
