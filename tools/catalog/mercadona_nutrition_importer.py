from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from label_text_extractor import TextExtraction
from mercadona_label_evidence import LabelImageEvidence
from mercadona_label_pipeline import process_label_file_ensemble
from nutrition_resolver import NutritionCandidate
from nutrition_visual_table_detector import VisualTableRegion, detect_visual_table_regions

IMPORTER_VERSION = "1.1.0"


@dataclass(frozen=True)
class NutritionImportAttempt:
    stage: str
    region: str | None
    status: str
    reason: str | None


@dataclass(frozen=True)
class NutritionImportResult:
    status: str
    candidate: NutritionCandidate | None
    attempts: tuple[NutritionImportAttempt, ...]
    reason: str | None


def import_from_label_file(
    evidence: LabelImageEvidence,
    image_path: str | Path,
    *,
    gtin: str | None,
    brand: str | None,
    tesseract_strategies: Iterable[tuple[str, Callable[[str | Path], TextExtraction]]],
    neural_extractor: Callable[[str | Path], TextExtraction] | None = None,
    region_detector: Callable[[str | Path, str | Path], list[VisualTableRegion]] = detect_visual_table_regions,
    work_dir: str | Path,
) -> NutritionImportResult:
    """Mercadona label import with independent-engine acceptance.

    Tesseract-only passes are useful for locating/parsing text but are correlated
    observations and cannot create usable OCR nutrition. On each visually
    detected table region, the neural reader is fused with Tesseract so only
    agreement between independent OCR engine families can become DECLARED.
    """
    attempts: list[NutritionImportAttempt] = []
    tesseract_strategies = tuple(tesseract_strategies)

    original = process_label_file_ensemble(
        evidence, image_path, gtin=gtin, brand=brand, strategies=tesseract_strategies,
    )
    attempts.append(NutritionImportAttempt("TESSERACT_ORIGINAL", None, original.status, original.reason))
    if original.candidate is not None:
        # Kept for compatibility with any future tesseract_strategies that
        # genuinely contain more than one independent OCR family.
        return NutritionImportResult("DECLARED", original.candidate, tuple(attempts), None)

    regions = region_detector(image_path, Path(work_dir) / "visual-regions")
    for region in regions[:3]:
        strategies = list(tesseract_strategies)
        if neural_extractor is not None:
            strategies.append(("paddleocr:neural", neural_extractor))
        combined = process_label_file_ensemble(
            evidence, region.path, gtin=gtin, brand=brand, strategies=tuple(strategies),
        )
        attempts.append(NutritionImportAttempt(
            "INDEPENDENT_OCR_VISUAL_REGION", region.name, combined.status, combined.reason
        ))
        if combined.candidate is not None:
            return NutritionImportResult("DECLARED", combined.candidate, tuple(attempts), None)

    status = "REVIEW" if any(a.status == "REVIEW" for a in attempts) else "UNRESOLVED"
    reason = "NO_INDEPENDENTLY_CORROBORATED_LABEL_READING"
    return NutritionImportResult(status, None, tuple(attempts), reason)
