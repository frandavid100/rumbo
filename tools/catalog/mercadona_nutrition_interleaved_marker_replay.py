from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

from nutrition_label_reader import LabelReadResult, read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings

REPLAY_POLICY_VERSION = "1.1.0"
CORE_FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")
MAX_TARGET_ROW_DISTANCE_LINES = 8

_HEADING_PATTERNS = (
    "informacion nutricional",
    "declaracion nutricional",
    "valores nutricionales",
)
_MARKER_PATTERNS = (
    ("preparacion", re.compile(r"^preparacion\b", re.I)),
    ("conservacion", re.compile(r"^conservacion\b", re.I)),
    ("condiciones de conservacion", re.compile(r"^condiciones de conservacion\b", re.I)),
    ("modo de empleo", re.compile(r"^modo de empleo\b", re.I)),
    ("fabricado por", re.compile(r"^fabricado por\b", re.I)),
    ("consumir preferentemente", re.compile(r"^consumir preferentemente\b", re.I)),
)
_TARGET_PATTERNS = {
    "fat_g": re.compile(r"^(?:grasas?(?:\s*/\s*lipidos?)?|lipidos?|grasa total)\b", re.I),
    "carbohydrate_g": re.compile(r"^(?:hidratos? de carbono|carbohidratos?)\b", re.I),
    "protein_g": re.compile(r"^proteinas?\b", re.I),
}
_STRICT_VALUE_WITH_UNIT = re.compile(
    r"^([<>]?)\s*(\d{1,3}(?:\.\d{1,2})?)\s*(g|9|q|yg|y)\s*$",
    re.I,
)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def strip_interleaved_packaging_marker_lines(
    text: str,
    *,
    missing_core_field: str,
) -> tuple[str, tuple[str, ...]]:
    """Remove only a packaging-section line that visibly clips a later core row.

    OCR can interleave a side column (for example, ``Consumir preferentemente``)
    into the middle of the nutrition table. The generic parser intentionally
    stops at those packaging markers, which is normally a useful safety boundary.
    This replay makes one narrow exception: an exact marker line may be removed
    only after an explicit nutrition heading and only when the *already known
    missing* macro row starts within the next few OCR lines.

    Numeric tokens and nutrition labels are never changed. A later ensemble must
    still independently corroborate all four core values before DECLARED is usable.
    """
    target = _TARGET_PATTERNS.get(missing_core_field)
    if target is None or not text:
        return text, ()

    lines = text.splitlines(keepends=True)
    folded_lines = [_fold(line).strip() for line in lines]
    heading_index = next(
        (
            index
            for index, line in enumerate(folded_lines)
            if any(heading in line for heading in _HEADING_PATTERNS)
        ),
        None,
    )
    if heading_index is None:
        return text, ()

    remove: dict[int, str] = {}
    for index in range(heading_index + 1, len(lines)):
        line = folded_lines[index]
        marker_name = next(
            (name for name, pattern in _MARKER_PATTERNS if pattern.match(line)),
            None,
        )
        if marker_name is None:
            continue
        stop = min(len(lines), index + 1 + MAX_TARGET_ROW_DISTANCE_LINES)
        if any(target.match(folded_lines[j]) for j in range(index + 1, stop)):
            remove[index] = marker_name

    if not remove:
        return text, ()
    cleaned = "".join(line for index, line in enumerate(lines) if index not in remove)
    return cleaned, tuple(remove[index] for index in sorted(remove))


def strict_target_value_with_unit(
    text: str,
    *,
    missing_core_field: str,
) -> float | None:
    """Return the missing macro only when its immediate cell has a gram unit.

    The interleaved-marker replay is a rescue path, so it is stricter than the
    generic parser. It accepts only a value on the same line as the target label
    or on the immediately following line, with an explicit gram-like OCR unit.
    It never skips an intervening glyph/prose line and never turns inequalities
    into exact values. This rejects the real Tesseract artefact ``Proteinas / 3d
    / 119`` while accepting independent ``Proteinas / 11 g`` observations.
    """
    target = _TARGET_PATTERNS.get(missing_core_field)
    if target is None:
        return None
    lines = [_fold(line).strip() for line in (text or "").splitlines()]
    for index, line in enumerate(lines):
        match = target.match(line)
        if not match:
            continue
        candidates: list[str] = []
        same_line = line[match.end():].strip()
        if same_line:
            candidates.append(same_line)
        elif index + 1 < len(lines):
            candidates.append(lines[index + 1])
        for candidate in candidates:
            value_match = _STRICT_VALUE_WITH_UNIT.match(candidate)
            if not value_match or value_match.group(1) in ("<", ">"):
                continue
            raw_number = value_match.group(2)
            unit = value_match.group(3).lower()
            value = float(raw_number)
            # A terminal `9` is an observed OCR rendering of the printed g glyph:
            # `119` => `11 g`, `279` => `27 g`. Only apply this repair when the
            # strict regex itself consumed that final 9 as the unit token.
            if unit == "9" and candidate.replace(" ", "").endswith("9"):
                value = float(raw_number)
            if 0 <= value <= 100:
                return value
    return None


