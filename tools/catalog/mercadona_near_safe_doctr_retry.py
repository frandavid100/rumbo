from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

from label_doctr_extractor import (
    DOCTR_DETECTION_ARCH,
    DOCTR_RECOGNITION_ARCH,
    extract_with_doctr,
)
from label_easyocr_extractor import extract_with_easyocr
from label_image_preprocess import build_fallback_variants
import mercadona_near_safe_variant_rescue as rescue
import mercadona_neural_ocr_wave as base

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
DEFAULT_LIMIT = 16
DOCTR_VARIANT_NAMES = (
    "full_autocontrast",
    "crop_center",
    "crop_left",
    "crop_right",
    "crop_top",
    "crop_bottom",
)
EXTRA_BLOCKING_PREFIXES = (
    "OCR_BOUNDED_CORE_VALUE",
)


def _token(value) -> str:
    return str(value or "").strip()


def _missing_core_fields(ensemble) -> list[str]:
    nutrition = ensemble.nutrition or {}
    return [field for field in CORE if field not in nutrition]


def should_run_doctr_rescue(ensemble) -> bool:
    """Route extra independent OCR only for clean bounded REVIEW observations.

    Two shapes are allowed without changing acceptance thresholds:
    * complete tuples with weak cross-family corroboration; or
    * exactly-3/4 tuples with one genuinely missing core row.

    The missing-core route only spends extra OCR work. It never fills the missing
    value from history or arithmetic: a usable result must still recover all four
    fields in the same fresh observation and satisfy the ordinary ensemble gate.
    """
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return False
    if ensemble.basis not in {"100_g", "100_ml"}:
        return False
    if not ensemble.nutrition:
        return False
    if ensemble.independent_engine_families < 2:
        return False

    reasons = tuple(str(reason) for reason in ensemble.reasons)
    if any(
        reason.startswith(prefix)
        for reason in reasons
        for prefix in (*rescue.HARD_BLOCKING_PREFIXES, *EXTRA_BLOCKING_PREFIXES)
    ):
        return False

    missing = _missing_core_fields(ensemble)
    if not missing:
        return (
            1 <= ensemble.corroborated_fields < len(CORE)
            and "UNCORROBORATED_CORE_FIELDS" in reasons
        )

    if len(missing) != 1:
        return False
    if not (1 <= ensemble.corroborated_fields <= len(CORE) - 1):
        return False
    return any(reason == "MISSING_CORE:" + missing[0] for reason in reasons)


