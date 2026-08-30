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
PROBE_VERSION = "1.0.0"


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


def _attempt_replay(attempt: dict[str, Any]) -> tuple[dict[str, Any], dict[str, tuple[str, ...]]]:
    readings: list[ParsedOCRReading] = []
    repairs_by_strategy: dict[str, tuple[str, ...]] = {}
    target_kind = str(attempt.get("target_kind") or "persisted_target")

    for strategy, payload in sorted((attempt.get("engines") or {}).items()):
        if not isinstance(payload, dict):
            continue
        text = str(payload.get("normalized_ocr_text") or "")
        repaired, repairs = repair_observed_ocr_typos(text)
        if repairs:
            repairs_by_strategy[strategy] = repairs
        confidence = float(payload.get("confidence") or 0.0)
        parsed = read_nutrition_label(repaired, extraction_confidence=confidence)
        readings.append(ParsedOCRReading(
            strategy=f"{strategy}:{target_kind}",
            result=parsed,
            extraction_confidence=confidence,
            engine_family=_engine_family(strategy),
        ))

    ensemble = fuse_ocr_readings(readings)
    payload = {
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
    return payload, repairs_by_strategy


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
    old_declared_regressions: list[str] = []
    old_declared_value_changes: list[str] = []
    conflicting_declared_attempts: list[str] = []

    for row in rows:
        pid = str(row.get("product_id") or "")
        prior_replay = row.get("replay") or {}
        prior_status = str(prior_replay.get("status") or row.get("status") or "UNKNOWN")
        attempt_results: list[dict[str, Any]] = []
        row_repairs: dict[str, dict[str, tuple[str, ...]]] = {}

        for index, attempt in enumerate(row.get("attempts") or []):
            ensemble, repairs = _attempt_replay(attempt)
            attempt_results.append(ensemble)
            if repairs:
                row_repairs[str(index)] = repairs
                changed_products.add(pid)
                for values in repairs.values():
                    repair_counts.update(values)

        declared_attempts = [x for x in attempt_results if x.get("status") == "DECLARED"]
        safe_declared: dict[str, Any] | None = None
        if declared_attempts:
            candidate = declared_attempts[0]
            if all(_compatible(candidate, other) for other in declared_attempts[1:]):
                safe_declared = candidate
            else:
                conflicting_declared_attempts.append(pid)

        if prior_status == "DECLARED":
            if safe_declared is None:
                old_declared_regressions.append(pid)
            else:
                prior_nutrition = prior_replay.get("nutrition") or {}
                prior_basis = prior_replay.get("basis")
                if prior_basis != safe_declared.get("basis") or any(
                    prior_nutrition.get(field) is None
                    or not _close(field, float(prior_nutrition[field]), float((safe_declared.get("nutrition") or {})[field]))
                    for field in FIELDS
                ):
                    old_declared_value_changes.append(pid)

        if prior_status == "REVIEW" and safe_declared is not None:
            promotions.append({
                "product_id": pid,
                "ean": row.get("ean"),
                "name": row.get("name"),
                "basis": safe_declared.get("basis"),
                "nutrition": safe_declared.get("nutrition"),
                "corroborated_fields": safe_declared.get("corroborated_fields"),
                "independent_engine_families": safe_declared.get("independent_engine_families"),
                "repairs": row_repairs,
                "source": "MERCADONA_FIRST_PARTY/label image",
                "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
                "redistribution_allowed": False,
                "usable": False,
                "note": "probe only; requires parser integration and end-to-end OCR validation before canonical promotion",
            })

        if row_repairs:
            repaired_rows.append({
                "product_id": pid,
                "prior_status": prior_status,
                "repairs": row_repairs,
                "attempt_ensembles": attempt_results,
            })

    summary = {
        "kind": "MERCADONA_PERSISTED_OCR_TYPO_RECOVERY_PROBE",
        "probe_version": PROBE_VERSION,
        "input_rows": len(rows),
        "prior_declared": sum(1 for row in rows if (row.get("replay") or {}).get("status") == "DECLARED"),
        "prior_review": sum(1 for row in rows if (row.get("replay") or {}).get("status") == "REVIEW"),
        "products_with_repaired_tokens": len(changed_products),
        "repair_counts": dict(sorted(repair_counts.items())),
        "probe_review_to_declared": len(promotions),
        "probe_promotion_product_ids": [row["product_id"] for row in promotions],
        "old_declared_regressions": old_declared_regressions,
        "old_declared_value_changes": old_declared_value_changes,
        "conflicting_declared_attempts": conflicting_declared_attempts,
        "safety_gate_passed": not old_declared_regressions and not old_declared_value_changes and not conflicting_declared_attempts,
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
    return 0 if summary["safety_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
