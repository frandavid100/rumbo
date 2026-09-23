from __future__ import annotations

"""Narrow Mercadona repair for a manufacturer line interleaved in a nutrition row.

Observed on first-party product 21649: PP-OCRv6 linearises the protein value as
``6.7 g / Fabricado/Producido por: ... / Proteínas`` while fat and carbohydrate
remain ordinary value-before-label rows. This module never invents a value or
skips arbitrary prose. It accepts only that exact bilingual manufacturer-prefix
shape, requires all three macro values to be explicitly present, an explicit
per-100 basis, high OCR confidence, and a near-exact energy/macro tuple.
"""

import re

from mercadona_nutrition_label_percentage_guard import (
    LabelReadResult,
    read_nutrition_label as _read_nutrition_label,
)
from nutrition_label_reader import _fold, _number_immediately_before, _nutrition_block

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
_ALLOWED_FORWARD_NOISE = frozenset({"IMPOSSIBLE_CARBOHYDRATE_G"})
_HARD_REASON_PREFIXES = (
    "MULTIPLE_NUTRITION_COLUMNS",
    "ENERGY_MACRO_MISMATCH_STRICT",
)
_REASON = "MERCADONA_MANUFACTURER_INTERLEAVED_VALUE_BEFORE_LABEL_STRUCTURE"


def _protein_before_bilingual_manufacturer(text: str) -> float | None:
    """Read only ``<value g> / Fabricado/Producido por: ... / Proteínas``."""
    folded = _fold(text)
    for label in _PROTEIN_PATTERNS:
        for match in re.finditer(label, folded, flags=re.I):
            head = folded[max(0, match.start() - 240):match.start()].rstrip()
            candidate = re.search(
                r"(?:^|\n)\s*([<>]?)\s*(\d{1,3}(?:\.\d{1,2})?)\s*"
                r"(?:g|9|q|yg|y)\s*\n"
                r"\s*fabricado\s*/\s*producido\s+por\s*:[^\n]{1,160}\s*$",
                head,
                flags=re.I,
            )
            if candidate is None or candidate.group(1) in ("<", ">"):
                continue
            value = float(candidate.group(2))
            if 0.0 <= value <= 100.0:
                return value
    return None


def _energy_residual(nutrition: dict[str, float]) -> float:
    estimated = (
        9.0 * nutrition["fat_g"]
        + 4.0 * nutrition["carbohydrate_g"]
        + 4.0 * nutrition["protein_g"]
    )
    return abs(estimated - nutrition["calories"])


def _repair_manufacturer_interleave(
    result: LabelReadResult,
    *,
    extraction_confidence: float,
) -> LabelReadResult | None:
    if result.status != "REVIEW":
        return None
    if result.basis not in {"100_g", "100_ml"} or extraction_confidence < .85:
        return None
    if any(str(reason).startswith(_HARD_REASON_PREFIXES) for reason in result.reasons):
        return None

    impossible = {
        str(reason)
        for reason in result.reasons
        if str(reason).startswith("IMPOSSIBLE_")
    }
    if impossible - _ALLOWED_FORWARD_NOISE:
        return None

    existing = dict(result.nutrition or {})
    calories = existing.get("calories")
    if not isinstance(calories, (int, float)):
        return None

    block = _nutrition_block(result.normalized_text)
    fat = _number_immediately_before(_FAT_PATTERNS, block)
    carbs = _number_immediately_before(_CARB_PATTERNS, block)
    protein = _protein_before_bilingual_manufacturer(block)
    if any(value is None for value in (fat, carbs, protein)):
        return None

    complete = {
        "calories": float(calories),
        "fat_g": float(fat),
        "carbohydrate_g": float(carbs),
        "protein_g": float(protein),
    }
    if any(not 0.0 <= complete[key] <= 100.0 for key in ("fat_g", "carbohydrate_g", "protein_g")):
        return None
    if _energy_residual(complete) > max(6.0, complete["calories"] * .03):
        return None

    cleaned = tuple(
        reason for reason in result.reasons
        if not (
            str(reason).startswith("MISSING_CORE:")
            or str(reason).startswith("ENERGY_MACRO_MISMATCH:")
            or str(reason) in _ALLOWED_FORWARD_NOISE
        )
    )
    discarded = tuple(
        f"FORWARD_{reason}_DISCARDED"
        for reason in sorted(impossible & _ALLOWED_FORWARD_NOISE)
    )
    return LabelReadResult(
        status="DECLARED",
        basis=result.basis,
        nutrition=complete,
        confidence=min(1.0, extraction_confidence),
        reasons=cleaned + discarded + (_REASON,),
        normalized_text=result.normalized_text,
    )


def read_nutrition_label(text: str, *, extraction_confidence: float = 1.0) -> LabelReadResult:
    result = _read_nutrition_label(text, extraction_confidence=extraction_confidence)
    repaired = _repair_manufacturer_interleave(
        result,
        extraction_confidence=extraction_confidence,
    )
    return repaired if repaired is not None else result
