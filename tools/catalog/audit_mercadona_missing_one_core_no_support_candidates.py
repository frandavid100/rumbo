from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_mercadona_missing_one_core_candidates import _support_observations
from audit_mercadona_p9_review_failure_modes import (
    CORE_FIELDS,
    EXPECTED_ROWS,
    EXPECTED_STILL_REVIEW,
    has_energy_mismatch,
    is_hard_conflict,
    load_jsonl,
    replay_ensemble,
)

AUDIT_POLICY_VERSION = "1.0.0"
EXPECTED_CANDIDATES = 33


def candidate_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("status") != "REVIEW" or (row.get("replay") or {}).get("status") != "REVIEW":
        return None

    replay = row.get("replay") or {}
    ensemble = replay_ensemble(row)
    nutrition = ensemble.get("nutrition") or replay.get("nutrition") or {}
    present = [field for field in CORE_FIELDS if nutrition.get(field) is not None]
    if len(present) != 3:
        return None

    basis = ensemble.get("basis") or replay.get("basis")
    families = int(ensemble.get("independent_engine_families") or 0)
    corroborated = int(ensemble.get("corroborated_fields") or 0)
    if (
        basis not in {"100_g", "100_ml"}
        or families < 2
        or corroborated != 3
        or is_hard_conflict(ensemble)
        or has_energy_mismatch(ensemble)
    ):
        return None

    missing_field = next(field for field in CORE_FIELDS if nutrition.get(field) is None)
    support = _support_observations(row, field=missing_field, basis=basis)
    if support:
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
        "missing_field_support": [],
        "corroborated_fields": corroborated,
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

    rows = load_jsonl(Path(args.replay_results))
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} replay rows, got {len(rows)}")

    stable_review_count = sum(
        row.get("status") == "REVIEW" and (row.get("replay") or {}).get("status") == "REVIEW"
        for row in rows
    )
    if stable_review_count != EXPECTED_STILL_REVIEW:
        raise ValueError(
            f"expected {EXPECTED_STILL_REVIEW} original+replay REVIEW rows, got {stable_review_count}"
        )

    candidates = [payload for row in rows if (payload := candidate_payload(row)) is not None]
    candidates.sort(key=lambda row: str(row["product_id"]))
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CANDIDATES} candidates, got {len(candidates)}")

    summary = {
        "audit_policy_version": AUDIT_POLICY_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "replay_rows": len(rows),
        "stable_original_and_replay_review_rows": stable_review_count,
        "candidate_universe": len(candidates),
        "candidate_policy": (
            "stable original+replay REVIEW + exactly 3 fused core values + explicit 100g/100ml basis "
            "+ >=2 OCR families + exactly 3 corroborated existing core fields + no OCR hard conflict "
            "+ no energy/macro mismatch + no prior non-Tesseract same-basis observation for the missing field; "
            "final promotion still requires a fully corroborated coherent DECLARED tuple"
        ),
        "missing_core_field_counts": {
            field: sum(row["missing_core_field"] == field for row in candidates)
            for field in CORE_FIELDS
            if any(row["missing_core_field"] == field for row in candidates)
        },
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
    (out / "missing-one-core-no-support.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in candidates),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
