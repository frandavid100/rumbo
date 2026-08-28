from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any, Callable

from label_text_extractor import TextExtraction

EASYOCR_EXTRACTOR_VERSION = "1.0.0"
DEFAULT_LANGUAGES = ("es", "en")
_READERS: dict[tuple[str, ...], tuple[Any, str | None]] = {}


class EasyOCRExtractionError(RuntimeError):
    pass


def _default_reader(languages: tuple[str, ...]) -> tuple[Any, str | None]:
    if languages in _READERS:
        return _READERS[languages]
    try:
        import easyocr
    except Exception as exc:  # pragma: no cover - live workflow only
        raise EasyOCRExtractionError(f"EasyOCR is not installed: {exc}") from exc
    try:
        reader = easyocr.Reader(list(languages), gpu=False, verbose=False)
    except Exception as exc:
        raise EasyOCRExtractionError(f"EasyOCR initialization failed: {exc}") from exc
    value = (reader, getattr(easyocr, "__version__", None))
    _READERS[languages] = value
    return value


def _box_anchor(box: Any, fallback: int) -> tuple[float, float]:
    try:
        points = list(box)
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        return min(ys), min(xs)
    except Exception:
        return float(fallback), 0.0


def extract_with_easyocr(
    image_path: str | Path,
    *,
    languages: tuple[str, ...] = DEFAULT_LANGUAGES,
    reader_factory: Callable[[tuple[str, ...]], tuple[Any, str | None]] | None = None,
) -> TextExtraction:
    """Read a label with a third, independent OCR family at catalog-build time.

    EasyOCR is deliberately lazy and CPU-only. Its output is merely another
    observation: Rumbo's deterministic nutrition parser, energy/macro checks and
    independent-engine ensemble still decide whether any value is usable.
    """
    path = Path(image_path)
    if not path.is_file():
        raise EasyOCRExtractionError(f"Image not found: {path}")
    languages = tuple(str(x).strip() for x in languages if str(x).strip())
    if not languages:
        raise EasyOCRExtractionError("At least one OCR language is required")

    if reader_factory is None:
        reader, package_version = _default_reader(languages)
    else:
        try:
            reader, package_version = reader_factory(languages)
        except Exception as exc:
            raise EasyOCRExtractionError(f"EasyOCR initialization failed: {exc}") from exc

    try:
        results = list(reader.readtext(str(path), detail=1, paragraph=False))
    except Exception as exc:
        raise EasyOCRExtractionError(f"EasyOCR failed: {exc}") from exc

    rows: list[tuple[float, float, str, float]] = []
    for index, result in enumerate(results):
        if not isinstance(result, (list, tuple)) or len(result) < 3:
            continue
        box, text, confidence = result[0], str(result[1]).strip(), result[2]
        if not text:
            continue
        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.0
        y, x = _box_anchor(box, index)
        rows.append((y, x, text, max(0.0, min(1.0, confidence))))

    # Preserve approximate reading order. Packaging tables often have several
    # cells on one horizontal band, so coarsen y before sorting left-to-right.
    rows.sort(key=lambda row: (round(row[0] / 12.0), row[1], row[0]))
    return TextExtraction(
        text="\n".join(row[2] for row in rows).strip(),
        confidence=mean(row[3] for row in rows) if rows else 0.0,
        engine="easyocr",
        engine_version=package_version,
        language="+".join(languages),
    )
