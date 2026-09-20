from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Iterable

try:
    from PIL import Image, ImageEnhance, ImageOps
except ImportError as exc:  # pragma: no cover - dependency is checked in CI
    raise RuntimeError("Pillow is required for label image preprocessing") from exc

PREPROCESS_VERSION = "1.1.1"
PADDLE_SAFE_MAX_SIDE = 3900
NATIVE_TILE_OVERLAP_FRACTION = 0.15
LEGACY_CROP_ENLARGE_FACTOR = 1.5


@dataclass(frozen=True)
class ImageVariant:
    name: str
    path: Path


def _save_autocontrast(source: Image.Image, path: Path) -> None:
    gray = ImageOps.grayscale(source)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.35)
    gray.save(path, quality=95)


def _crop_boxes(width: int, height: int) -> list[tuple[str, tuple[int, int, int, int]]]:
    # Overlapping regions. They enlarge text without assuming a fixed table
    # position; intended only as fallback after whole-image OCR fails.
    mx, my = int(width * 0.08), int(height * 0.08)
    cx, cy = width // 2, height // 2
    ox, oy = int(width * 0.12), int(height * 0.12)
    return [
        ("center", (mx, my, width - mx, height - my)),
        ("left", (mx, my, min(width, cx + ox), height - my)),
        ("right", (max(0, cx - ox), my, width - mx, height - my)),
        ("top", (mx, my, width - mx, min(height, cy + oy))),
        ("bottom", (mx, max(0, cy - oy), width - mx, height - my)),
    ]


def _axis_native_intervals(
    length: int,
    *,
    max_side: int = PADDLE_SAFE_MAX_SIDE,
    overlap_fraction: float = NATIVE_TILE_OVERLAP_FRACTION,
) -> list[tuple[int, int]]:
    if length <= max_side:
        return [(0, length)]

    # Split before PaddleOCR has to apply its own max-side downscale.  The number
    # of base segments deliberately leaves room for a symmetric overlap margin,
    # so every emitted tile remains below max_side while nearby rows are repeated
    # across a boundary.  Pixels stay at the first-party image's native scale.
    effective_span = max_side * (1.0 - overlap_fraction)
    segment_count = max(2, math.ceil(length / effective_span))
    boundaries = [round(index * length / segment_count) for index in range(segment_count + 1)]
    intervals: list[tuple[int, int]] = []
    for index in range(segment_count):
        start, end = boundaries[index], boundaries[index + 1]
        base = max(1, end - start)
        margin = max(1, round(base * overlap_fraction / 2.0))
        left = max(0, start - margin)
        right = min(length, end + margin)
        if right - left > max_side:
            # Defensive cap for unusual rounding/very small max_side fixtures.
            center = (left + right) // 2
            half = max_side // 2
            left = max(0, min(length - max_side, center - half))
            right = min(length, left + max_side)
        intervals.append((left, right))
    return intervals


def _native_tile_boxes(
    width: int,
    height: int,
) -> list[tuple[str, tuple[int, int, int, int]]]:
    if max(width, height) <= PADDLE_SAFE_MAX_SIDE:
        return []
    xs = _axis_native_intervals(width)
    ys = _axis_native_intervals(height)
    boxes: list[tuple[str, tuple[int, int, int, int]]] = []
    for row, (top, bottom) in enumerate(ys):
        for col, (left, right) in enumerate(xs):
            boxes.append((f"native_tile_r{row}_c{col}", (left, top, right, bottom)))
    return boxes


def _resize_legacy_crop_for_detector(crop: Image.Image) -> Image.Image:
    """Enlarge a crop only while keeping its longest side below Paddle's cap.

    PP-OCRv6 otherwise emits a max_side_limit warning and immediately shrinks the
    fixed 1.5x fallback. Keeping the preprocessed image below that boundary makes
    the scale deterministic and avoids spending OCR work on pixels that Paddle
    will discard internally. Oversized unusual inputs are explicitly reduced here;
    their native-resolution tiles are attempted earlier by the rescue route.
    """
    longest = max(crop.width, crop.height)
    if longest <= 0:
        return crop
    scale = min(LEGACY_CROP_ENLARGE_FACTOR, PADDLE_SAFE_MAX_SIDE / float(longest))
    if abs(scale - 1.0) < 1e-9:
        return crop
    width = max(1, round(crop.width * scale))
    height = max(1, round(crop.height * scale))
    return crop.resize((width, height), Image.Resampling.LANCZOS)


def build_fallback_variants(image_path: str | Path, output_dir: str | Path) -> list[ImageVariant]:
    """Create deterministic OCR fallback variants from one already-downloaded image.

    No variant is evidence by itself. Every extracted value must still pass the
    normal parser/ensemble and energy-macro validation.
    """
    source_path = Path(image_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    variants: list[ImageVariant] = []
    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        full = out / "full-autocontrast.jpg"
        _save_autocontrast(image, full)
        variants.append(ImageVariant("full_autocontrast", full))

        width, height = image.size
        for name, box in _native_tile_boxes(width, height):
            tile = image.crop(box)
            path = out / f"{name.replace('_', '-')}.jpg"
            _save_autocontrast(tile, path)
            variants.append(ImageVariant(name, path))

        for name, box in _crop_boxes(width, height):
            crop = image.crop(box)
            target = _resize_legacy_crop_for_detector(crop)
            path = out / f"crop-{name}.jpg"
            _save_autocontrast(target, path)
            variants.append(ImageVariant(f"crop_{name}", path))
    return variants
