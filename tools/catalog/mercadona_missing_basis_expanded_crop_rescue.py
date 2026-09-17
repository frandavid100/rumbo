from __future__ import annotations

"""Bounded Mercadona rescue for OCR crops that lost the explicit per-100 basis.

This module changes OCR routing only for a preselected, identity/image-bounded
REVIEW cohort. It expands each freshly detected nutrition-table region upward so
the same temporary crop can contain both the explicit ``por 100 g``/``100 ml``
header and the complete macro table. Each expanded crop is evaluated independently:
values, basis, or votes are never fused across crops or across historical runs.

The ordinary parser, energy/macro coherence checks, independent OCR-family
corroboration and DECLARED acceptance contract remain unchanged. Historical
candidate values are diagnostic only and can never be promoted by this module.

Heavy OCR/image dependencies are imported lazily so the dependency-free target
selector can run before a workflow installs the OCR stack.
"""

from math import ceil
from pathlib import Path
from types import SimpleNamespace

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
MISSING_BASIS_REASON = "MISSING_100G_100ML_BASIS"
TOP_EXPANSION_RATIOS = (0.45, 0.80)
SIDE_EXPANSION_RATIO = 0.08
BOTTOM_EXPANSION_RATIO = 0.05
MIN_CURRENT_CORE_FIELDS_FOR_BASIS_DOCTR = 3
MAX_REGIONS_PER_PRODUCT = 2

# Set by main() before the docTR predicate is installed. Leaving this unset keeps
# pure unit tests and dependency-free cohort selection importable.
_ORIGINAL_SHOULD_RUN_DOCTR = None


def select_missing_basis_targets(rows) -> list[dict]:
    """Return only complete 3-of-4 REVIEW diagnostics whose explicit basis is absent.

    Safety blockers are deliberately not converted into positive evidence here.
    This selector only decides whether a tiny cohort deserves a fresh OCR attempt;
    a result is usable only if one new expanded crop independently becomes
    DECLARED under the unchanged downstream contract.
    """
    selected: list[dict] = []
    for row in rows:
        values = row.get("diagnostic_candidate_values") or {}
        reason_prefixes = {str(value) for value in (row.get("reason_prefixes") or [])}
        product_id = str(row.get("product_id") or "").strip()
        ean = str(row.get("ean") or "").strip()
        image_url = str(row.get("image_url") or "").strip()
        if not (
            row.get("canonical_status") == "REVIEW"
            and int(row.get("corroborated_fields") or 0) == 3
            and int(row.get("independent_engine_families") or 0) >= 2
            and row.get("basis") not in {"100_g", "100_ml"}
            and all(values.get(field) is not None for field in CORE)
            and MISSING_BASIS_REASON in reason_prefixes
            and product_id
            and ean
            and image_url
        ):
            continue
        selected.append(row)

    selected.sort(key=lambda row: (len(str(row["product_id"])), str(row["product_id"])))
    return selected


def expanded_box(
    box,
    image_size: tuple[int, int],
    *,
    top_ratio: float,
    side_ratio: float = SIDE_EXPANSION_RATIO,
    bottom_ratio: float = BOTTOM_EXPANSION_RATIO,
) -> tuple[int, int, int, int]:
    """Expand a detected table box, preferentially upward, and clip to the image."""
    x1, y1, x2, y2 = (int(value) for value in box)
    image_width, image_height = (int(value) for value in image_size)
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    side = ceil(width * side_ratio)
    top = ceil(height * top_ratio)
    bottom = ceil(height * bottom_ratio)
    return (
        max(0, x1 - side),
        max(0, y1 - top),
        min(image_width, x2 + side),
        min(image_height, y2 + bottom),
    )


def expanded_basis_ocr_targets(image_path: Path, regions) -> list[tuple[str, Path, object | None]]:
    """Create independent temporary crops that include more label context above.

    The returned targets are separate observations. The production loop calls the
    OCR ensemble independently for each target and never combines fields between
    them. If no visual region exists, retain the ordinary full-back-image fallback.
    """
    if not regions:
        return [("full_back_image", image_path, None)]

    from PIL import Image, ImageOps

    targets: list[tuple[str, Path, object]] = []
    with Image.open(image_path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image_size = image.size
        for region_index, region in enumerate(regions[:MAX_REGIONS_PER_PRODUCT]):
            for top_ratio in TOP_EXPANSION_RATIOS:
                crop_box = expanded_box(region.box, image_size, top_ratio=top_ratio)
                crop = image.crop(crop_box)
                pct = int(round(top_ratio * 100))
                target_path = image_path.parent / f"basis-expanded-{region_index:02d}-top-{pct}.jpg"
                crop.save(target_path, quality=95)
                meta = SimpleNamespace(
                    name=f"basis-expanded-{region_index:02d}-top-{pct}",
                    box=crop_box,
                    score=region.score,
                    horizontal_lines=region.horizontal_lines,
                    vertical_lines=region.vertical_lines,
                    line_density=region.line_density,
                )
                targets.append((f"expanded_visual_region_top_{pct}", target_path, meta))
    return targets


def should_run_missing_basis_doctr_rescue(ensemble) -> bool:
    """Spend docTR when a fresh expanded crop is complete/near-complete but lacks basis.

    Routing is wider than the normal near-safe retry only for missing-basis REVIEW
    observations. It does not make them usable: the final fused observation still
    must satisfy the unmodified parser and DECLARED contract.
    """
    if _ORIGINAL_SHOULD_RUN_DOCTR is not None and _ORIGINAL_SHOULD_RUN_DOCTR(ensemble):
        return True
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return False
    if ensemble.basis in {"100_g", "100_ml"}:
        return False
    nutrition = ensemble.nutrition if isinstance(ensemble.nutrition, dict) else {}
    present = sum(nutrition.get(field) is not None for field in CORE)
    if present < MIN_CURRENT_CORE_FIELDS_FOR_BASIS_DOCTR:
        return False
    if int(ensemble.independent_engine_families or 0) < 1:
        return False
    reasons = {str(reason) for reason in ensemble.reasons}
    return any(reason.startswith(MISSING_BASIS_REASON) for reason in reasons)


def main() -> int:
    # The base loop still downloads the exact first-party image into a temporary
    # directory. Only target geometry and bounded independent-family OCR routing
    # are changed. No image bytes survive the run.
    global _ORIGINAL_SHOULD_RUN_DOCTR

    import mercadona_bounded_doctr_rescue as bounded
    import mercadona_near_safe_doctr_retry as retry
    import mercadona_neural_ocr_wave as base

    _ORIGINAL_SHOULD_RUN_DOCTR = retry.should_run_doctr_rescue
    base._ORIGINAL_EXTRACT_REGION = base._extract_region
    retry.should_run_doctr_rescue = should_run_missing_basis_doctr_rescue
    base._extract_region = bounded._extract_region_with_post_doctr_easyocr
    base._ocr_targets = expanded_basis_ocr_targets
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
