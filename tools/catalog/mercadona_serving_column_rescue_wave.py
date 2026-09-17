from __future__ import annotations

from dataclasses import replace

import mercadona_neural_ocr_wave as base
from label_easyocr_extractor import extract_with_easyocr
from label_neural_extractor import extract_with_paddleocr
from label_text_extractor import extract_with_tesseract
from mercadona_explicit_serving_column_rescue import project_explicit_serving_column
from nutrition_ocr_ensemble import fuse_ocr_readings


# This runner is deliberately separate from the production wave. It always pays
# for a third OCR family, but only for a tiny explicitly selected rescue cohort.
# Acceptance is unchanged: at least two independent OCR families must corroborate
# all four fields before the ordinary ensemble can declare.
EXTRACTOR_SPECS = (
    ("paddleocr", "paddleocr", extract_with_paddleocr),
    ("tesseract-psm4", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=4)),
    ("tesseract-psm6", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=6)),
    ("tesseract-psm11", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=11)),
    ("easyocr", "easyocr", extract_with_easyocr),
)


def _project_if_safe(reading):
    confidence = float(reading.extraction.confidence)
    projection = project_explicit_serving_column(
        reading.extraction.text,
        extraction_confidence=confidence,
    )
    if projection is not None:
        return replace(reading, parsed=projection.result)

    # The global parser intentionally refuses to DECLARE a single OCR observation
    # below 0.85 confidence. Do not relax that rule. For this bounded rescue only,
    # if the engine is still above the ensemble's existing 0.70 evidence floor,
    # rerun the *structural* projector at the parser threshold to determine whether
    # all eight numeric cells + both explicit headers form a valid scaled table.
    # Any successful structural projection is immediately demoted back to REVIEW
    # at the real OCR confidence. It can therefore only help if a separate engine
    # independently corroborates the same values under the unchanged ensemble gate.
    if confidence < 0.70:
        return reading
    structural = project_explicit_serving_column(
        reading.extraction.text,
        extraction_confidence=0.85,
    )
    if structural is None or structural.result.status != "DECLARED" or structural.result.nutrition is None:
        return reading
    demoted = replace(
        structural.result,
        status="REVIEW",
        confidence=confidence,
        reasons=tuple(dict.fromkeys((
            "LOW_EXTRACTION_CONFIDENCE",
            "STRUCTURAL_PROJECTION_RETAINED_AS_REVIEW",
            *structural.result.reasons,
        ))),
    )
    return replace(reading, parsed=demoted)


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
        # independently parser-DECLARED projections. Any conflicting DECLARED
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
