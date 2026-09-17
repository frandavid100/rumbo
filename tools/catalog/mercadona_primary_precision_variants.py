from __future__ import annotations

"""Lossless high-resolution primary-column crops for bounded Mercadona OCR retries.

These variants change image preprocessing only. They never alter parsed values,
merge observations, or relax any nutrition/ensemble acceptance rule. Callers are
expected to create them inside a temporary directory and to treat each crop as
an independent OCR observation.
"""

from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from label_image_preprocess import ImageVariant


PRIMARY_COLUMN_WIDTH_RATIOS = (0.42, 0.50)
PRIMARY_COLUMN_SCALE = 3.0


def _save_precision_variant(source: Image.Image, path: Path) -> None:
    """Preserve tiny decimal points without introducing thresholded glyph shapes."""
    gray = ImageOps.grayscale(source)
    gray = ImageOps.autocontrast(gray, cutoff=0)
    gray = ImageEnhance.Contrast(gray).enhance(1.15)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1.0, percent=175, threshold=1))
    gray.save(path, format="PNG", optimize=False)


def build_precision_primary_column_variants(
    image_path: str | Path,
    output_dir: str | Path,
    *,
    width_ratios: tuple[float, ...] | None = None,
) -> list[ImageVariant]:
    """Create deterministic lossless 3x left-column crops of a bounded label.

    The default crop ratios deliberately match the already-audited primary-column
    rescue. ``width_ratios`` exists for diagnostic-only probes that need to test a
    slightly wider crop without changing the production defaults. Only the
    rasterization changes: 3x Lanczos, light contrast enhancement, unsharp
    masking, and lossless PNG. No crop is combined with another crop.
    """
    source_path = Path(image_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    ratios = PRIMARY_COLUMN_WIDTH_RATIOS if width_ratios is None else tuple(width_ratios)
    if not ratios or any(ratio <= 0 or ratio > 1 for ratio in ratios):
        raise ValueError("width_ratios must contain only values in (0, 1]")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    variants: list[ImageVariant] = []
    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        width, height = image.size
        for ratio in ratios:
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
            path = out / f"primary-precision-left-{ratio_pct}.png"
            _save_precision_variant(target, path)
            variants.append(ImageVariant(f"primary_precision_left_{ratio_pct}", path))

    return variants
