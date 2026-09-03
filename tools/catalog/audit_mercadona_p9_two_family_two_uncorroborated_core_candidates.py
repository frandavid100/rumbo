from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

CORE_FIELDS = ("calories", "protein_g", "carbohydrate_g", "fat_g")
EXPECTED_ROWS = 2630
EXPECTED_STILL_REVIEW = 2459
EXPECTED_CANDIDATES = 62
AUDIT_POLICY_VERSION = "1.0.0"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def replay_ensemble(row: dict[str, Any]) -> dict[str, Any]:
    ensembles = (row.get("replay") or {}).get("attempt_ensembles") or []
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


def candidate_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    replay = row.get("replay") or {}
    if row.get("status") != "REVIEW" or replay.get("status") != "REVIEW":
        return None
    if str(row.get("perspective")) != "9":
        return None

    ensemble = replay_ensemble(row)
    nutrition = ensemble.get("nutrition") or replay.get("nutrition") or {}
    basis = ensemble.get("basis") or replay.get("basis")
    families = int(ensemble.get("independent_engine_families") or 0)
    corroborated = int(ensemble.get("corroborated_fields") or 0)
    reasons = [str(reason) for reason in (ensemble.get("reasons") or [])]

    if any(nutrition.get(field) is None for field in CORE_FIELDS):
        return None
    if basis not in {"100_g", "100_ml"} or "UNCORROBORATED_BASIS" in reasons:
        return None
    if families != 2 or corroborated != 2:
        return None
    if is_hard_conflict(ensemble) or has_energy_mismatch(ensemble):
        return None

    field_rows = [field for field in (ensemble.get("fields") or []) if field.get("name") in CORE_FIELDS]
    uncorroborated = [field for field in field_rows if not bool(field.get("corroborated"))]
    if len(field_rows) != 4 or len(uncorroborated) != 2:
        return None
    if any(len(field.get("engine_families") or []) != 1 for field in uncorroborated):
        return None

    uncorroborated_fields = sorted(str(field.get("name")) for field in uncorroborated)
    uncorroborated_sources = {
        str(field.get("name")): str((field.get("engine_families") or [""])[0])
        for field in uncorroborated
    }
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
        "uncorroborated_core_fields": uncorroborated_fields,
        "uncorroborated_source_families": uncorroborated_sources,
        "corroborated_fields": corroborated,
        "independent_engine_families": families,
        "reasons": reasons,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-results", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows = load_jsonl(Path(args.replay_results))
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} replay rows, got {len(rows)}")
    stable_reviews = [row for row in rows if row.get("status") == "REVIEW" and (row.get("replay") or {}).get("status") == "REVIEW"]
    if len(stable_reviews) != EXPECTED_STILL_REVIEW:
        raise ValueError(f"expected {EXPECTED_STILL_REVIEW} original+replay REVIEW rows, got {len(stable_reviews)}")

    candidates = [payload for row in stable_reviews if (payload := candidate_payload(row)) is not None]
    candidates.sort(key=lambda row: str(row["product_id"]))
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CANDIDATES} candidates, got {len(candidates)}")

    field_pair_counts = Counter("+".join(row["uncorroborated_core_fields"]) for row in candidates)
    source_counts = Counter(
        f"{field}:{family}"
        for row in candidates
        for field, family in row["uncorroborated_source_families"].items()
    )
    summary = {
        "audit_policy_version": AUDIT_POLICY_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "replay_rows": len(rows),
        "stable_original_and_replay_review_rows": len(stable_reviews),
        "candidate_universe": len(candidates),
        "candidate_policy": "stable p9 original+replay REVIEW + all 4 core values observed + explicit 100g/100ml basis + exactly 2 independent OCR families + exactly 2 corroborated core fields + exactly 2 uncorroborated core fields each observed by exactly 1 family + no OCR hard conflict + no energy/macro mismatch; routing only",
        "uncorroborated_core_pair_counts": dict(sorted(field_pair_counts.items())),
        "uncorroborated_source_family_counts": dict(sorted(source_counts.items())),
        "next_safe_experiment": "bounded deterministic 16-product Tesseract CLAHE/OTSU/adaptive pilot; acceptance unchanged and requires all four core fields independently corroborated",
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "two-family-two-uncorroborated-core-candidates.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in candidates),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
