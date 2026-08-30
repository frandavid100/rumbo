from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

from nutrition_label_reader import read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")
PROBE_VERSION = "1.1.0"


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _engine_family(strategy: str) -> str:
    value = strategy.lower()
    if value.startswith("tesseract"):
        return "tesseract"
    if value.startswith("paddleocr"):
        return "paddleocr"
    if value.startswith("easyocr"):
        return "easyocr"
    return value.split(":", 1)[0]


def repair_observed_ocr_typos(text: str) -> tuple[str, tuple[str, ...]]:
    """Apply only narrow OCR repairs observed in persisted Mercadona label evidence.

    This is deliberately a probe, not a canonical parser change. Repairs are allowed
    only where the OCR token is structurally a nutrition-table token: a numeric kcal
    unit typo, or an exact standalone `Grasas` row-label typo. No numeric value is
    invented, rounded, copied from another engine, or inferred from energy balance.
    """
    repairs: list[str] = []
    out_lines: list[str] = []

    for line in (text or "").splitlines():
        original = line

        # Observed unit confusions where OCR retains the numeric energy value but
        # corrupts the printed `kcal` glyph. Require a number immediately before
        # the unit so prose cannot be rewritten into an energy observation.
        line, count = re.subn(
            r"(?i)(\b\d{1,4}(?:[.,]\d{1,2})?)[ \t]*(?:keal|kcai|kcall|kcali)(?![a-z0-9])",
            r"\1 kcal",
            line,
        )
        if count:
            repairs.append("ENERGY_UNIT_OCR_VARIANT")

        # A rarer observed Tesseract failure drops the leading `k` and reads
        # `Ícal`. Accept that repair only on a line that also contains a printed
        # kJ energy token, making the unit pairing explicit rather than guessed.
        if re.search(r"(?i)\b\d{2,4}(?:[.,]\d+)?[ \t]*k[ \t]*j\b", line):
            line, count = re.subn(
                r"(?i)(\b\d{1,4}(?:[.,]\d{1,2})?)[ \t]*[ií]cal(?![a-z0-9])",
                r"\1 kcal",
                line,
            )
            if count:
                repairs.append("ENERGY_UNIT_DROPPED_K")

        # Persisted PP-OCR/Tesseract evidence contains exact standalone row-label
        # substitutions `brasas` and `vrasas` for printed `Grasas`. Do not repair
        # prose such as `a las brasas`, and do not accept looser edit-distance
        # guesses (`asas`, `rasas`, etc.) in this conservative probe.
        if re.fullmatch(r"[ \t]*(?:brasas|vrasas)[ \t]*", line, flags=re.I):
            indent = line[: len(line) - len(line.lstrip(" \t"))]
            line = indent + "Grasas"
            repairs.append("FAT_LABEL_OCR_VARIANT")

        out_lines.append(line)
        if original.endswith("\r") and not line.endswith("\r"):
            out_lines[-1] += "\r"

    repaired = "\n".join(out_lines)
    if (text or "").endswith("\n"):
        repaired += "\n"
    return repaired, tuple(dict.fromkeys(repairs))


def _safe_fuse(readings: list[ParsedOCRReading]):
    """Mirror the production ensemble's REVIEW-poisoning safety behavior.

    REVIEW observations are audit evidence, not positive votes. First use the full
    conservative fusion. If it does not declare, retry using only independently
    parser-DECLARED readings; that strict result may win only if it independently
    satisfies all normal ensemble/basis/energy safeguards. This is the same narrow
    rescue used by the neural OCR path after a corroborating engine is available.
    """
    raw = fuse_ocr_readings(readings)
    if raw.declared_usable:
        return raw
    strict = fuse_ocr_readings([reading for reading in readings if reading.result.status == "DECLARED"])
    return strict if strict.declared_usable else raw


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


