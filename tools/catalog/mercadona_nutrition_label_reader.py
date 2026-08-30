from __future__ import annotations

from nutrition_label_reader import (
    LabelReadResult,
    _number_immediately_before,
    _nutrition_block,
    read_nutrition_label as _read_nutrition_label,
)

READER_VERSION = "1.0.0"


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


def _row_order_ambiguity(result: LabelReadResult) -> str | None:
    """Detect a narrow observed PP-OCR value-before-label failure.

    Some Mercadona rear labels are linearised with the numeric column before its
    row labels near the end of the table. A label->next-number parser can then
    bind the following row's value to a macro (observed: protein <- salt). This
    can still pass the broad energy tolerance on carbohydrate-heavy products.

    Do not infer the alternative value. Route to REVIEW only when the explicit
    immediately-preceding value would make a near-exact energy tuple and is
    materially better than the parsed tuple. This preserves normal label/value
    layouts while prioritising precision over recall.
    """
    if result.status != "DECLARED" or result.nutrition is None:
        return None
    required = ("calories", "fat_g", "carbohydrate_g", "protein_g")
    if any(result.nutrition.get(key) is None for key in required):
        return None

    nutrition = {key: float(result.nutrition[key]) for key in required}
    block = _nutrition_block(result.normalized_text)
    parsed_residual = _energy_residual(nutrition)

    for key, patterns in _MACRO_PATTERNS.items():
        before = _number_immediately_before(patterns, block)
        if before is None or abs(float(before) - nutrition[key]) <= 0.05:
            continue
        alternative = dict(nutrition)
        alternative[key] = float(before)
        alternative_residual = _energy_residual(alternative)
        near_exact = alternative_residual <= max(6.0, nutrition["calories"] * 0.03)
        material_improvement = (
            parsed_residual - alternative_residual
            >= max(6.0, nutrition["calories"] * 0.02)
        )
        if near_exact and material_improvement:
            return f"AMBIGUOUS_VALUE_BEFORE_LABEL:{key}"
    return None


def read_nutrition_label(text: str, *, extraction_confidence: float = 1.0) -> LabelReadResult:
    result = _read_nutrition_label(text, extraction_confidence=extraction_confidence)
    ambiguity = _row_order_ambiguity(result)
    if ambiguity is None:
        return result
    return LabelReadResult(
        status="REVIEW",
        basis=result.basis,
        nutrition=result.nutrition,
        confidence=min(result.confidence, 0.65),
        reasons=tuple(result.reasons) + (ambiguity,),
        normalized_text=result.normalized_text,
    )
