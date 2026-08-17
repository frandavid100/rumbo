from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from PIL import Image, ImageEnhance, ImageOps
except ImportError as exc:  # pragma: no cover - dependency is checked in CI
    raise RuntimeError("Pillow is required for label image preprocessing") from exc

PREPROCESS_VERSION = "1.0.0"


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
        for name, box in _crop_boxes(width, height):
            crop = image.crop(box)
            # Enlarge crops so small pack text occupies more pixels for OCR.
            target = crop.resize((int(crop.width * 1.5), int(crop.height * 1.5)), Image.Resampling.LANCZOS)
            path = out / f"crop-{name}.jpg"
            _save_autocontrast(target, path)
            variants.append(ImageVariant(f"crop_{name}", path))
    return variants