def _attempt_replay(
    attempt: dict[str, Any], *, apply_repairs: bool
) -> tuple[dict[str, Any], dict[str, tuple[str, ...]]]:
    readings: list[ParsedOCRReading] = []
    repairs_by_strategy: dict[str, tuple[str, ...]] = {}
    target_kind = str(attempt.get("target_kind") or "persisted_target")

    for strategy, payload in sorted((attempt.get("engines") or {}).items()):
        if not isinstance(payload, dict):
            continue
        text = str(payload.get("normalized_ocr_text") or "")
        repaired, repairs = repair_observed_ocr_typos(text)
        parse_text = repaired if apply_repairs else text
        if apply_repairs and repairs:
            repairs_by_strategy[strategy] = repairs
        confidence = float(payload.get("confidence") or 0.0)
        parsed = read_nutrition_label(parse_text, extraction_confidence=confidence)
        readings.append(ParsedOCRReading(
            strategy=f"{strategy}:{target_kind}",
            result=parsed,
            extraction_confidence=confidence,
            engine_family=_engine_family(strategy),
        ))

    return _ensemble_payload(_safe_fuse(readings)), repairs_by_strategy


def _close(field: str, a: float, b: float) -> bool:
    if field == "calories":
        tolerance = max(5.0, 0.04 * max(abs(a), abs(b), 1.0))
    else:
        tolerance = max(0.6, 0.10 * max(abs(a), abs(b), 1.0))
    return abs(a - b) <= tolerance


