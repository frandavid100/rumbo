from __future__ import annotations

from itertools import combinations

from nutrition_label_reader import (
    LabelReadResult,
    _number_immediately_before,
    _nutrition_block,
    read_nutrition_label as _read_nutrition_label,
)

READER_VERSION = "1.0.2"


_FAT_PATTERNS = (
    r"(?:^|\n)\s*grasas?(?:\s*/\s*lipidos?)?\b",
    r"(?:^|\n)\s*lipidos?\b",
    r"(?:^|\n)\s*grasa total\b",
)
_CARB_PATTERNS = (
    r"(?:^|\n)\s*hidratos? de carbono\b",
    r"(?:^|\n)\s*carbohidratos?\b",
)
_PROTEIN_PATTERNS = (r"(?:^|\n)\s*proteinas?\b",)
_MACRO_PATTERNS = {
    "fat_g": _FAT_PATTERNS,
    "carbohydrate_g": _CARB_PATTERNS,
    "protein_g": _PROTEIN_PATTERNS,
}


def _energy_residual(nutrition: dict[str, float]) -> float:
    estimated = (
        9 * nutrition["fat_g"]
        + 4 * nutrition["carbohydrate_g"]
        + 4 * nutrition["protein_g"]
    )
    return abs(estimated - nutrition["calories"])


def _near_exact_energy(nutrition: dict[str, float]) -> bool:
    return _energy_residual(nutrition) <= max(6.0, nutrition["calories"] * 0.03)


def _materially_improves_energy(
    original: dict[str, float], alternative: dict[str, float]
) -> bool:
    return (
        _energy_residual(original) - _energy_residual(alternative)
        >= max(6.0, original["calories"] * 0.02)
    )


def _row_order_ambiguity(result: LabelReadResult) -> str | None:
    """Detect narrow observed OCR value-before-label failures.

    Some Mercadona rear labels are linearised with the numeric column before its
    row labels near the end of the table. A label->next-number parser can then
    bind the following row's value to a macro (observed: protein <- salt). This
    can still pass the broad energy tolerance on carbohydrate-heavy products.

    Do not infer alternative values. Route the tuple to REVIEW-only audit text
    when explicit immediately-preceding values would make a near-exact energy
    tuple and materially improve the parsed one. For an already-DECLARED tuple,
    retain the historical single-field guard. For a tuple already in REVIEW due
    to energy/macronutrient mismatch, also allow a combination of two or more
    competing before-label bindings: this is the observed Mercadona 21594 mode.
    """
    if result.status not in {"DECLARED", "REVIEW"} or result.nutrition is None:
        return None
    required = ("calories", "fat_g", "carbohydrate_g", "protein_g")
    if any(result.nutrition.get(key) is None for key in required):
        return None

    nutrition = {key: float(result.nutrition[key]) for key in required}
    block = _nutrition_block(result.normalized_text)
    alternatives: dict[str, float] = {}
    for key, patterns in _MACRO_PATTERNS.items():
        before = _number_immediately_before(patterns, block)
        if before is None or abs(float(before) - nutrition[key]) <= 0.05:
            continue
        alternatives[key] = float(before)

    # Preserve the original DECLARED guard exactly: one competing row is enough
    # only if that single replacement almost perfectly explains the energy.
    for key, before in alternatives.items():
        alternative = dict(nutrition)
        alternative[key] = before
        if _near_exact_energy(alternative) and _materially_improves_energy(nutrition, alternative):
            return f"AMBIGUOUS_VALUE_BEFORE_LABEL:{key}"

    # A REVIEW tuple already carrying the strict energy-mismatch reason may have
    # more than one shifted row. Search explicit competing bindings only to prove
    # ambiguity; never expose the resulting values. Requiring the existing
    # mismatch reason keeps this branch narrow and prevents ordinary label/value
    # layouts from being reinterpreted merely because several previous row values
    # happen to form another plausible combination.
    has_energy_mismatch = any(
        str(reason).startswith("ENERGY_MACRO_MISMATCH") for reason in result.reasons
    )
    if result.status == "REVIEW" and has_energy_mismatch and len(alternatives) >= 2:
        keys = tuple(alternatives)
        for size in range(2, len(keys) + 1):
            for subset in combinations(keys, size):
                alternative = dict(nutrition)
                for key in subset:
                    alternative[key] = alternatives[key]
                if _near_exact_energy(alternative) and _materially_improves_energy(
                    nutrition, alternative
                ):
                    return "AMBIGUOUS_VALUE_BEFORE_LABEL:" + ",".join(subset)
    return None


def read_nutrition_label(text: str, *, extraction_confidence: float = 1.0) -> LabelReadResult:
    result = _read_nutrition_label(text, extraction_confidence=extraction_confidence)
    ambiguity = _row_order_ambiguity(result)
    if ambiguity is None:
        return result
    # REVIEW reads normally remain useful as corroborating evidence in the OCR
    # ensemble. Row-order ambiguity is different: the tuple itself is known to
    # contain a competing binding, so exposing it would let an unsafe value
    # corroborate another engine. Preserve text/basis/reason for audit only.
    return LabelReadResult(
        status="REVIEW",
        basis=result.basis,
        nutrition=None,
        confidence=min(result.confidence, 0.65),
        reasons=tuple(result.reasons) + (ambiguity,),
        normalized_text=result.normalized_text,
    )