def _guard_replayed_target(
    parsed: LabelReadResult,
    cleaned_text: str,
    *,
    missing_core_field: str,
    marker_removed: bool,
) -> tuple[LabelReadResult, float | None, bool]:
    if not marker_removed or missing_core_field not in _TARGET_PATTERNS:
        return parsed, None, True
    strict_value = strict_target_value_with_unit(
        cleaned_text,
        missing_core_field=missing_core_field,
    )
    parsed_value = (parsed.nutrition or {}).get(missing_core_field)
    valid = (
        strict_value is not None
        and isinstance(parsed_value, (int, float))
        and abs(float(parsed_value) - strict_value) <= 1e-9
    )
    if valid or parsed_value is None:
        return parsed, strict_value, valid

    nutrition = dict(parsed.nutrition or {})
    nutrition.pop(missing_core_field, None)
    reasons = list(parsed.reasons)
    guard_reason = f"INTERLEAVED_TARGET_REQUIRES_EXPLICIT_UNIT:{missing_core_field}"
    if guard_reason not in reasons:
        reasons.append(guard_reason)
    missing_reason = f"MISSING_CORE:{missing_core_field}"
    if not any(str(reason).startswith("MISSING_CORE:") for reason in reasons):
        reasons.append(missing_reason)
    guarded = LabelReadResult(
        status="REVIEW",
        basis=parsed.basis,
        nutrition=nutrition or None,
        confidence=min(parsed.confidence, .60),
        reasons=tuple(reasons),
        normalized_text=parsed.normalized_text,
    )
    return guarded, strict_value, False


def _family(strategy: str) -> str:
    low = strategy.lower()
    if "tesseract" in low or low.startswith("psm"):
        return "tesseract"
    if "paddle" in low or "pp-ocr" in low:
        return "paddleocr"
    if "easyocr" in low:
        return "easyocr"
    return low.split(":", 1)[0] or "unknown"


def _ensemble_payload(ensemble) -> dict[str, Any]:
    return {
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


def replay_row(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    missing = str(baseline.get("missing_core_field") or "")
    out = {
        "product_id": str(row.get("product_id") or ""),
        "ean": row.get("ean"),
        "name": row.get("name"),
        "brand": row.get("brand"),
        "image_url": row.get("image_url"),
        "image_index": row.get("image_index"),
        "perspective": row.get("perspective"),
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "missing_core_field_before_replay": missing,
        "replay_policy_version": REPLAY_POLICY_VERSION,
        "status": "REVIEW",
        "attempts": [],
    }

    for original_attempt in row.get("attempts") or []:
        target_kind = str(original_attempt.get("target_kind") or "unknown")
        readings: list[ParsedOCRReading] = []
        engine_payload: dict[str, Any] = {}
        for strategy, engine in sorted((original_attempt.get("engines") or {}).items()):
            text = str(engine.get("normalized_ocr_text") or "")
            cleaned, removed = strip_interleaved_packaging_marker_lines(
                text,
                missing_core_field=missing,
            )
            confidence = float(engine.get("confidence") or 0.0)
            parsed = read_nutrition_label(cleaned, extraction_confidence=confidence)
            parsed, strict_value, unit_guard_passed = _guard_replayed_target(
                parsed,
                cleaned,
                missing_core_field=missing,
                marker_removed=bool(removed),
            )
            family = _family(strategy)
            readings.append(ParsedOCRReading(
                strategy=f"{strategy}:{target_kind}",
                result=parsed,
                extraction_confidence=confidence,
                engine_family=family,
            ))
            engine_payload[strategy] = {
                "family": family,
                "confidence": confidence,
                "status": parsed.status,
                "basis": parsed.basis,
                "nutrition": parsed.nutrition,
                "reasons": list(parsed.reasons),
                "removed_interleaved_markers": list(removed),
                "strict_target_value_with_unit": strict_value,
                "strict_target_unit_guard_passed": unit_guard_passed,
                "normalized_ocr_text": parsed.normalized_text,
            }

        ensemble = fuse_ocr_readings(readings)
        replay_attempt = {
            "target_kind": target_kind,
            "engines": engine_payload,
            "ensemble": _ensemble_payload(ensemble),
        }
        out["attempts"].append(replay_attempt)
        if ensemble.declared_usable:
            out["status"] = "DECLARED"
            out["basis"] = ensemble.basis
            out["nutrition"] = ensemble.nutrition
            out["claim"] = (
                "OCR_DERIVED_FROM_MERCADONA_IMAGE; "
                "source=MERCADONA_FIRST_PARTY/label image; "
                f"replay_policy={REPLAY_POLICY_VERSION}; target={target_kind}; "
                f"independent_engines={ensemble.independent_engine_families}; "
                f"corroborated_fields={ensemble.corroborated_fields}; basis={ensemble.basis}"
            )
            break

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot-results", required=True)
    ap.add_argument("--baseline-candidates", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = [
        json.loads(line)
        for line in Path(args.pilot_results).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    baseline_rows = [
        json.loads(line)
        for line in Path(args.baseline_candidates).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    baseline = {str(row.get("product_id") or ""): row for row in baseline_rows}

    results = []
    counts: Counter[str] = Counter()
    marker_counts: Counter[str] = Counter()
    for row in rows:
        pid = str(row.get("product_id") or "")
        if pid not in baseline:
            raise SystemExit(f"pilot product missing from baseline candidate universe: {pid}")
        replayed = replay_row(row, baseline[pid])
        results.append(replayed)
        counts[replayed["status"]] += 1
        for attempt in replayed.get("attempts") or []:
            for engine in (attempt.get("engines") or {}).values():
                marker_counts.update(engine.get("removed_interleaved_markers") or [])

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results),
        encoding="utf-8",
    )
    (out / "summary.json").write_text(
        json.dumps({
            "source": "MERCADONA_FIRST_PARTY/label image",
            "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
            "redistribution_allowed": False,
            "replay_policy_version": REPLAY_POLICY_VERSION,
            "processed": len(results),
            "status_counts": dict(sorted(counts.items())),
            "removed_marker_observations": dict(sorted(marker_counts.items())),
            "numeric_tokens_modified": False,
            "images_persisted": False,
            "CLASSIFIED": 0,
            "MENU_ELIGIBLE": 0,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
