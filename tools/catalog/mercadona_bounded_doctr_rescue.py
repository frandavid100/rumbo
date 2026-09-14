from __future__ import annotations

"""Bounded docTR rescue for safe historical Mercadona REVIEW regressions.

This module changes OCR routing only. It never relaxes the parser, ensemble,
energy/macro coherence, independent-family corroboration, or provenance gates.
The caller is responsible for supplying a cohort whose historical identity and
first-party image have already been revalidated exactly.
"""

import mercadona_near_safe_doctr_retry as retry

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
MIN_PRESENT_CORE_FIELDS = 2


def should_run_bounded_doctr_rescue(ensemble) -> bool:
    """Add docTR to a clean but incomplete REVIEW observation.

    The ordinary near-safe retry is intentionally restricted to complete 4-field
    candidates. This bounded rescue is for products that were previously
    DECLARED and later regressed to a non-contradictory REVIEW. It may spend a
    fourth OCR family on a current extraction with at least two core fields, but
    it cannot make that extraction usable unless the unchanged downstream
    ensemble independently satisfies the normal DECLARED contract.
    """
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return False
    if ensemble.basis not in {"100_g", "100_ml"}:
        return False
    nutrition = ensemble.nutrition if isinstance(ensemble.nutrition, dict) else {}
    present = sum(nutrition.get(field) is not None for field in CORE)
    if present < MIN_PRESENT_CORE_FIELDS:
        return False
    if int(ensemble.independent_engine_families or 0) < 1:
        return False
    reasons = [str(reason) for reason in ensemble.reasons]
    return not any(
        reason.startswith(prefix)
        for reason in reasons
        for prefix in retry.rescue.HARD_BLOCKING_PREFIXES
    )


def main() -> int:
    # Reuse the already-audited docTR extraction/fusion path. Only the routing
    # predicate differs for this explicitly bounded cohort.
    retry.should_run_doctr_rescue = should_run_bounded_doctr_rescue
    return retry.main()


if __name__ == "__main__":
    raise SystemExit(main())
