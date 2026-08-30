from __future__ import annotations

"""Re-run Mercadona OCR parsing/consensus without downloading images.

Neural OCR artifacts persist normalized OCR text and each engine's prior
label-parser result, but never image bytes. Ensemble-only changes can replay the
stored parser result; parser changes can instead reparse the exact persisted
OCR text before recomputing consensus. Neither mode infers missing values or
changes source/provenance metadata.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from mercadona_nutrition_label_reader import READER_VERSION as MERCADONA_READER_VERSION
from mercadona_nutrition_label_reader import read_nutrition_label as read_mercadona_nutrition_label
from nutrition_label_reader import LabelReadResult
from nutrition_ocr_ensemble import ENSEMBLE_VERSION, ParsedOCRReading, fuse_ocr_readings

CORE_FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")


def _family(strategy: str, payload: dict[str, Any]) -> str:
    text = f"{strategy} {payload.get('engine') or ''}".lower()
    if "tesseract" in text or strategy.lower().startswith("psm"):
        return "tesseract"
    if "paddle" in text or "pp-ocr" in text:
        return "paddleocr"
    if "easyocr" in text:
        return "easyocr"
    return strategy.split(":", 1)[0].lower() or "unknown"


def _label_result(payload: dict[str, Any], *, reparse_label_text: bool = False) -> LabelReadResult:
    normalized_text = str(payload.get("normalized_ocr_text") or "")
    if reparse_label_text and normalized_text:
        return read_mercadona_nutrition_label(
            normalized_text,
            extraction_confidence=float(payload.get("confidence") or 0.0),
        )

    nutrition = payload.get("nutrition")
    if not isinstance(nutrition, dict):
        nutrition = None
    return LabelReadResult(
        status=str(payload.get("status") or "REVIEW"),
        basis=payload.get("basis"),
        nutrition=nutrition,
        confidence=float(payload.get("confidence") or 0.0),
        reasons=tuple(str(x) for x in (payload.get("reasons") or ())),
        normalized_text=normalized_text,
    )


def _readings(attempt: dict[str, Any], *, reparse_label_text: bool = False) -> tuple[ParsedOCRReading, ...]:
    target = str(attempt.get("target_kind") or "stored_evidence")
    readings: list[ParsedOCRReading] = []
    for strategy, payload in (attempt.get("engines") or {}).items():
        if not isinstance(payload, dict):
            continue
        readings.append(
            ParsedOCRReading(
                strategy=f"{strategy}:{target}",
                result=_label_result(payload, reparse_label_text=reparse_label_text),
                # The live pipeline deliberately fuses with extraction confidence,
                # not the parser's capped REVIEW confidence. Persisted artifacts
                # store that extraction confidence in the engine payload.
                extraction_confidence=float(payload.get("confidence") or 0.0),
                engine_family=_family(str(strategy), payload),
            )
        )
    return tuple(readings)


def _ensemble_payload(ensemble) -> dict[str, Any]:
    return {
        "ensemble_version": ENSEMBLE_VERSION,
        "status": ensemble.status,
        "basis": ensemble.basis,
        "nutrition": ensemble.nutrition,
        "confidence": ensemble.confidence,
        "corroborated_fields": ensemble.corroborated_fields,
        "independent_engine_families": ensemble.independent_engine_families,
        "reasons": list(ensemble.reasons),
        "fields": [
            {
                "name": field.name,
                "value": field.value,
                "strategies": list(field.strategies),
                "engine_families": list(field.engine_families),
                "corroborated": field.corroborated,
            }
            for field in ensemble.fields
        ],
    }


def replay_attempt(attempt: dict[str, Any], *, reparse_label_text: bool = False) -> dict[str, Any]:
    readings = _readings(attempt, reparse_label_text=reparse_label_text)
    ensemble = fuse_ocr_readings(readings)

    # Mirror mercadona_neural_ocr_wave._extract_region exactly: EasyOCR is a
    # bounded rescue. If REVIEW observations merely poison two independently
    # parser-DECLARED matching reads, retry consensus from positive reads only.
    has_easyocr = any(reading.family == "easyocr" for reading in readings)
    if not ensemble.declared_usable and has_easyocr:
        strict = fuse_ocr_readings(
            reading for reading in readings if reading.result.status == "DECLARED"
        )
        if strict.declared_usable:
            ensemble = strict
    return _ensemble_payload(ensemble)


def _complete_plausible_core(nutrition: Any) -> dict[str, float] | None:
    if not isinstance(nutrition, dict) or any(nutrition.get(key) is None for key in CORE_FIELDS):
        return None
    try:
        values = {key: float(nutrition[key]) for key in CORE_FIELDS}
    except (TypeError, ValueError):
        return None
    if not 0 <= values["calories"] <= 1000:
        return None
    if any(not 0 <= values[key] <= 100 for key in ("fat_g", "carbohydrate_g", "protein_g")):
        return None
    return values


def _energy_consistent_core(nutrition: Any) -> bool:
    values = _complete_plausible_core(nutrition)
    if values is None:
        return False
    estimated = (
        9 * values["fat_g"]
        + 4 * values["carbohydrate_g"]
        + 4 * values["protein_g"]
    )
    return abs(estimated - values["calories"]) <= max(8.0, values["calories"] * 0.10)


def _safer_review_fallback(
    current_nutrition: Any,
    current_basis: str | None,
    candidate: dict[str, Any],
) -> bool:
    """Prefer a later complete coherent REVIEW only over a complete bad tuple.

    This is intentionally much narrower than generic REVIEW ranking. It exists
    for the observed Mercadona 21594 failure mode where the first crop binds a
    neighbouring row into a complete energy-incoherent tuple and a later crop of
    the same first-party image supplies a complete energy-coherent tuple on the
    same explicit per-100 basis. Status remains REVIEW; no value is inferred.
    """
    candidate_basis = candidate.get("basis")
    if current_basis is None or candidate_basis != current_basis:
        return False
    if _complete_plausible_core(current_nutrition) is None:
        return False
    if _energy_consistent_core(current_nutrition):
        return False
    if _complete_plausible_core(candidate.get("nutrition")) is None:
        return False
    return _energy_consistent_core(candidate.get("nutrition"))


def replay_product(
    row: dict[str, Any], *, reparse_label_text: bool = False
) -> tuple[str, dict[str, float] | None, str | None, list[dict[str, Any]]]:
    replayed: list[dict[str, Any]] = []
    best_status = "NO_VISUAL_REGION" if row.get("status") == "NO_VISUAL_REGION" else "REVIEW"
    best_nutrition: dict[str, float] | None = None
    best_basis: str | None = None

    for attempt in row.get("attempts") or ():
        if not isinstance(attempt, dict):
            continue
        ensemble = replay_attempt(attempt, reparse_label_text=reparse_label_text)
        replayed.append(ensemble)
        if ensemble["status"] == "DECLARED":
            return "DECLARED", ensemble.get("nutrition"), ensemble.get("basis"), replayed
        if ensemble.get("nutrition") is not None:
            best_status = "REVIEW"
            if best_nutrition is None:
                best_nutrition = ensemble.get("nutrition")
                best_basis = ensemble.get("basis")
            elif _safer_review_fallback(best_nutrition, best_basis, ensemble):
                best_nutrition = ensemble.get("nutrition")
                best_basis = ensemble.get("basis")

    if not replayed and row.get("status") == "ERROR":
        return "ERROR", None, None, replayed
    return best_status, best_nutrition, best_basis, replayed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Prior Mercadona OCR results.jsonl")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument(
        "--reparse-label-text",
        action="store_true",
        help="Reparse persisted normalized OCR text with the current conservative Mercadona reader before consensus",
    )
    ap.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit non-zero if an existing DECLARED regresses or changes macro values",
    )
    args = ap.parse_args()

    source = Path(args.input)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    old_counts: Counter[str] = Counter()
    new_counts: Counter[str] = Counter()
    transitions: Counter[str] = Counter()
    promotions: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    value_changes: list[dict[str, Any]] = []
    output_rows: list[dict[str, Any]] = []

    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        old_status = str(row.get("status") or "UNRESOLVED")
        old_counts[old_status] += 1

        status, nutrition, basis, replayed = replay_product(
            row, reparse_label_text=args.reparse_label_text
        )
        new_counts[status] += 1
        transitions[f"{old_status}->{status}"] += 1

        audit = {
            "product_id": row.get("product_id"),
            "ean": row.get("ean"),
            "name": row.get("name"),
            "old_status": old_status,
            "new_status": status,
            "old_nutrition": row.get("nutrition"),
            "new_nutrition": nutrition,
            "basis": basis,
        }
        if old_status != "DECLARED" and status == "DECLARED":
            promotions.append(audit)
        if old_status == "DECLARED" and status != "DECLARED":
            regressions.append(audit)
        if old_status == status == "DECLARED" and row.get("nutrition") != nutrition:
            value_changes.append(audit)

        updated = dict(row)
        updated["replay"] = {
            "ensemble_version": ENSEMBLE_VERSION,
            "mercadona_reader_version": MERCADONA_READER_VERSION if args.reparse_label_text else None,
            "reparsed_label_text": bool(args.reparse_label_text),
            "prior_status": old_status,
            "status": status,
            "basis": basis,
            "nutrition": nutrition,
            "attempt_ensembles": replayed,
        }
        output_rows.append(updated)

    (out / "results-replayed.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    (out / "promotions.json").write_text(
        json.dumps(promotions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        "mode": (
            "REPLAY_REPARSE_FROM_PERSISTED_OCR_TEXT"
            if args.reparse_label_text
            else "REPLAY_FROM_PERSISTED_OCR_EVIDENCE"
        ),
        "ensemble_version": ENSEMBLE_VERSION,
        "mercadona_reader_version": MERCADONA_READER_VERSION if args.reparse_label_text else None,
        "processed": len(output_rows),
        "old_status_counts": dict(sorted(old_counts.items())),
        "new_status_counts": dict(sorted(new_counts.items())),
        "transitions": dict(sorted(transitions.items())),
        "promotions": len(promotions),
        "regressions": len(regressions),
        "declared_value_changes": len(value_changes),
        "redistribution_allowed": False,
        "note": "No images downloaded; no OCR rerun; no missing values inferred",
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    unsafe = bool(regressions or value_changes)
    if unsafe:
        (out / "regressions.json").write_text(
            json.dumps(regressions, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out / "declared-value-changes.json").write_text(
            json.dumps(value_changes, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 3 if args.fail_on_regression and unsafe else 0


if __name__ == "__main__":
    raise SystemExit(main())
