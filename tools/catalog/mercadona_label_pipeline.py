from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Callable, Iterable
from urllib.request import Request, urlopen

from label_text_extractor import TextExtraction, extract_with_tesseract
from mercadona_label_evidence import LabelImageEvidence
from mercadona_nutrition_reader import (
    OCR_EVIDENCE_LEVEL,
    VisionExtraction,
    MercadonaLabelReading,
    read_evidence,
    to_candidate,
)
from nutrition_ocr_ensemble import ENSEMBLE_VERSION, ParsedOCRReading, OCREnsembleResult, fuse_ocr_readings
from nutrition_resolver import NutritionCandidate, ProductIdentity

PIPELINE_VERSION = "1.3.0"
USER_AGENT = "RumboCatalog/0.1 (label reader; contact: frandavid100@users.noreply.github.com)"


@dataclass(frozen=True)
class LabelPipelineResult:
    reading: MercadonaLabelReading | None
    candidate: NutritionCandidate | None
    status: str
    reason: str | None


@dataclass(frozen=True)
class LabelEnsemblePipelineResult:
    status: str
    candidate: NutritionCandidate | None
    ensemble: OCREnsembleResult | None
    readings: tuple[tuple[str, MercadonaLabelReading], ...]
    reason: str | None


def download_label_image(url: str, target: Path, timeout: float = 12.0) -> None:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
    with urlopen(req, timeout=timeout) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        if not content_type.startswith("image/"):
            raise ValueError(f"Unexpected content type: {content_type or 'unknown'}")
        target.write_bytes(response.read())


def process_label_file(
    evidence: LabelImageEvidence,
    image_path: str | Path,
    *,
    gtin: str | None = None,
    brand: str | None = None,
    format: str | None = None,
    extractor: Callable[[str | Path], TextExtraction] = extract_with_tesseract,
) -> LabelPipelineResult:
    try:
        extracted = extractor(image_path)
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


def _ensemble_candidate(
    evidence: LabelImageEvidence,
    ensemble: OCREnsembleResult,
    *, gtin: str | None, brand: str | None, format: str | None,
) -> NutritionCandidate | None:
    if not ensemble.declared_usable or ensemble.nutrition is None:
        return None
    field_trace = ";".join(
        f"{field.name}={field.value}@{','.join(field.strategies)}[{','.join(field.engine_families)}]"
        for field in ensemble.fields
    )
    return NutritionCandidate(
        identity=ProductIdentity(name=evidence.product_name, brand=brand, gtin=gtin, format=format),
        nutrition=ensemble.nutrition,
        source="Mercadona label OCR ensemble",
        source_url=evidence.image_url,
        source_record_id=f"{evidence.retailer_sku}:image:{evidence.image_index}",
        observed_at=evidence.observed_at,
        upstream_license=None,
        redistribution_allowed=False,
        source_family="Mercadona label",
        evidence_level=OCR_EVIDENCE_LEVEL,
        claim=(f"{OCR_EVIDENCE_LEVEL}; one pack image via OCR ensemble {ENSEMBLE_VERSION}; "
               f"confidence={ensemble.confidence:.3f}; corroborated_fields={ensemble.corroborated_fields}; "
               f"independent_engines={ensemble.independent_engine_families}; {field_trace}"),
    )


def process_label_file_ensemble(
    evidence: LabelImageEvidence,
    image_path: str | Path,
    *,
    strategies: Iterable[tuple[str, Callable[[str | Path], TextExtraction]]],
    gtin: str | None = None,
    brand: str | None = None,
    format: str | None = None,
) -> LabelEnsemblePipelineResult:
    """Run OCR strategies over one image and require independent-engine fusion.

    Multiple layouts/crops from a single OCR engine are useful for recall but
    are correlated observations. They are never allowed to short-circuit the
    ensemble into a usable nutrition record.
    """
    readings: list[tuple[str, MercadonaLabelReading]] = []
    try:
        for name, extractor in strategies:
            extracted = extractor(image_path)
            reading = read_evidence(evidence, VisionExtraction(
                text=extracted.text,
                confidence=extracted.confidence,
                engine=extracted.engine,
                engine_version=extracted.engine_version,
            ))
            readings.append((name, reading))

        ensemble = fuse_ocr_readings(
            ParsedOCRReading(
                name,
                reading.parsed,
                reading.extraction.confidence,
                engine_family=reading.extraction.engine,
            )
            for name, reading in readings
        )
        candidate = _ensemble_candidate(evidence, ensemble, gtin=gtin, brand=brand, format=format)
        if candidate is not None:
            return LabelEnsemblePipelineResult("DECLARED", candidate, ensemble, tuple(readings), None)
        return LabelEnsemblePipelineResult(
            "REVIEW" if ensemble.nutrition else "UNREADABLE",
            None, ensemble, tuple(readings), ",".join(ensemble.reasons) or None,
        )
    except Exception as exc:
        return LabelEnsemblePipelineResult("ERROR", None, None, tuple(readings), f"{type(exc).__name__}:{exc}")


def process_label_image(
    evidence: LabelImageEvidence,
    *,
    gtin: str | None = None,
    brand: str | None = None,
    format: str | None = None,
    timeout: float = 12.0,
    downloader: Callable[[str, Path, float], None] = download_label_image,
    extractor: Callable[[str | Path], TextExtraction] = extract_with_tesseract,
) -> LabelPipelineResult:
    try:
        with tempfile.TemporaryDirectory(prefix="rumbo-label-") as td:
            path = Path(td) / "label-image"
            downloader(evidence.image_url, path, timeout)
            return process_label_file(
                evidence, path, gtin=gtin, brand=brand, format=format, extractor=extractor
            )
    except Exception as exc:
        return LabelPipelineResult(None, None, "ERROR", f"{type(exc).__name__}:{exc}")