def build_doctr_retry_candidates(
    diagnostic_path: str | Path,
    product_path: str | Path,
    *,
    limit: int = DEFAULT_LIMIT,
) -> tuple[list[dict], dict]:
    """Build a bounded retry cohort from current canonical 2/4 REVIEW rows.

    Mercadona product_id is treated only as a lookup key, never stable identity.
    The current first-party detail must carry the same non-empty EAN as the
    canonical OCR observation before an image is eligible. Prior exact-image
    attempts remain eligible because this wave adds docTR as a genuinely new OCR
    family; acceptance thresholds remain unchanged.
    """
    targets: dict[str, dict] = {}
    missing_anchor_ean: list[str] = []
    for line in Path(diagnostic_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        pid = _token(row.get("product_id"))
        values = row.get("diagnostic_candidate_values") or {}
        if not (
            row.get("canonical_status") == "REVIEW"
            and row.get("corroborated_fields") == 2
            and int(row.get("independent_engine_families") or 0) >= 2
            and row.get("basis") in {"100_g", "100_ml"}
            and all(field in values for field in CORE)
            and not (row.get("safety_blockers") or [])
            and pid
            and row.get("image_url")
        ):
            continue
        if not _token(row.get("ean")):
            missing_anchor_ean.append(pid)
            continue
        targets[pid] = row

    candidates: list[dict] = []
    unmatched_current_photo: list[str] = []
    missing_current_ean: list[str] = []
    reassigned_current_product_ids: list[str] = []
    for line in Path(product_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        pid = _token(row.get("product_id"))
        diagnostic = targets.get(pid)
        if diagnostic is None:
            continue

        anchor_ean = _token(diagnostic.get("ean"))
        current_ean = _token(row.get("ean"))
        if not current_ean:
            missing_current_ean.append(pid)
            continue
        if current_ean != anchor_ean:
            reassigned_current_product_ids.append(pid)
            continue

        image_url = str(diagnostic["image_url"])
        photos = row.get("photos") if isinstance(row.get("photos"), list) else []
        match = next(
            (
                (index, photo)
                for index, photo in enumerate(photos)
                if isinstance(photo, dict) and str(photo.get("zoom") or "") == image_url
            ),
            None,
        )
        if match is None:
            unmatched_current_photo.append(pid)
            continue

        image_index, photo = match
        actual_perspective = photo.get("perspective")
        routed_photo = dict(photo)
        routed_photo["perspective"] = 9
        candidate = dict(row)
        candidate["photos"] = [routed_photo]
        candidate["_near_safe_image_meta"] = {
            "image_url": image_url,
            "image_index": image_index,
            "perspective": actual_perspective,
            "canonical_ean": anchor_ean,
            "current_ean": current_ean,
            "identity_basis": "EXACT_CURRENT_EAN_MATCH",
            "canonical_latest_raw_run_id": diagnostic.get("latest_raw_run_id"),
            "canonical_corroborated_fields": diagnostic.get("corroborated_fields"),
            "canonical_engine_families": diagnostic.get("independent_engine_families"),
            "canonical_confidence": diagnostic.get("confidence"),
        }
        candidates.append(candidate)

    candidates.sort(
        key=lambda row: (
            0 if row.get("ingredients") else 1,
            -int((row.get("_near_safe_image_meta") or {}).get("canonical_engine_families") or 0),
            -float((row.get("_near_safe_image_meta") or {}).get("canonical_confidence") or 0.0),
            str(row.get("product_id") or ""),
        )
    )
    selected = candidates[:limit]
    summary = {
        "pilot_limit": limit,
        "canonical_two_of_four_targets": len(targets),
        "canonical_two_of_four_targets_missing_ean": sorted(set(missing_anchor_ean)),
        "current_exact_first_party_image_targets": len(candidates),
        "current_exact_identity_and_first_party_image_targets": len(candidates),
        "selected": len(selected),
        "selected_with_structured_ingredients": sum(bool(row.get("ingredients")) for row in selected),
        "selected_without_structured_ingredients": sum(not bool(row.get("ingredients")) for row in selected),
        "selected_product_ids": [str(row.get("product_id")) for row in selected],
        "unmatched_current_first_party_photo": sorted(set(unmatched_current_photo)),
        "missing_current_ean": sorted(set(missing_current_ean)),
        "reassigned_current_product_ids": sorted(set(reassigned_current_product_ids)),
        "identity_policy": "CURRENT_PRODUCT_ID_IS_NOT_IDENTITY; EXACT_NONEMPTY_CANONICAL_EAN_EQUALS_CURRENT_FIRST_PARTY_EAN_REQUIRED_BEFORE_IMAGE_RETRY",
        "selection_policy": "CURRENT_CLEAN_CANONICAL_2_OF_4_REVIEW_EXACT_EAN_IDENTITY_AND_EXACT_CURRENT_FIRST_PARTY_IMAGE; PRIOR_ATTEMPTS_ALLOWED_ONLY_BECAUSE_DOCTR_IS_A_NEW_INDEPENDENT_OCR_FAMILY",
        "new_independent_ocr_family": "doctr",
        "doctr_detection_arch": DOCTR_DETECTION_ARCH,
        "doctr_recognition_arch": DOCTR_RECOGNITION_ARCH,
        "acceptance_policy_changed": False,
    }
    return selected, summary


def refresh_workflow_cohort_if_available() -> dict | None:
    diagnostic_path = Path(
        "mercadona-current-ocr-residual-audit/current-review-failure-modes/near-safe-complete-review.jsonl"
    )
    product_path = Path("mercadona-first-party-final/products.jsonl")
    if not diagnostic_path.exists() or not product_path.exists():
        return None

    selected, summary = build_doctr_retry_candidates(diagnostic_path, product_path)
    if not selected:
        raise SystemExit("No actionable current 2-of-4 exact-EAN exact-image targets remain for docTR retry")

    with_ingredients = [row for row in selected if row.get("ingredients")]
    without_ingredients = [row for row in selected if not row.get("ingredients")]

    def write_jsonl(path: str, rows: list[dict]) -> None:
        Path(path).write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

    write_jsonl("two-of-four-with-ingredients.jsonl", with_ingredients)
    write_jsonl("two-of-four-without-ingredients.jsonl", without_ingredients)
    Path("two-of-four-selection-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def _fuse(readings, target_kind: str):
    fused = base.fuse_ocr_readings(base._as_parsed_readings(readings, target_kind))
    if fused.declared_usable:
        return fused
    strict = base._fuse_declared_only_readings(
        (
            (strategy, family, reading.parsed, reading.extraction.confidence)
            for strategy, family, reading in readings
        ),
        target_kind,
    )
    return strict if strict.declared_usable else fused


def _extract_doctr(evidence, image_path: Path, strategy: str, readings, engine_errors) -> None:
    try:
        extracted = extract_with_doctr(image_path)
        readings.append((strategy, "doctr", base._reading(evidence, extracted)))
    except Exception as exc:
        engine_errors[strategy] = f"{type(exc).__name__}:{exc}"


def _extract_easyocr(evidence, image_path: Path, strategy: str, readings, engine_errors) -> None:
    try:
        extracted = extract_with_easyocr(image_path)
        readings.append((strategy, "easyocr", base._reading(evidence, extracted)))
    except Exception as exc:
        engine_errors[strategy] = f"{type(exc).__name__}:{exc}"


def _has_family(readings, family: str) -> bool:
    return any(existing_family == family for _strategy, existing_family, _reading in readings)


def _extract_region(evidence, region_path: Path, target_kind: str):
    readings, engine_errors, ensemble = base._ORIGINAL_EXTRACT_REGION(
        evidence, region_path, target_kind
    )
    if not should_run_doctr_rescue(ensemble):
        return readings, engine_errors, ensemble

    missing_before_retry = _missing_core_fields(ensemble)

    # A historical 3/4 row cannot be completed from history. When the fresh
    # Paddle/Tesseract observation is itself a clean 3/4 tuple, run *two* extra
    # independent OCR families on this same region. docTR alone could discover a
    # missing value but could not independently corroborate it; EasyOCR + docTR
    # can, while the ordinary four-field ensemble contract remains unchanged.
    # No crop/transform values are fused in this missing-core path.
    if len(missing_before_retry) == 1:
        if not _has_family(readings, "easyocr"):
            _extract_easyocr(evidence, region_path, "easyocr-missing-core", readings, engine_errors)
        if not _has_family(readings, "doctr"):
            _extract_doctr(evidence, region_path, "doctr-missing-core", readings, engine_errors)
        return readings, engine_errors, _fuse(readings, target_kind)

    _extract_doctr(evidence, region_path, "doctr-original", readings, engine_errors)
    candidate = _fuse(readings, target_kind)
    if candidate.declared_usable:
        return readings, engine_errors, candidate

    with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-doctr-retry-") as td:
        variants = {variant.name: variant for variant in build_fallback_variants(region_path, td)}
        for variant_name in DOCTR_VARIANT_NAMES:
            variant = variants.get(variant_name)
            if variant is None:
                engine_errors[f"doctr-{variant_name}"] = "MISSING_PREPROCESS_VARIANT"
                continue
            _extract_doctr(
                evidence,
                variant.path,
                f"doctr-{variant_name}",
                readings,
                engine_errors,
            )
            candidate = _fuse(readings, target_kind)
            if candidate.declared_usable:
                return readings, engine_errors, candidate

    return readings, engine_errors, _fuse(readings, target_kind)


def _explicit_policy_flags_on_results_from_argv() -> None:
    """Make the rescue's non-inference/non-classification contract explicit.

    The underlying neural OCR runner predates these audit fields and therefore
    omitted them rather than writing false. This rescue never infers missing
    values and never performs semantic classification; materialize those facts in
    its JSONL output before the workflow's fail-closed provenance validation.
    """
    try:
        out_index = sys.argv.index("--out") + 1
        out_dir = Path(sys.argv[out_index])
    except (ValueError, IndexError):
        return

    for path in out_dir.glob("results-*.jsonl"):
        patched: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            row.setdefault("missing_values_inferred", False)
            row.setdefault("CLASSIFIED", 0)
            row.setdefault("MENU_ELIGIBLE", 0)
            patched.append(row)
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in patched),
            encoding="utf-8",
        )


def main() -> int:
    refresh_workflow_cohort_if_available()
    base._ORIGINAL_EXTRACT_REGION = base._extract_region
    base._extract_region = _extract_region
    rc = base.main()
    _explicit_policy_flags_on_results_from_argv()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
