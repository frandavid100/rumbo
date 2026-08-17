from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Callable
from urllib.request import Request, urlopen

from label_text_extractor import TextExtraction, extract_with_tesseract
from mercadona_label_evidence import LabelImageEvidence
from mercadona_nutrition_reader import VisionExtraction, MercadonaLabelReading, read_evidence, to_candidate
from nutrition_resolver import NutritionCandidate

PIPELINE_VERSION = "1.0.0"
USER_AGENT = "RumboCatalog/0.1 (label reader; contact: frandavid100@users.noreply.github.com)"


@dataclass(frozen=True)
class LabelPipelineResult:
    reading: MercadonaLabelReading | None
    candidate: NutritionCandidate | None
    status: str
    reason: str | None


def _download(url: str, target: Path, timeout: float) -> None:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
    with urlopen(req, timeout=timeout) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        if not content_type.startswith("image/"):
            raise ValueError(f"Unexpected content type: {content_type or 'unknown'}")
        target.write_bytes(response.read())


def process_label_image(
    evidence: LabelImageEvidence,
    *,
    gtin: str | None = None,
    brand: str | None = None,
    format: str | None = None,
    timeout: float = 20.0,
    downloader: Callable[[str, Path, float], None] = _download,
    extractor: Callable[[str | Path], TextExtraction] = extract_with_tesseract,
) -> LabelPipelineResult:
    """Download one Mercadona pack image, OCR it and validate nutrition.

    Source images are transient build inputs: they are not written to the
    published catalog and are deleted when this function returns.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="rumbo-label-") as td:
            path = Path(td) / "label-image"
            downloader(evidence.image_url, path, timeout)
            extracted = extractor(path)
            vision = VisionExtraction(
                text=extracted.text,
                confidence=extracted.confidence,
                engine=extracted.engine,
                engine_version=extracted.engine_version,
            )
            reading = read_evidence(evidence, vision)
            candidate = to_candidate(reading, gtin=gtin, brand=brand, format=format)
            if candidate is not None:
                return LabelPipelineResult(reading, candidate, "DECLARED", None)
            return LabelPipelineResult(reading, None, reading.parsed.status,
                                       ",".join(reading.parsed.reasons) or None)
    except Exception as exc:
        return LabelPipelineResult(None, None, "ERROR", f"{type(exc).__name__}:{exc}")
