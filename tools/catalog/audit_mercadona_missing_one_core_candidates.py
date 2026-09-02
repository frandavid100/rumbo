from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

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
EXPECTED_CANDIDATES = 34


def _close(field: str, a: float, b: float) -> bool:
    a = float(a)
    b = float(b)
    tolerance = (
        max(5.0, 0.04 * max(abs(a), abs(b), 1.0))
        if field == "calories"
        else max(0.6, 0.10 * max(abs(a), abs(b), 1.0))
    )
    return abs(a - b) <= tolerance


def _engine_family(name: str) -> str | None:
    name = str(name or "").lower()
    if name.startswith("paddleocr"):
        return "paddleocr"
    if name.startswith("easyocr"):
        return "easyocr"
    return None


def _support_observations(
    row: dict[str, Any], *, field: str, basis: str
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for attempt_index, attempt in enumerate(row.get("attempts") or []):
        for engine_name, engine in (attempt.get("engines") or {}).items():
            family = _engine_family(str(engine_name))
            if family is None or engine.get("basis") != basis:
                continue
            nutrition = engine.get("nutrition") or {}
            value = nutrition.get(field)
            if value is None or not isinstance(value, (int, float)):
                continue
            observations.append(
                {
                    "attempt_index": attempt_index,
                    "engine": str(engine_name),
                    "engine_family": family,
                    "status": engine.get("status"),
                    "basis": basis,
                    "value": float(value),
                }
            )
    return observations


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
    if (
        basis not in {"100_g", "100_ml"}
        or families < 2
        or is_hard_conflict(ensemble)
        or has_energy_mismatch(ensemble)
    ):
        return None

    missing_field = next(field for field in CORE_FIELDS if nutrition.get(field) is None)
    support = _support_observations(row, field=missing_field, basis=basis)
    if not support:
        return None

    first_value = support[0]["value"]
    if any(not _close(missing_field, first_value, item["value"]) for item in support[1:]):
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
        "candidate_universe": len(candidates),
        "candidate_policy": (
            "stable original+replay REVIEW + exactly 3 fused core values + explicit 100g/100ml basis "
            "+ >=2 OCR families + no OCR hard conflict + no energy/macro mismatch + the missing core "
            "field already observed by a non-Tesseract OCR family on the same basis"
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
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
