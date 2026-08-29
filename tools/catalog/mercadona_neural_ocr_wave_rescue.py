from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import mercadona_neural_ocr_wave as base

RESCUE_POLICY_VERSION = "2.0.0"
RESCUE_POLICY = (
    "EASYOCR_WHEN_BASELINE_HAS_DECLARED_UNCORROBORATED_READING_OR_"
    "TWO_INDEPENDENT_FAMILIES_WITH_AT_LEAST_THREE_NONCONFLICTING_CORE_FIELDS"
)


def _has_hard_conflict(ensemble) -> bool:
    return any(
        str(reason).startswith("OCR_FIELD_CONFLICT")
        or str(reason).startswith("OCR_SAME_ENGINE_CONFLICT")
        or str(reason) == "OCR_BASIS_CONFLICT"
        for reason in (ensemble.reasons or ())
    )


def _should_run_easyocr(ensemble, readings) -> bool:
    """Keep EasyOCR bounded while rescuing near-complete independent reads.

    The original policy only paid for EasyOCR when one baseline engine had a
    fully parser-DECLARED reading. Audit of the validated 2048 partial wave found
    many REVIEW rows where PaddleOCR and Tesseract already supplied three or four
    non-conflicting core fields between two independent families, but neither
    engine was individually complete. EasyOCR is useful independent evidence in
    that narrow situation. It never bypasses the existing parser, energy/macro
    plausibility checks, basis checks, or four-field/two-family corroboration.
    """
    if ensemble.declared_usable:
        return False
    if any(reading.parsed.status == "DECLARED" for _strategy, _family, reading in readings):
        return True
    if ensemble.independent_engine_families < 2:
        return False
    if len(ensemble.nutrition or {}) < 3:
        return False
    if _has_hard_conflict(ensemble):
        return False
    return True


def _extract_region(evidence, region_path: Path, target_kind: str):
    readings = []
    engine_errors: dict[str, str] = {}
    extractor_specs = (
        ("paddleocr", "paddleocr", base.extract_with_paddleocr),
        ("tesseract-psm4", "tesseract", lambda path: base.extract_with_tesseract(path, language="spa", psm=4)),
        ("tesseract-psm6", "tesseract", lambda path: base.extract_with_tesseract(path, language="spa", psm=6)),
        ("tesseract-psm11", "tesseract", lambda path: base.extract_with_tesseract(path, language="spa", psm=11)),
    )
    for strategy, family, extractor in extractor_specs:
        try:
            extracted = extractor(region_path)
            reading = base._reading(evidence, extracted)
            readings.append((strategy, family, reading))
        except Exception as exc:
            engine_errors[strategy] = f"{type(exc).__name__}:{exc}"

    ensemble = base.fuse_ocr_readings(base._as_parsed_readings(readings, target_kind))

    if _should_run_easyocr(ensemble, readings):
        try:
            extracted = base.extract_with_easyocr(region_path)
            reading = base._reading(evidence, extracted)
            readings.append(("easyocr", "easyocr", reading))
        except Exception as exc:
            engine_errors["easyocr"] = f"{type(exc).__name__}:{exc}"
        else:
            raw_with_easyocr = base.fuse_ocr_readings(base._as_parsed_readings(readings, target_kind))
            if raw_with_easyocr.declared_usable:
                ensemble = raw_with_easyocr
            else:
                strict = base._fuse_declared_only_readings(
                    (
                        (strategy, family, reading.parsed, reading.extraction.confidence)
                        for strategy, family, reading in readings
                    ),
                    target_kind,
                )
                ensemble = strict if strict.declared_usable else raw_with_easyocr

    return readings, engine_errors, ensemble


def _rewrite_summary() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--out", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    args, _ = parser.parse_known_args(sys.argv[1:])
    path = Path(args.out) / f"summary-{args.shard_index:02d}.json"
    if not path.is_file():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["mode"] = "PADDLEOCR_TESSERACT_WITH_BOUNDED_NEAR_COMPLETE_EASYOCR_RESCUE"
    payload["fallback_policy"] = (
        "FULL_BACK_IMAGE_ONLY_WHEN_NO_VISUAL_REGION; " + RESCUE_POLICY
    )
    payload["rescue_policy_version"] = RESCUE_POLICY_VERSION
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    base._extract_region = _extract_region
    result = base.main()
    _rewrite_summary()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
