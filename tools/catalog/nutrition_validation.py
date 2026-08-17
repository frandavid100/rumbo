from __future__ import annotations

from dataclasses import dataclass


VALIDATOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class NutritionValidation:
    valid: bool
    reasons: tuple[str, ...]


def validate_nutrition(
    calories: float | None,
    protein_g: float | None,
    carbohydrate_g: float | None,
    fat_g: float | None,
    fiber_g: float | None = None,
    salt_g: float | None = None,
) -> NutritionValidation:
    """Conservative blocking checks for values expressed per 100 g/ml.

    These checks intentionally catch only physically impossible or strongly
    incoherent values. Energy-vs-macro coherence remains tolerant because
    fibre, polyols, alcohol and rounding can explain legitimate differences.
    """
    reasons: list[str] = []
    core = {
        "calories": calories,
        "protein_g": protein_g,
        "carbohydrate_g": carbohydrate_g,
        "fat_g": fat_g,
    }
    if any(v is None for v in core.values()):
        reasons.append("INCOMPLETE_CORE_NUTRITION")
        return NutritionValidation(False, tuple(reasons))

    assert calories is not None and protein_g is not None and carbohydrate_g is not None and fat_g is not None
    if not 0 <= calories <= 950:
        reasons.append("CALORIES_OUT_OF_RANGE")
    for label, value in (("PROTEIN", protein_g), ("CARBOHYDRATE", carbohydrate_g), ("FAT", fat_g)):
        if not 0 <= value <= 100:
            reasons.append(f"{label}_OUT_OF_RANGE")
    if fiber_g is not None and not 0 <= fiber_g <= 100:
        reasons.append("FIBER_OUT_OF_RANGE")
    if salt_g is not None and not 0 <= salt_g <= 100:
        reasons.append("SALT_OUT_OF_RANGE")

    core_sum = protein_g + carbohydrate_g + fat_g
    if core_sum > 105:
        reasons.append("CORE_MACRO_SUM_IMPOSSIBLE")
    if fiber_g is not None and core_sum + fiber_g > 110:
        reasons.append("MACRO_FIBER_SUM_IMPOSSIBLE")

    # Very broad coherence band; this is a blocker only for extreme cases.
    macro_kcal = protein_g * 4 + carbohydrate_g * 4 + fat_g * 9
    if macro_kcal >= 40:
        if calories < macro_kcal * 0.45:
            reasons.append("ENERGY_TOO_LOW_FOR_MACROS")
        if calories > macro_kcal * 2.5 + 120:
            reasons.append("ENERGY_TOO_HIGH_FOR_MACROS")

    return NutritionValidation(not reasons, tuple(reasons))
