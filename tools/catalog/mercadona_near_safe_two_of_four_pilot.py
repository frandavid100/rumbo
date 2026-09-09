from __future__ import annotations

import mercadona_near_safe_variant_rescue as rescue
import mercadona_neural_ocr_wave as base


# This pilot broadens only the *observation retry* gate from the exhausted 3/4
# cohort to a clean 2/4-corroborated cohort. Acceptance remains the existing
# conservative ensemble policy. In particular, the bounded dissenting-family
# rescue in mercadona_near_safe_variant_rescue still requires exactly 3/4 fields
# and therefore cannot promote a 2/4 tuple by itself.
#
# Cohort selection is intentionally rebuilt from the latest canonical residual
# on every workflow run. After a successful reconciliation, repeating the same
# bounded 16-product wave therefore advances to the current clean 2/4 residual
# rather than replaying products that have already left that cohort.
def should_run_two_of_four_variant_rescue(ensemble) -> bool:
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
    if ensemble.corroborated_fields != 2:
        return False
    if "UNCORROBORATED_CORE_FIELDS" not in ensemble.reasons:
        return False
    return not any(
        str(reason).startswith(prefix)
        for reason in ensemble.reasons
        for prefix in rescue.HARD_BLOCKING_PREFIXES
    )


def main() -> int:
    # Reuse the already-tested deterministic crop/layout observation machinery,
    # changing only its retry predicate for this bounded pilot. The normal
    # fusion, basis checks, macro-energy coherence checks and DECLARED threshold
    # are untouched.
    base._ORIGINAL_EXTRACT_REGION = base._extract_region
    rescue.should_run_variant_rescue = should_run_two_of_four_variant_rescue
    base._extract_region = rescue._extract_region
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
