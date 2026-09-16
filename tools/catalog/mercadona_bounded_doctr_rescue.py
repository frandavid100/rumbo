from __future__ import annotations

"""Bounded docTR + EasyOCR rescue for safe historical Mercadona REVIEW regressions.

This module changes OCR routing only. It never relaxes the parser, ensemble,
energy/macro coherence, independent-family corroboration, or provenance gates.
The caller is responsible for supplying a cohort whose historical identity and
first-party image have already been revalidated exactly.
"""

from pathlib import Path
import tempfile

from PIL import Image, ImageEnhance, ImageOps

from label_easyocr_extractor import extract_with_easyocr
from label_image_preprocess import ImageVariant, build_fallback_variants
import mercadona_near_safe_doctr_retry as retry

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
MIN_PRESENT_CORE_FIELDS = 2
MIN_BOUNDED_HISTORICAL_PRESENT_CORE_FIELDS = 1
MIN_POST_DOCTR_ENGINE_FAMILIES_FOR_EASYOCR = 2
MIN_POST_DOCTR_CORROBORATED_FIELDS_FOR_EASYOCR = 1
EASYOCR_VARIANT_NAMES = (
    "full_autocontrast",
    "crop_center",
    "crop_left",
    "crop_right",
    "crop_top",
    "crop_bottom",
)
PRIMARY_COLUMN_WIDTH_RATIOS = (0.42, 0.50)
PRIMARY_COLUMN_SCALE = 2.0

# Keep a stable handle to the audited docTR extraction path before main() swaps
# the production extractor to the wrapper below.
_DOCTR_EXTRACT_REGION = retry._extract_region


def should_run_bounded_doctr_rescue(ensemble) -> bool:
    """Add docTR to a clean but incomplete REVIEW observation.

    The ordinary near-safe retry is intentionally restricted to complete 4-field
    candidates. This bounded rescue is for products that were previously
    DECLARED and later regressed to a non-contradictory REVIEW. It may spend an
    additional OCR family on a current extraction with at least two core fields.
    For this already identity/image-bounded historical cohort, a one-field
    extraction is also eligible only when the ensemble explicitly reports the
    remaining fields as MISSING_CORE. That widens OCR routing, not acceptance:
    the unchanged downstream ensemble must still satisfy the normal DECLARED
    contract independently.
    """
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return False
    if ensemble.basis not in {"100_g", "100_ml"}:
        return False
    nutrition = ensemble.nutrition if isinstance(ensemble.nutrition, dict) else {}
    present = sum(nutrition.get(field) is not None for field in CORE)
    reasons = [str(reason) for reason in ensemble.reasons]
    if present < MIN_PRESENT_CORE_FIELDS:
        if present < MIN_BOUNDED_HISTORICAL_PRESENT_CORE_FIELDS:
            return False
        if not any(reason.startswith("MISSING_CORE:") for reason in reasons):
            return False
    if int(ensemble.independent_engine_families or 0) < 1:
        return False
    return not any(
        reason.startswith(prefix)
        for reason in reasons
        for prefix in retry.rescue.HARD_BLOCKING_PREFIXES
    )


def should_run_post_doctr_easyocr_rescue(ensemble) -> bool:
    """Spend EasyOCR on a clean complete tuple that docTR left under-corroborated.

    A bounded docTR pass can recover all four core values while leaving one or
    more of them supported by too few independent OCR families. In that exact
    state EasyOCR is useful as a genuinely independent third or fourth OCR
    family. Route only complete tuples with an explicit per-100 basis, at least
    two existing engine families, at least one already-corroborated core field,
    and no hard blocker. This still does not change acceptance: the ordinary
    ensemble must independently corroborate all four fields before the
    observation can become DECLARED.
    """
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return False
    if ensemble.basis not in {"100_g", "100_ml"}:
        return False
    nutrition = ensemble.nutrition if isinstance(ensemble.nutrition, dict) else {}
    if any(nutrition.get(field) is None for field in CORE):
        return False
    if int(ensemble.independent_engine_families or 0) < MIN_POST_DOCTR_ENGINE_FAMILIES_FOR_EASYOCR:
        return False
    corroborated = int(ensemble.corroborated_fields or 0)
    if not (MIN_POST_DOCTR_CORROBORATED_FIELDS_FOR_EASYOCR <= corroborated < len(CORE)):
        return False
    reasons = [str(reason) for reason in ensemble.reasons]
    if "UNCORROBORATED_CORE_FIELDS" not in reasons:
        return False
    return not any(
        reason.startswith(prefix)
        for reason in reasons
        for prefix in retry.rescue.HARD_BLOCKING_PREFIXES
    )


def _save_primary_column_variant(source: Image.Image, path: Path) -> None:
    gray = ImageOps.grayscale(source)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.35)
    gray.save(path, quality=95)


def build_bounded_primary_column_variants(
    image_path: str | Path,
    output_dir: str | Path,
) -> list[ImageVariant]:
    """Create deterministic left-column crops for an already-bounded label region.

    Some Mercadona labels print a primary per-100-g column beside a prepared-
    serving column. Whole-region OCR can interleave both numeric cells and leave
    one macro under-corroborated even though the primary value is visible. These
    temporary crops isolate only the left portion of the same first-party label;
    they do not infer which value is correct and do not alter parser or ensemble
    acceptance. The crop observations remain EasyOCR-family evidence and must
    still agree independently with another OCR family.
    """
    source_path = Path(image_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    variants: list[ImageVariant] = []
    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        width, height = image.size
        for ratio in PRIMARY_COLUMN_WIDTH_RATIOS:
            crop_width = max(1, min(width, int(width * ratio)))
            crop = image.crop((0, 0, crop_width, height))
            target = crop.resize(
                (
                    max(1, int(crop.width * PRIMARY_COLUMN_SCALE)),
                    max(1, int(crop.height * PRIMARY_COLUMN_SCALE)),
                ),
                Image.Resampling.LANCZOS,
            )
            ratio_pct = int(round(ratio * 100))
            path = out / f"primary-left-{ratio_pct}.jpg"
            _save_primary_column_variant(target, path)
            variants.append(ImageVariant(f"primary_left_{ratio_pct}", path))
    return variants


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
        # Try the primary-column isolation first. If it supplies the one missing
        # corroboration, return before broad crops can introduce correlated
        # secondary-column noise from the same EasyOCR family.
        primary_dir = Path(td) / "primary-column"
        for variant in build_bounded_primary_column_variants(region_path, primary_dir):
            _extract_easyocr(
                evidence,
                variant.path,
                f"easyocr-{variant.name}",
                readings,
                engine_errors,
            )
            candidate = retry._fuse(readings, target_kind)
            if candidate.declared_usable:
                return readings, engine_errors, candidate

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
    # regression cohort. Then layer an EasyOCR independent-family pass solely on
    # a clean complete under-corroborated state produced by that audited route.
    retry.should_run_doctr_rescue = should_run_bounded_doctr_rescue
    retry._extract_region = _extract_region_with_post_doctr_easyocr
    return retry.main()


if __name__ == "__main__":
    raise SystemExit(main())
