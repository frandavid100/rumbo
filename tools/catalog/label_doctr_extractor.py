from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from statistics import mean
from typing import Any, Callable

from label_text_extractor import TextExtraction

DOCTR_EXTRACTOR_VERSION = "1.0.0"
DOCTR_DETECTION_ARCH = "fast_tiny"
DOCTR_RECOGNITION_ARCH = "crnn_mobilenet_v3_small"
_PREDICTOR: tuple[Any, str | None] | None = None


class DocTRExtractionError(RuntimeError):
    pass


def _package_version() -> str | None:
    try:
        return version("python-doctr")
    except PackageNotFoundError:  # pragma: no cover - live dependency path
        return None


def _default_predictor() -> tuple[Any, str | None]:
    global _PREDICTOR
    if _PREDICTOR is not None:
        return _PREDICTOR
    try:
        from doctr.models import ocr_predictor
    except Exception as exc:  # pragma: no cover - live workflow only
        raise DocTRExtractionError(f"docTR is not installed: {exc}") from exc
    try:
        predictor = ocr_predictor(
            det_arch=DOCTR_DETECTION_ARCH,
            reco_arch=DOCTR_RECOGNITION_ARCH,
            pretrained=True,
            assume_straight_pages=True,
            preserve_aspect_ratio=True,
        )
    except Exception as exc:
        raise DocTRExtractionError(f"docTR initialization failed: {exc}") from exc
    _PREDICTOR = (predictor, _package_version())
    return _PREDICTOR


def _default_document_loader(path: Path):
    try:
        from doctr.io import DocumentFile
    except Exception as exc:  # pragma: no cover - live workflow only
        raise DocTRExtractionError(f"docTR is not installed: {exc}") from exc
    return DocumentFile.from_images(str(path))


def extract_with_doctr(
    image_path: str | Path,
    *,
    predictor_factory: Callable[[], tuple[Any, str | None]] | None = None,
    document_loader: Callable[[Path], Any] | None = None,
) -> TextExtraction:
    """Read a label with docTR as an additional independent OCR family.

    docTR is used only as an observation source. Rumbo's deterministic nutrition
    parser and ensemble still decide whether values are usable. Model weights are
    loaded lazily and image bytes remain temporary in the caller's workspace.
    """
    path = Path(image_path)
    if not path.is_file():
        raise DocTRExtractionError(f"Image not found: {path}")

    factory = predictor_factory or _default_predictor
    loader = document_loader or _default_document_loader
    try:
        predictor, package_version = factory()
        document = loader(path)
        result = predictor(document)
    except DocTRExtractionError:
        raise
    except Exception as exc:
        raise DocTRExtractionError(f"docTR failed: {exc}") from exc

    lines: list[str] = []
    confidences: list[float] = []
    try:
        pages = list(getattr(result, "pages", ()) or ())
        for page in pages:
            for block in list(getattr(page, "blocks", ()) or ()):
                for line in list(getattr(block, "lines", ()) or ()):
                    words = list(getattr(line, "words", ()) or ())
                    values = []
                    for word in words:
                        value = str(getattr(word, "value", "") or "").strip()
                        if not value:
                            continue
                        values.append(value)
                        try:
                            confidence = float(getattr(word, "confidence", 0.0) or 0.0)
                        except Exception:
                            confidence = 0.0
                        confidences.append(max(0.0, min(1.0, confidence)))
                    if values:
                        lines.append(" ".join(values))
    except Exception as exc:
        raise DocTRExtractionError(f"docTR result parsing failed: {exc}") from exc

    return TextExtraction(
        text="\n".join(lines).strip(),
        confidence=mean(confidences) if confidences else 0.0,
        engine=f"doctr-{DOCTR_DETECTION_ARCH}-{DOCTR_RECOGNITION_ARCH}",
        engine_version=package_version,
        language="multilingual-latin",
    )
