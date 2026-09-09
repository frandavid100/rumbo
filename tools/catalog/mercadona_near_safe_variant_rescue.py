from __future__ import annotations

import tempfile
from pathlib import Path

import mercadona_neural_ocr_wave as base
from label_easyocr_extractor import extract_with_easyocr
from label_image_preprocess import build_fallback_variants
from label_neural_extractor import extract_with_paddleocr
from label_text_extractor import extract_with_tesseract
from nutrition_ocr_ensemble import fuse_ocr_readings

HARD_BLOCKING_PREFIXES = (
    "OCR_FIELD_CONFLICT",
    "OCR_SAME_ENGINE_CONFLICT",
    "OCR_BASIS_CONFLICT",
    "ENERGY_MACRO_MISMATCH",
    "MULTIPLE_NUTRITION_COLUMNS",
    "IMPOSSIBLE_",
)


def should_run_variant_rescue(ensemble) -> bool:
    """Retry only clean 3/4-corroborated REVIEW tuples.

    This changes OCR observation quality, never acceptance. The extra image is a
    temporary deterministic transform of the same Mercadona rear-label image and
    observations from the same OCR engine remain the same engine family.
    """
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return False
    if ensemble.basis not in {"100_g", "100_ml"}:
        return False
    if not ensemble.nutrition or any(
        field not in ensemble.nutrition for field in base.CORE_NUTRITION_FIELDS
    ):
        return False
    if ensemble.independent_engine_families < 2:
        return False
    if ensemble.corroborated_fields != len(base.CORE_NUTRITION_FIELDS) - 1:
        return False
    if "UNCORROBORATED_CORE_FIELDS" not in ensemble.reasons:
        return False
    return not any(
        str(reason).startswith(prefix)
        for reason in ensemble.reasons
        for prefix in HARD_BLOCKING_PREFIXES
    )


def _extract_region(evidence, region_path: Path, target_kind: str):
    readings, engine_errors, ensemble = base._ORIGINAL_EXTRACT_REGION(
        evidence, region_path, target_kind
    )
    if not should_run_variant_rescue(ensemble):
        return readings, engine_errors, ensemble

    with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-near-safe-variant-") as td:
        variants = build_fallback_variants(region_path, td)
        variant = next(v for v in variants if v.name == "full_autocontrast")
        specs = (
            ("paddleocr-autocontrast", "paddleocr", extract_with_paddleocr),
            (
                "tesseract-psm4-autocontrast",
                "tesseract",
                lambda path: extract_with_tesseract(path, language="spa", psm=4),
            ),
            (
                "tesseract-psm6-autocontrast",
                "tesseract",
                lambda path: extract_with_tesseract(path, language="spa", psm=6),
            ),
            (
                "tesseract-psm11-autocontrast",
                "tesseract",
                lambda path: extract_with_tesseract(path, language="spa", psm=11),
            ),
            ("easyocr-autocontrast", "easyocr", extract_with_easyocr),
        )
        for strategy, family, extractor in specs:
            try:
                extracted = extractor(variant.path)
                reading = base._reading(evidence, extracted)
                readings.append((strategy, family, reading))
            except Exception as exc:
                engine_errors[strategy] = f"{type(exc).__name__}:{exc}"

    fused = fuse_ocr_readings(base._as_parsed_readings(readings, target_kind))
    if fused.declared_usable:
        return readings, engine_errors, fused

    strict = base._fuse_declared_only_readings(
        (
            (strategy, family, reading.parsed, reading.extraction.confidence)
            for strategy, family, reading in readings
        ),
        target_kind,
    )
    return readings, engine_errors, strict if strict.declared_usable else fused


def main() -> int:
    return base.main()


if __name__ == "__main__":
    # Keep the production wave's output/provenance schema exactly unchanged while
    # substituting only the bounded near-safe extraction step.
    base._ORIGINAL_EXTRACT_REGION = base._extract_region
    base._extract_region = _extract_region
    raise SystemExit(main())