def _compatible(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("basis") != b.get("basis"):
        return False
    na = a.get("nutrition") or {}
    nb = b.get("nutrition") or {}
    return all(
        na.get(field) is not None
        and nb.get(field) is not None
        and _close(field, float(na[field]), float(nb[field]))
        for field in FIELDS
    )


def _safe_declared_from_attempts(
    attempt_results: list[dict[str, Any]], pid: str, conflicts: list[str]
) -> dict[str, Any] | None:
    declared_attempts = [x for x in attempt_results if x.get("status") == "DECLARED"]
    if not declared_attempts:
        return None
    candidate = declared_attempts[0]
    if all(_compatible(candidate, other) for other in declared_attempts[1:]):
        return candidate
    conflicts.append(pid)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay-results", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = _load(Path(args.replay_results))
    if len(rows) != 2630:
        raise ValueError(f"expected 2630 persisted p9 OCR rows, got {len(rows)}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    promotions: list[dict[str, Any]] = []
    repaired_rows: list[dict[str, Any]] = []
    repair_counts: Counter[str] = Counter()
    changed_products: set[str] = set()
    baseline_declared_products: set[str] = set()
    repaired_declared_products: set[str] = set()
    historical_declared_unreproduced: list[str] = []
    historical_declared_conflicts: list[str] = []
    repair_declared_regressions: list[str] = []
    repair_declared_value_changes: list[str] = []
    baseline_conflicting_attempts: list[str] = []
    repaired_conflicting_attempts: list[str] = []

    for row in rows:
        pid = str(row.get("product_id") or "")
        prior_replay = row.get("replay") or {}
        prior_status = str(prior_replay.get("status") or row.get("status") or "UNKNOWN")
        baseline_attempt_results: list[dict[str, Any]] = []
        repaired_attempt_results: list[dict[str, Any]] = []
        row_repairs: dict[str, dict[str, tuple[str, ...]]] = {}

        for index, attempt in enumerate(row.get("attempts") or []):
            baseline_ensemble, _ = _attempt_replay(attempt, apply_repairs=False)
            repaired_ensemble, repairs = _attempt_replay(attempt, apply_repairs=True)
            baseline_attempt_results.append(baseline_ensemble)
            repaired_attempt_results.append(repaired_ensemble)
            if repairs:
                row_repairs[str(index)] = repairs
                changed_products.add(pid)
                for values in repairs.values():
                    repair_counts.update(values)

        baseline_declared = _safe_declared_from_attempts(
            baseline_attempt_results, pid, baseline_conflicting_attempts
        )
        repaired_declared = _safe_declared_from_attempts(
            repaired_attempt_results, pid, repaired_conflicting_attempts
        )
        if baseline_declared is not None:
            baseline_declared_products.add(pid)
        if repaired_declared is not None:
            repaired_declared_products.add(pid)

        # The persisted 130-product trusted cut is immutable historical evidence.
        # Current parser replay is diagnostic and must never demote it. A repaired
        # parse is unsafe only if it actually produces a conflicting complete tuple.
        if prior_status == "DECLARED":
            if repaired_declared is None:
                historical_declared_unreproduced.append(pid)
            else:
                persisted = {
                    "basis": prior_replay.get("basis"),
                    "nutrition": prior_replay.get("nutrition"),
                }
                if not _compatible(persisted, repaired_declared):
                    historical_declared_conflicts.append(pid)

        # Isolate the effect of these exact token repairs from every parser/ensemble
        # improvement already present on the branch. Existing current-replay gains
        # are not attributed to this probe and are not staged as typo promotions.
        if baseline_declared is not None:
            if repaired_declared is None:
                repair_declared_regressions.append(pid)
            elif not _compatible(baseline_declared, repaired_declared):
                repair_declared_value_changes.append(pid)

        if (
            prior_status == "REVIEW"
            and baseline_declared is None
            and repaired_declared is not None
            and bool(row_repairs)
        ):
            promotions.append({
                "product_id": pid,
                "ean": row.get("ean"),
                "name": row.get("name"),
                "basis": repaired_declared.get("basis"),
                "nutrition": repaired_declared.get("nutrition"),
                "corroborated_fields": repaired_declared.get("corroborated_fields"),
                "independent_engine_families": repaired_declared.get("independent_engine_families"),
                "repairs": row_repairs,
                "source": "MERCADONA_FIRST_PARTY/label image",
                "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
                "redistribution_allowed": False,
                "usable": False,
                "note": "incremental persisted-text probe only; requires canonical parser integration and end-to-end OCR reproduction before promotion",
            })

        if row_repairs:
            repaired_rows.append({
                "product_id": pid,
                "prior_status": prior_status,
                "repairs": row_repairs,
                "baseline_attempt_ensembles": baseline_attempt_results,
                "repaired_attempt_ensembles": repaired_attempt_results,
            })

    safety_gate_passed = not (
        historical_declared_conflicts
        or repair_declared_regressions
        or repair_declared_value_changes
        or repaired_conflicting_attempts
    )
    summary = {
        "kind": "MERCADONA_PERSISTED_OCR_TYPO_RECOVERY_PROBE",
        "probe_version": PROBE_VERSION,
        "input_rows": len(rows),
        "prior_declared": sum(1 for row in rows if (row.get("replay") or {}).get("status") == "DECLARED"),
        "prior_review": sum(1 for row in rows if (row.get("replay") or {}).get("status") == "REVIEW"),
        "products_with_repaired_tokens": len(changed_products),
        "repair_counts": dict(sorted(repair_counts.items())),
        "current_unrepaired_reparse_declared": len(baseline_declared_products),
        "current_repaired_reparse_declared": len(repaired_declared_products),
        "incremental_typo_review_to_declared": len(promotions),
        "incremental_typo_promotion_product_ids": [row["product_id"] for row in promotions],
        "historical_declared_unreproduced_by_current_reparse": historical_declared_unreproduced,
        "historical_declared_conflicts": historical_declared_conflicts,
        "repair_declared_regressions": repair_declared_regressions,
        "repair_declared_value_changes": repair_declared_value_changes,
        "baseline_conflicting_declared_attempts": baseline_conflicting_attempts,
        "repaired_conflicting_declared_attempts": repaired_conflicting_attempts,
        "safety_gate_passed": safety_gate_passed,
        "canonical_promotions_applied": 0,
        "images_downloaded": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "source": "MERCADONA_FIRST_PARTY/label image",
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }

    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "promotions.json").write_text(json.dumps(promotions, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "repaired-rows.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in repaired_rows),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if safety_gate_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
