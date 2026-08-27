from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from label_text_extractor import TextExtraction
from mercadona_label_evidence import LabelImageEvidence
from mercadona_label_pipeline import process_label_file_ensemble
from nutrition_resolver import NutritionCandidate
from nutrition_visual_table_detector import VisualTableRegion, detect_visual_table_regions

IMPORTER_VERSION = "1.3.0"


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


def prepare_right_angle_rotations(
    image_path: str | Path,
    work_dir: str | Path,
) -> list[tuple[str, Path]]:
    """Create temporary right-angle views without persisting source images.

    Mercadona rear-label photos are not guaranteed to have their nutrition table
    upright. OCR orientation heuristics are intentionally disabled, so explicitly
    try only the three lossless right-angle alternatives before visual cropping.
    Pillow is imported lazily so ordinary catalog validation does not depend on it.
    """
    from PIL import Image, ImageOps

    out = Path(work_dir)
    out.mkdir(parents=True, exist_ok=True)
    rotations: list[tuple[str, Path]] = []
    with Image.open(image_path) as raw:
        image = ImageOps.exif_transpose(raw)
        for angle in (90, 180, 270):
            path = out / f"rotated-{angle}.png"
            image.rotate(angle, expand=True).save(path, format="PNG", optimize=True)
            rotations.append((str(angle), path))
    return rotations


def import_from_label_file(
    evidence: LabelImageEvidence,
    image_path: str | Path,
    *,
    gtin: str | None,
    brand: str | None,
    tesseract_strategies: Iterable[tuple[str, Callable[[str | Path], TextExtraction]]],
    neural_extractor: Callable[[str | Path], TextExtraction] | None = None,
    rotation_preparer: Callable[[str | Path, str | Path], list[tuple[str, Path]]] = prepare_right_angle_rotations,
    region_detector: Callable[[str | Path, str | Path], list[VisualTableRegion]] = detect_visual_table_regions,
    work_dir: str | Path,
) -> NutritionImportResult:
    """Mercadona label import with independent-engine acceptance.

    Tesseract-only passes are useful for locating/parsing text but are correlated
    observations and cannot create usable OCR nutrition. If the original image
    already yields a plausible Tesseract reading, corroborate that same image
    with the independent neural OCR family. If it does not, try right-angle
    rotations before relying on visual table crops. No rotation can relax parser,
    coherence or independent-engine acceptance rules.
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

    # A REVIEW here means Tesseract found enough nutrition structure to make an
    # independent read worthwhile. Do not spend neural inference on an original
    # image that Tesseract found wholly unreadable: there would be nothing
    # independent with which to corroborate neural values anyway.
    if original.status == "REVIEW" and neural_extractor is not None:
        strategies = list(tesseract_strategies)
        strategies.append(("paddleocr:neural", neural_extractor))
        combined_original = process_label_file_ensemble(
            evidence, image_path, gtin=gtin, brand=brand, strategies=tuple(strategies),
        )
        attempts.append(NutritionImportAttempt(
            "INDEPENDENT_OCR_ORIGINAL", None, combined_original.status, combined_original.reason
        ))
        if combined_original.candidate is not None:
            return NutritionImportResult("DECLARED", combined_original.candidate, tuple(attempts), None)

    # A large fraction of first-party rear-label images are sideways or inverted.
    # Probe rotations with cheap Tesseract first; only pay for the independent
    # neural family when a rotated image reaches REVIEW and can be corroborated.
    try:
        rotations = rotation_preparer(image_path, Path(work_dir) / "rotations")
    except Exception as exc:
        attempts.append(NutritionImportAttempt(
            "ROTATION_PREP", None, "ERROR", f"{type(exc).__name__}:{exc}"
        ))
        rotations = []

    for rotation_name, rotation_path in rotations:
        rotated = process_label_file_ensemble(
            evidence, rotation_path, gtin=gtin, brand=brand, strategies=tesseract_strategies,
        )
        attempts.append(NutritionImportAttempt(
            f"TESSERACT_ROTATED_{rotation_name}", rotation_name, rotated.status, rotated.reason
        ))
        if rotated.candidate is not None:
            return NutritionImportResult("DECLARED", rotated.candidate, tuple(attempts), None)
        if rotated.status != "REVIEW" or neural_extractor is None:
            continue

        strategies = list(tesseract_strategies)
        strategies.append(("paddleocr:neural", neural_extractor))
        combined_rotated = process_label_file_ensemble(
            evidence, rotation_path, gtin=gtin, brand=brand, strategies=tuple(strategies),
        )
        attempts.append(NutritionImportAttempt(
            f"INDEPENDENT_OCR_ROTATED_{rotation_name}", rotation_name,
            combined_rotated.status, combined_rotated.reason,
        ))
        if combined_rotated.candidate is not None:
            return NutritionImportResult("DECLARED", combined_rotated.candidate, tuple(attempts), None)

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
