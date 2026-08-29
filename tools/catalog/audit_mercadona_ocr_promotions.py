from __future__ import annotations

"""Independently audit REVIEW->DECLARED Mercadona OCR replay promotions.

The replay workflow can exercise a newer consensus policy over persisted OCR
observations without downloading images.  This audit deliberately re-checks the
promotion boundary from the raw per-engine parser payloads rather than trusting
only the replayed ensemble summary.  It never infers missing values and never
changes catalogue classification.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _family(strategy: str, payload: dict[str, Any]) -> str:
    text = f"{strategy} {payload.get('engine') or ''}".lower()
    if "tesseract" in text or strategy.lower().startswith("psm"):
        return "tesseract"
    if "paddle" in text or "pp-ocr" in text:
        return "paddleocr"
    if "easyocr" in text:
        return "easyocr"
    return strategy.split(":", 1)[0].lower() or "unknown"


def _close(field: str, a: float, b: float) -> bool:
    if field == "calories":
        tolerance = max(5.0, 0.04 * max(abs(a), abs(b), 1.0))
    else:
        tolerance = max(0.6, 0.10 * max(abs(a), abs(b), 1.0))
    return abs(a - b) <= tolerance


def _complete(payload: dict[str, Any]) -> bool:
    nutrition = payload.get("nutrition")
    return isinstance(nutrition, dict) and all(isinstance(nutrition.get(k), (int, float)) for k in FIELDS)


def _eligible_engine_payloads(attempt: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    out: list[tuple[str, str, dict[str, Any]]] = []
    for strategy, payload in (attempt.get("engines") or {}).items():
        if not isinstance(payload, dict):
            continue
        confidence = float(payload.get("confidence") or 0.0)
        if payload.get("status") == "NOT_NUTRITION_LABEL" or confidence < 0.70:
            continue
        if not isinstance(payload.get("nutrition"), dict):
            continue
        out.append((str(strategy), _family(str(strategy), payload), payload))
    return out


def _find_declared_attempt(row: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    replay = row.get("replay") or {}
    ensembles = replay.get("attempt_ensembles") or []
    for index, ensemble in enumerate(ensembles):
        if isinstance(ensemble, dict) and ensemble.get("status") == "DECLARED":
            return index, ensemble
    raise ValueError("promotion has no DECLARED replay attempt")


def _audit_one(row: dict[str, Any], promotion: dict[str, Any]) -> dict[str, Any]:
    pid = str(row.get("product_id") or "")
    errors: list[str] = []
    if str(promotion.get("old_status")) == "DECLARED":
        errors.append("NOT_A_PROMOTION")
    if str(promotion.get("new_status")) != "DECLARED":
        errors.append("PROMOTION_NOT_DECLARED")

    try:
        attempt_index, ensemble = _find_declared_attempt(row)
    except ValueError as exc:
        return {"product_id": pid, "errors": [str(exc)]}

    attempts = row.get("attempts") or []
    if attempt_index >= len(attempts) or not isinstance(attempts[attempt_index], dict):
        return {"product_id": pid, "errors": ["MISSING_SOURCE_ATTEMPT"]}
    attempt = attempts[attempt_index]
    nutrition = ensemble.get("nutrition") or {}
    if promotion.get("new_nutrition") != nutrition:
        errors.append("PROMOTION_NUTRITION_MISMATCH")

    basis = ensemble.get("basis")
    if basis not in ("100_g", "100_ml"):
        errors.append("MISSING_OR_INVALID_BASIS")

    independent_families = int(ensemble.get("independent_engine_families") or 0)
    corroborated_fields = int(ensemble.get("corroborated_fields") or 0)
    if independent_families < 2:
        errors.append("INSUFFICIENT_ENSEMBLE_FAMILIES")
    if corroborated_fields < 4:
        errors.append("INSUFFICIENT_ENSEMBLE_CORROBORATION")

    payloads = _eligible_engine_payloads(attempt)
    explicit_bases = {
        str(payload.get("basis"))
        for _strategy, _family_name, payload in payloads
        if payload.get("basis")
    }
    if len(explicit_bases) > 1:
        errors.append("RAW_BASIS_CONFLICT")

    complete_basis_families = sorted({
        family
        for _strategy, family, payload in payloads
        if payload.get("basis") == basis and _complete(payload)
    })
    if not complete_basis_families:
        errors.append("NO_COMPLETE_EXPLICIT_BASIS_SOURCE")

    field_support: dict[str, list[str]] = {}
    for field in FIELDS:
        accepted = nutrition.get(field)
        if not isinstance(accepted, (int, float)):
            errors.append(f"MISSING_ACCEPTED_{field.upper()}")
            field_support[field] = []
            continue
        families = sorted({
            family
            for _strategy, family, payload in payloads
            if isinstance((payload.get("nutrition") or {}).get(field), (int, float))
            and _close(field, float(accepted), float(payload["nutrition"][field]))
        })
        field_support[field] = families
        if len(families) < 2:
            errors.append(f"RAW_UNCORROBORATED_{field.upper()}")

    if all(isinstance(nutrition.get(k), (int, float)) for k in FIELDS):
        calories = float(nutrition["calories"])
        estimated = 9 * float(nutrition["fat_g"]) + 4 * float(nutrition["carbohydrate_g"]) + 4 * float(nutrition["protein_g"])
        tolerance = max(8.0, calories * 0.10)
        delta = abs(estimated - calories)
        if delta > tolerance:
            errors.append("ENERGY_MACRO_MISMATCH")
    else:
        estimated = None
        delta = None
        tolerance = None

    return {
        "product_id": pid,
        "ean": row.get("ean"),
        "name": row.get("name"),
        "attempt_index": attempt_index,
        "target_kind": attempt.get("target_kind"),
        "basis": basis,
        "nutrition": nutrition,
        "independent_engine_families": independent_families,
        "corroborated_fields": corroborated_fields,
        "complete_explicit_basis_families": complete_basis_families,
        "field_support_families": field_support,
        "ensemble_reasons": list(ensemble.get("reasons") or []),
        "estimated_kcal_from_core_macros": estimated,
        "energy_delta_kcal": delta,
        "energy_tolerance_kcal": tolerance,
        "safe": not errors,
        "errors": errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replayed", required=True, help="results-replayed.jsonl from replay workflow")
    ap.add_argument("--promotions", required=True, help="promotions.json from replay workflow")
    ap.add_argument("--out", required=True)
    ap.add_argument("--expected-promotions", type=int)
    args = ap.parse_args()

    rows = _load_jsonl(Path(args.replayed))
    rows_by_id = {str(row.get("product_id") or ""): row for row in rows}
    promotions = json.loads(Path(args.promotions).read_text(encoding="utf-8"))
    if not isinstance(promotions, list):
        raise SystemExit("promotions payload must be a list")
    if args.expected_promotions is not None and len(promotions) != args.expected_promotions:
        raise SystemExit(f"promotion count changed: {len(promotions)} != {args.expected_promotions}")

    audited: list[dict[str, Any]] = []
    missing_rows: list[str] = []
    for promotion in promotions:
        pid = str(promotion.get("product_id") or "")
        row = rows_by_id.get(pid)
        if row is None:
            missing_rows.append(pid)
            continue
        audited.append(_audit_one(row, promotion))

    unsafe = [item for item in audited if not item.get("safe")]
    reason_counts: Counter[str] = Counter()
    single_basis_source = 0
    for item in audited:
        for reason in item.get("ensemble_reasons") or []:
            reason_counts[str(reason)] += 1
        if len(item.get("complete_explicit_basis_families") or []) == 1:
            single_basis_source += 1

    summary = {
        "mode": "INDEPENDENT_PROMOTION_AUDIT_FROM_PERSISTED_OCR_EVIDENCE",
        "processed_corpus": len(rows),
        "promotions": len(promotions),
        "audited_promotions": len(audited),
        "safe_promotions": len(audited) - len(unsafe),
        "unsafe_promotions": len(unsafe),
        "missing_promotion_rows": missing_rows,
        "promotions_with_single_complete_explicit_basis_family": single_basis_source,
        "ensemble_reason_counts": dict(sorted(reason_counts.items())),
        "images_downloaded": False,
        "ocr_rerun": False,
        "missing_values_inferred": False,
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "source": "MERCADONA_FIRST_PARTY/label image",
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "promotion-audit.json").write_text(json.dumps(audited, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if missing_rows or unsafe:
        if unsafe:
            print(json.dumps(unsafe[:20], ensure_ascii=False, indent=2))
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
