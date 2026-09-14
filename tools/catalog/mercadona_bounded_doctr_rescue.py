from __future__ import annotations

"""Bounded docTR + EasyOCR rescue for safe historical Mercadona REVIEW regressions.

This module changes OCR routing only. It never relaxes the parser, ensemble,
energy/macro coherence, independent-family corroboration, or provenance gates.
The caller is responsible for supplying a cohort whose historical identity and
first-party image have already been revalidated exactly.
"""

from pathlib import Path
import tempfile

from label_easyocr_extractor import extract_with_easyocr
from label_image_preprocess import build_fallback_variants
import mercadona_near_safe_doctr_retry as retry

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
MIN_PRESENT_CORE_FIELDS = 2
EASYOCR_VARIANT_NAMES = (
    "full_autocontrast",
    "crop_center",
    "crop_left",
    "crop_right",
    "crop_top",
    "crop_bottom",
)

# Keep a stable handle to the audited docTR extraction path before main() swaps
# the production extractor to the wrapper below.
_DOCTR_EXTRACT_REGION = retry._extract_region


def should_run_bounded_doctr_rescue(ensemble) -> bool:
    """Add docTR to a clean but incomplete REVIEW observation.

    The ordinary near-safe retry is intentionally restricted to complete 4-field
    candidates. This bounded rescue is for products that were previously
    DECLARED and later regressed to a non-contradictory REVIEW. It may spend a
    fourth OCR family on a current extraction with at least two core fields, but
    it cannot make that extraction usable unless the unchanged downstream
    ensemble independently satisfies the normal DECLARED contract.
    """
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return False
    if ensemble.basis not in {"100_g", "100_ml"}:
        return False
    nutrition = ensemble.nutrition if isinstance(ensemble.nutrition, dict) else {}
    present = sum(nutrition.get(field) is not None for field in CORE)
    if present < MIN_PRESENT_CORE_FIELDS:
        return False
    if int(ensemble.independent_engine_families or 0) < 1:
        return False
    reasons = [str(reason) for reason in ensemble.reasons]
    return not any(
        reason.startswith(prefix)
        for reason in reasons
        for prefix in retry.rescue.HARD_BLOCKING_PREFIXES
    )


def should_run_post_doctr_easyocr_rescue(ensemble) -> bool:
    """Spend EasyOCR only on a clean complete 3/4 tuple after docTR.

    A bounded docTR pass can recover the previously missing macro while leaving
    that one field supported by docTR alone. In that exact state EasyOCR is useful
    as a genuinely independent fourth OCR family. This predicate does not change
    acceptance: the ordinary ensemble must still corroborate all four fields.
    """
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return False
    if ensemble.basis not in {"100_g", "100_ml"}:
        return False
    nutrition = ensemble.nutrition if isinstance(ensemble.nutrition, dict) else {}
    if any(nutrition.get(field) is None for field in CORE):
        return False
    if int(ensemble.independent_engine_families or 0) < 3:
        return False
    if int(ensemble.corroborated_fields or 0) != len(CORE) - 1:
        return False
    reasons = [str(reason) for reason in ensemble.reasons]
    if "UNCORROBORATED_CORE_FIELDS" not in reasons:
        return False
    return not any(
        reason.startswith(prefix)
        for reason in reasons
        for prefix in retry.rescue.HARD_BLOCKING_PREFIXES
    )


def _extract_easyocr(evidence, image_path: Path, strategy: str, readings, engine_errors) -> None:
    try:
        extracted = extract_with_easyocr(image_path)
        readings.append((strategy, "easyocr", retry.base._reading(evidence, extracted)))
    except Exception as exc:
        engine_errors[strategy] = f"{type(exc).__name__}:{exc}"


def _extract_region_with_post_doctr_easyocr(evidence, region_path: Path, target_kind: str):
    readings, engine_errors, ensemble = _DOCTR_EXTRACT_REGION(
        evidence, region_path, target_kind
    )
    if not should_run_post_doctr_easyocr_rescue(ensemble):
        return readings, engine_errors, ensemble

    # The baseline extractor may already have routed EasyOCR. Avoid repeating the
    # exact same observation, while still allowing deterministic temporary image
    # variants from the same family to improve glyph recognition.
    if not any(strategy == "easyocr" for strategy, family, _reading in readings if family == "easyocr"):
        _extract_easyocr(evidence, region_path, "easyocr", readings, engine_errors)
        candidate = retry._fuse(readings, target_kind)
        if candidate.declared_usable:
            return readings, engine_errors, candidate

    with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-post-doctr-easyocr-") as td:
        variants = {variant.name: variant for variant in build_fallback_variants(region_path, td)}
        for variant_name in EASYOCR_VARIANT_NAMES:
            variant = variants.get(variant_name)
            if variant is None:
                engine_errors[f"easyocr-{variant_name}"] = "MISSING_PREPROCESS_VARIANT"
                continue
            _extract_easyocr(
                evidence,
                variant.path,
                f"easyocr-{variant_name}",
                readings,
                engine_errors,
            )
            candidate = retry._fuse(readings, target_kind)
            if candidate.declared_usable:
                return readings, engine_errors, candidate

    return readings, engine_errors, retry._fuse(readings, target_kind)


def main() -> int:
    # First widen only docTR routing for this explicitly bounded historical
    # regression cohort. Then layer an EasyOCR fourth-family pass solely on the
    # clean complete 3/4 state produced by that audited docTR route.
    retry.should_run_doctr_rescue = should_run_bounded_doctr_rescue
    retry._extract_region = _extract_region_with_post_doctr_easyocr
    return retry.main()


if __name__ == "__main__":
    raise SystemExit(main())
