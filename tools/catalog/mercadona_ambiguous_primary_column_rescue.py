from __future__ import annotations

"""Bounded rescue for historically ambiguous multi-column Mercadona labels.

The caller must preselect a tiny historical cohort whose canonical REVIEW state
has a complete 3-of-4-corrobated tuple, at least three OCR families, and exactly
one normalized safety blocker: AMBIGUOUS_TABLE caused by a
MULTIPLE_NUTRITION_COLUMNS signal. Product identity and the exact first-party
perspective=9 image must then be revalidated against the live official API.

This module changes OCR routing only. It never promotes the historical tuple and
never fuses values across runs or across crop variants. A temporary primary-
column crop is usable only when that single crop independently satisfies the
unchanged parser, energy/macro coherence and OCR-family corroboration contract.
Image bytes remain temporary.
"""

from pathlib import Path
import tempfile

import mercadona_bounded_doctr_rescue as bounded
import mercadona_near_safe_doctr_retry as retry

CORE = bounded.CORE
AMBIGUOUS_TABLE_BLOCKER = "AMBIGUOUS_TABLE"
MULTIPLE_COLUMN_REASON = "MULTIPLE_NUTRITION_COLUMNS"


def select_ambiguous_primary_column_targets(rows) -> list[dict]:
    """Return only the auditable complete 3-of-4 ambiguity-only REVIEW cohort."""
    selected: list[dict] = []
    for row in rows:
        values = row.get("diagnostic_candidate_values") or {}
        blockers = {str(value) for value in (row.get("safety_blockers") or [])}
        reason_prefixes = {str(value) for value in (row.get("reason_prefixes") or [])}
        product_id = str(row.get("product_id") or "").strip()
        ean = str(row.get("ean") or "").strip()
        image_url = str(row.get("image_url") or "").strip()
        if not (
            row.get("canonical_status") == "REVIEW"
            and int(row.get("corroborated_fields") or 0) == 3
            and int(row.get("independent_engine_families") or 0) >= 3
            and row.get("basis") in {"100_g", "100_ml"}
            and all(values.get(field) is not None for field in CORE)
            and blockers == {AMBIGUOUS_TABLE_BLOCKER}
            and MULTIPLE_COLUMN_REASON in reason_prefixes
            and product_id
            and ean
            and image_url
        ):
            continue
        selected.append(row)

    selected.sort(key=lambda row: (len(str(row["product_id"])), str(row["product_id"])))
    return selected


def _prefixed(readings, prefix: str):
    return [
        (f"{prefix}/{strategy}", family, reading)
        for strategy, family, reading in readings
    ]


def _prefixed_errors(engine_errors: dict[str, str], prefix: str) -> dict[str, str]:
    return {f"{prefix}/{strategy}": error for strategy, error in engine_errors.items()}


def _extract_region(evidence, region_path: Path, target_kind: str):
    """Try ordinary bounded OCR, then independent primary-column observations.

    The original whole-region observation is never fused with a primary-column
    observation. Likewise 42% and 50% crops are never fused with each other. This
    is important: isolating a column may remove the layout ambiguity, but it does
    not make the historical ambiguous values positive evidence. Only a single
    freshly observed crop that independently becomes DECLARED may be returned.
    """
    baseline_readings, baseline_errors, baseline = bounded._extract_region_with_post_doctr_easyocr(
        evidence, region_path, target_kind
    )
    if baseline.declared_usable:
        return baseline_readings, baseline_errors, baseline

    with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-primary-column-ambiguity-") as td:
        variants = bounded.build_bounded_primary_column_variants(region_path, td)
        for variant in variants:
            crop_readings, crop_errors, crop_ensemble = bounded._DOCTR_EXTRACT_REGION(
                evidence, variant.path, target_kind
            )
            if crop_ensemble.declared_usable:
                prefix = variant.name
                return (
                    _prefixed(crop_readings, prefix),
                    _prefixed_errors(crop_errors, prefix),
                    crop_ensemble,
                )

    return baseline_readings, baseline_errors, baseline


def main() -> int:
    # Keep the proven bounded docTR routing for each fresh crop, but replace the
    # region wrapper with the ambiguity-specific no-cross-crop-fusion route above.
    retry.should_run_doctr_rescue = bounded.should_run_bounded_doctr_rescue
    retry._extract_region = _extract_region
    return retry.main()


if __name__ == "__main__":
    raise SystemExit(main())
