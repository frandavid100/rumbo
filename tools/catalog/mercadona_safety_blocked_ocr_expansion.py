from __future__ import annotations

"""Fresh OCR routing expansion for the final Mercadona safety-blocked residual.

This module deliberately changes *routing only*. It adds docTR and EasyOCR on
additional deterministic crops/upscaled variants of an already identity- and
image-bounded first-party label. Parser rules, energy/macro coherence,
independent-family corroboration, and DECLARED acceptance remain unchanged.
"""

from pathlib import Path
import tempfile

from PIL import Image, ImageEnhance, ImageOps

from label_easyocr_extractor import extract_with_easyocr
from label_image_preprocess import ImageVariant, build_fallback_variants
import mercadona_near_safe_doctr_retry as retry

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
FALLBACK_NAMES = (
    "full_autocontrast",
    "crop_center",
    "crop_left",
    "crop_right",
    "crop_top",
    "crop_bottom",
)
SCALED_NAMES = (
    "full_autocontrast",
    "crop_center",
    "crop_left",
    "crop_top",
    "crop_bottom",
)
HARD_OR_UNDERREAD_PREFIXES = (
    "MULTIPLE_NUTRITION_COLUMNS",
    "ENERGY_MACRO_MISMATCH",
    "OCR_FIELD_CONFLICT",
    "OCR_SAME_ENGINE_CONFLICT",
    "UNCORROBORATED_CORE_FIELDS",
    "MISSING_CORE",
    "LOW_EXTRACTION_CONFIDENCE",
)


def should_expand_safety_blocked_review(ensemble) -> bool:
    """Spend extra OCR only on a bounded REVIEW that cannot already be used."""
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return False
    if ensemble.basis not in {"100_g", "100_ml"}:
        return False
    reasons = [str(reason) for reason in ensemble.reasons]
    return any(
        reason.startswith(prefix)
        for reason in reasons
        for prefix in HARD_OR_UNDERREAD_PREFIXES
    )


def _has_family(readings, family: str) -> bool:
    return any(reading_family == family for _strategy, reading_family, _reading in readings)


def _extract_easyocr(evidence, image_path: Path, strategy: str, readings, engine_errors) -> None:
    try:
        extracted = extract_with_easyocr(image_path)
        readings.append((strategy, "easyocr", retry.base._reading(evidence, extracted)))
    except Exception as exc:
        engine_errors[strategy] = f"{type(exc).__name__}:{exc}"


def _save_scaled_autocontrast(source_path: Path, target_path: Path) -> None:
    with Image.open(source_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image = ImageOps.grayscale(image)
        image = ImageOps.autocontrast(image, cutoff=1)
        image = ImageEnhance.Contrast(image).enhance(1.35)
        image = image.resize(
            (max(1, image.width * 2), max(1, image.height * 2)),
            Image.Resampling.LANCZOS,
        )
        image.save(target_path, quality=95)


def build_scaled_variants(
    image_path: str | Path,
    output_dir: str | Path,
) -> list[ImageVariant]:
    """Upscale deterministic fallback crops without changing their pixels semantically."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    fallback_dir = out / "fallback"
    variants = {variant.name: variant for variant in build_fallback_variants(image_path, fallback_dir)}
    scaled: list[ImageVariant] = []
    for name in SCALED_NAMES:
        variant = variants.get(name)
        if variant is None:
            continue
        target = out / f"scaled-{name}.jpg"
        _save_scaled_autocontrast(variant.path, target)
        scaled.append(ImageVariant(f"scaled_{name}", target))
    return scaled


def _try_fuse(readings, target_kind: str):
    return retry._fuse(readings, target_kind)


def _extract_region(evidence, region_path: Path, target_kind: str):
    readings, engine_errors, ensemble = retry.base._ORIGINAL_EXTRACT_REGION(
        evidence, region_path, target_kind
    )
    if not should_expand_safety_blocked_review(ensemble):
        return readings, engine_errors, ensemble

    # Force a genuinely independent docTR observation even when the baseline
    # REVIEW already carries a hard blocker. This cannot promote by itself: the
    # unchanged ensemble/strict-declared fusion below still enforces the normal
    # acceptance contract.
    retry._extract_doctr(evidence, region_path, "doctr-safety-original", readings, engine_errors)
    candidate = _try_fuse(readings, target_kind)
    if candidate.declared_usable:
        return readings, engine_errors, candidate

    # Add EasyOCR as another independent family if baseline routing did not
    # already do so. Again, no values are manually copied or fused here.
    if not _has_family(readings, "easyocr"):
        _extract_easyocr(evidence, region_path, "easyocr-safety-original", readings, engine_errors)
        candidate = _try_fuse(readings, target_kind)
        if candidate.declared_usable:
            return readings, engine_errors, candidate

    with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-safety-blocked-") as td:
        variants = {variant.name: variant for variant in build_fallback_variants(region_path, td)}
        for name in FALLBACK_NAMES:
            variant = variants.get(name)
            if variant is None:
                continue
            retry._extract_doctr(
                evidence,
                variant.path,
                f"doctr-safety-{name}",
                readings,
                engine_errors,
            )
            candidate = _try_fuse(readings, target_kind)
            if candidate.declared_usable:
                return readings, engine_errors, candidate

            _extract_easyocr(
                evidence,
                variant.path,
                f"easyocr-safety-{name}",
                readings,
                engine_errors,
            )
            candidate = _try_fuse(readings, target_kind)
            if candidate.declared_usable:
                return readings, engine_errors, candidate

        scaled_dir = Path(td) / "scaled"
        for variant in build_scaled_variants(region_path, scaled_dir):
            retry._extract_doctr(
                evidence,
                variant.path,
                f"doctr-{variant.name}",
                readings,
                engine_errors,
            )
            candidate = _try_fuse(readings, target_kind)
            if candidate.declared_usable:
                return readings, engine_errors, candidate

            _extract_easyocr(
                evidence,
                variant.path,
                f"easyocr-{variant.name}",
                readings,
                engine_errors,
            )
            candidate = _try_fuse(readings, target_kind)
            if candidate.declared_usable:
                return readings, engine_errors, candidate

    return readings, engine_errors, _try_fuse(readings, target_kind)


def main() -> int:
    # Preserve the untouched production extractor as the baseline, then layer
    # this routing-only expansion on top for the explicitly bounded cohort.
    retry.base._ORIGINAL_EXTRACT_REGION = retry.base._extract_region
    retry.base._extract_region = _extract_region
    return retry.base.main()


if __name__ == "__main__":
    raise SystemExit(main())
