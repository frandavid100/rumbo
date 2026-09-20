from __future__ import annotations

"""Variant retry for a cohort already proven canonical 3/4 upstream.

This module changes only OCR *routing*. The workflow that invokes it first
selects clean canonical REVIEW rows with exactly three observed core fields,
explicit 100 g/100 ml basis and no hard safety blocker, then re-observes the
exact same Mercadona first-party perspective=9 image URL in the current official
API detail.

For this preselected cohort we allow the existing temporary-variant machinery to
run when the fresh pass either keeps exactly three core fields or produces a
complete tuple with only 1/4, 2/4 or 3/4 fields corroborated. A fresh three-of-four
observation from only one OCR family is also retryable: variants are observation
quality retries whose purpose is precisely to seek an independent family, while
acceptance remains unchanged and still requires the ordinary independent-engine
gates. Historical values are never consumed by this decision.

Acceptance is untouched: a usable result still has to recover all four values in
the fresh observation and pass the normal parser, explicit-basis,
energy/macro-coherence and independent-engine corroboration gates. No value is
inferred or fused from the historical partial observation, and variant images are
temporary.
"""

import mercadona_near_safe_variant_rescue as rescue
import mercadona_neural_ocr_wave as base


def should_run_preselected_three_of_four_variant_rescue(ensemble) -> bool:
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return False
    if ensemble.basis not in {"100_g", "100_ml"}:
        return False
    if not ensemble.nutrition:
        return False
    if ensemble.independent_engine_families < 1:
        return False
    if any(
        str(reason).startswith(prefix)
        for reason in ensemble.reasons
        for prefix in rescue.HARD_BLOCKING_PREFIXES
    ):
        return False

    present = {
        field for field in base.CORE_NUTRITION_FIELDS
        if field in ensemble.nutrition and ensemble.nutrition.get(field) is not None
    }
    missing = [field for field in base.CORE_NUTRITION_FIELDS if field not in present]

    if not missing:
        # A complete fresh tuple still needs at least two independent families
        # before the bounded near-safe retry route is opened. This preserves the
        # established complete-tuple behaviour; the new single-family allowance
        # below is limited to an exact 3/4 MISSING_CORE observation.
        if ensemble.independent_engine_families < 2:
            return False
        if not (1 <= ensemble.corroborated_fields < len(base.CORE_NUTRITION_FIELDS)):
            return False
        return "UNCORROBORATED_CORE_FIELDS" in ensemble.reasons

    if len(missing) != 1:
        return False

    # The preselected workflow has already established the historical clean 3/4
    # contract. On the fresh exact same first-party image, one family may recover
    # the same 3/4 tuple while other engines fail to parse anything. Running
    # deterministic temporary variants is safe here because this is routing only:
    # a result can become usable only if the fresh retry independently recovers
    # all four fields and satisfies the unchanged >=2-family acceptance gates.
    if not (0 <= ensemble.corroborated_fields < len(base.CORE_NUTRITION_FIELDS)):
        return False

    # A missing field is retryable only when the ensemble explicitly records the
    # same single missing core field. This prevents the preselected route from
    # swallowing unrelated REVIEW shapes merely because their nutrition mapping
    # happens to contain three keys.
    expected = f"MISSING_CORE:{missing[0]}"
    return expected in ensemble.reasons


def main() -> int:
    base._ORIGINAL_EXTRACT_REGION = base._extract_region
    rescue.should_run_variant_rescue = should_run_preselected_three_of_four_variant_rescue
    base._extract_region = rescue._extract_region
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
