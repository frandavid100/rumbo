from __future__ import annotations

from dataclasses import replace

import mercadona_neural_ocr_wave as base
from label_easyocr_extractor import extract_with_easyocr
from label_neural_extractor import extract_with_paddleocr
from label_text_extractor import extract_with_tesseract
from mercadona_explicit_serving_column_rescue import project_explicit_serving_column
from nutrition_ocr_ensemble import fuse_ocr_readings


# This runner is deliberately separate from the production wave.  It always pays
# for a third OCR family, but only for a tiny explicitly selected rescue cohort.
# Acceptance is unchanged: at least two independent OCR families must independently
# produce a parser-DECLARED per-100 tuple before the ordinary ensemble can declare.
EXTRACTOR_SPECS = (
    ("paddleocr", "paddleocr", extract_with_paddleocr),
    ("tesseract-psm4", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=4)),
    ("tesseract-psm6", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=6)),
    ("tesseract-psm11", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=11)),
    ("easyocr", "easyocr", extract_with_easyocr),
)


def _project_if_safe(reading):
    projection = project_explicit_serving_column(
        reading.extraction.text,
        extraction_confidence=reading.extraction.confidence,
    )
    if projection is None:
        return reading
    return replace(reading, parsed=projection.result)


def _extract_region(evidence, region_path, target_kind: str):
    readings = []
    engine_errors: dict[str, str] = {}
    for strategy, family, extractor in EXTRACTOR_SPECS:
        try:
            extracted = extractor(region_path)
            reading = base._reading(evidence, extracted)
            readings.append((strategy, family, _project_if_safe(reading)))
        except Exception as exc:
            engine_errors[strategy] = f"{type(exc).__name__}:{exc}"

    parsed = base._as_parsed_readings(readings, target_kind)
    ensemble = fuse_ocr_readings(parsed)
    if not ensemble.declared_usable:
        # REVIEW observations are retained for audit but cannot veto two matching,
        # independently parser-DECLARED projections.  Any conflicting DECLARED
        # family remains inside this strict fusion and therefore still blocks.
        strict = base._fuse_declared_only_readings(
            (
                (strategy, family, reading.parsed, reading.extraction.confidence)
                for strategy, family, reading in readings
            ),
            target_kind,
        )
        if strict.declared_usable:
            ensemble = strict
    return readings, engine_errors, ensemble


def main() -> int:
    return base.main()


if __name__ == "__main__":
    base._extract_region = _extract_region
    raise SystemExit(main())
