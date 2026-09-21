from __future__ import annotations

from typing import Any


IMAGE_WIDE_STRUCTURAL_REASON_PREFIXES = (
    "MULTIPLE_NUTRITION_COLUMNS",
    "OCR_AMBIGUOUS_NUTRITION_COLUMNS",
)


def attempts_have_structural_ambiguity(attempts: list[dict[str, Any]]) -> bool:
    """Return True when any OCR target saw a structurally ambiguous nutrition table.

    Targets are alternative OCR views of the same first-party label image. A crop
    that isolates one column cannot make nutrition usable when another credible
    target exposes parallel nutrition columns on that image.
    """
    for attempt in attempts:
        ensemble = attempt.get("ensemble") if isinstance(attempt, dict) else None
        if not isinstance(ensemble, dict):
            continue
        reasons = ensemble.get("reasons") if isinstance(ensemble.get("reasons"), list) else []
        if any(
            str(reason).startswith(prefix)
            for reason in reasons
            for prefix in IMAGE_WIDE_STRUCTURAL_REASON_PREFIXES
        ):
            return True
    return False
