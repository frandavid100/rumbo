from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any, Callable

from label_text_extractor import TextExtraction

NEURAL_EXTRACTOR_VERSION = "1.0.0"
DEFAULT_OCR_VERSION = "PP-OCRv6"
DEFAULT_LANGUAGE = "es"


class NeuralExtractionError(RuntimeError):
    pass


def _payload(result: Any) -> dict:
    value = getattr(result, "json", result)
    if callable(value):
        value = value()
    if not isinstance(value, dict):
        raise NeuralExtractionError(f"Unexpected PaddleOCR result type: {type(value).__name__}")
    if isinstance(value.get("res"), dict):
        return value["res"]
    return value


def _ordered_lines(payload: dict) -> tuple[list[str], list[float]]:
    texts = list(payload.get("rec_texts") or [])
    scores = [float(x) for x in (payload.get("rec_scores") or [])]
    boxes = list(payload.get("rec_boxes") or [])

    rows = []
    for index, text in enumerate(texts):
        text = str(text).strip()
        if not text:
            continue
        score = scores[index] if index < len(scores) else 0.0
        if index < len(boxes) and len(boxes[index]) >= 4:
            x1, y1, x2, y2 = [float(v) for v in boxes[index][:4]]
            rows.append((y1, x1, text, score))
        else:
            rows.append((float(index), 0.0, text, score))
    rows.sort(key=lambda x: (round(x[0] / 12.0), x[1], x[0]))
    return [x[2] for x in rows], [x[3] for x in rows]


def extract_with_paddleocr(
    image_path: str | Path,
    *,
    language: str = DEFAULT_LANGUAGE,
    ocr_version: str = DEFAULT_OCR_VERSION,
    pipeline_factory: Callable[..., Any] | None = None,
) -> TextExtraction:
    """Read a focused label crop using PaddleOCR at catalog-build time.

    The neural OCR output is still only an observation. It must pass Rumbo's
    deterministic nutrition parser and coherence checks before becoming DECLARED.
    The import is lazy so normal catalog CI does not require PaddleOCR.
    """
    path = Path(image_path)
    if not path.is_file():
        raise NeuralExtractionError(f"Image not found: {path}")

    if pipeline_factory is None:
        try:
            import paddleocr
            from paddleocr import PaddleOCR
        except Exception as exc:  # pragma: no cover - exercised only in live workflow
            raise NeuralExtractionError(f"PaddleOCR is not installed: {exc}") from exc
        package_version = getattr(paddleocr, "__version__", None)
        pipeline_factory = PaddleOCR
    else:
        package_version = "fixture"

    try:
        pipeline = pipeline_factory(
            lang=language,
            ocr_version=ocr_version,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        results = list(pipeline.predict(str(path)))
    except Exception as exc:
        raise NeuralExtractionError(f"PaddleOCR failed: {exc}") from exc

    all_lines: list[str] = []
    all_scores: list[float] = []
    for result in results:
        lines, scores = _ordered_lines(_payload(result))
        all_lines.extend(lines)
        all_scores.extend(scores)

    return TextExtraction(
        text="\n".join(all_lines).strip(),
        confidence=max(0.0, min(1.0, mean(all_scores))) if all_scores else 0.0,
        engine=f"paddleocr-{ocr_version}",
        engine_version=package_version,
        language=language,
    )
