from __future__ import annotations

"""Variant retry for a cohort already proven canonical 3/4 upstream.

This module changes only OCR *routing*.  The workflow that invokes it first
selects clean canonical REVIEW rows with 3/4 corroborated core fields and then
re-observes the exact same Mercadona first-party perspective=9 image URL in the
current official API detail.  A fresh OCR pass can be noisier than the canonical
observation and fall to 2/4; in that case the ordinary 3/4-only retry predicate
would skip the deterministic temporary image variants entirely.

For this preselected cohort we therefore allow the existing variant machinery to
run when the fresh pass still has a complete, clean tuple with at least 2/4
corroborated fields.  Acceptance is untouched: a usable result still has to pass
the normal parser, explicit basis, energy/macro coherence and independent-engine
corroboration gates.  No value is inferred and variant images are temporary.
"""

import mercadona_near_safe_variant_rescue as rescue
import mercadona_neural_ocr_wave as base


def should_run_preselected_three_of_four_variant_rescue(ensemble) -> bool:
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return False
    if ensemble.basis not in {"100_g", "100_ml"}:
        return False
    if not ensemble.nutrition or any(
        field not in ensemble.nutrition for field in base.CORE_NUTRITION_FIELDS
    ):
        return False
    if ensemble.independent_engine_families < 2:
        return False
    # Upstream selection, not this predicate, proves canonical 3/4.  This lower
    # bound only prevents a stochastic/noisy fresh re-read from suppressing the
    # observation variants.  One-family/one-field evidence remains too weak even
    # for this bounded retry route.
    if not (2 <= ensemble.corroborated_fields < len(base.CORE_NUTRITION_FIELDS)):
        return False
    if "UNCORROBORATED_CORE_FIELDS" not in ensemble.reasons:
        return False
    return not any(
        str(reason).startswith(prefix)
        for reason in ensemble.reasons
        for prefix in rescue.HARD_BLOCKING_PREFIXES
    )


def main() -> int:
    base._ORIGINAL_EXTRACT_REGION = base._extract_region
    rescue.should_run_variant_rescue = should_run_preselected_three_of_four_variant_rescue
    base._extract_region = rescue._extract_region
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
