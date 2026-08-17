from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from label_text_extractor import TextExtraction
from mercadona_label_evidence import LabelImageEvidence
from mercadona_label_pipeline import LabelEnsemblePipelineResult, process_label_file_ensemble
from nutrition_resolver import NutritionCandidate
from nutrition_visual_table_detector import VisualTableRegion, detect_visual_table_regions

IMPORTER_VERSION = "1.0.0"


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
    """Formal Mercadona label fallback: cheap OCR first, neural OCR only on visual regions.

    Acceptance remains delegated to Rumbo's deterministic parser/ensemble. The
    neural reader never writes nutrition directly.
    """
    attempts: list[NutritionImportAttempt] = []
    original = process_label_file_ensemble(
        evidence, image_path, gtin=gtin, brand=brand, strategies=tesseract_strategies,
    )
    attempts.append(NutritionImportAttempt("TESSERACT_ORIGINAL", None, original.status, original.reason))
    if original.candidate is not None:
        return NutritionImportResult("DECLARED", original.candidate, tuple(attempts), None)

    regions = region_detector(image_path, Path(work_dir) / "visual-regions")
    for region in regions[:3]:
        cheap = process_label_file_ensemble(
            evidence, region.path, gtin=gtin, brand=brand, strategies=tesseract_strategies,
        )
        attempts.append(NutritionImportAttempt("TESSERACT_VISUAL_REGION", region.name, cheap.status, cheap.reason))
        if cheap.candidate is not None:
            return NutritionImportResult("DECLARED", cheap.candidate, tuple(attempts), None)

        if neural_extractor is None:
            continue
        neural = process_label_file_ensemble(
            evidence, region.path, gtin=gtin, brand=brand,
            strategies=(("neural", neural_extractor),),
        )
        attempts.append(NutritionImportAttempt("NEURAL_VISUAL_REGION", region.name, neural.status, neural.reason))
        if neural.candidate is not None:
            return NutritionImportResult("DECLARED", neural.candidate, tuple(attempts), None)

    status = "REVIEW" if any(a.status == "REVIEW" for a in attempts) else "UNRESOLVED"
    reason = "NO_ACCEPTED_LABEL_READING"
    return NutritionImportResult(status, None, tuple(attempts), reason)
