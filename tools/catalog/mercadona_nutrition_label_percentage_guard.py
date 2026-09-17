from __future__ import annotations

"""Mercadona-only guard against ingredient percentages masquerading as fat rows.

Whole-pack OCR can interleave an ingredients column after the visible nutrition
heading. A line such as ``grasa (16%). emulgente ...`` then starts at a line
boundary and can look like a total-fat label even though the number is an
ingredient percentage, not grams per 100 g/ml.

This module changes no number and invents no value. It only makes that exact
singular ``grasa (<percent>%)`` ingredient shape ineligible as a nutrition-row
label; the ordinary Mercadona structural reader must still recover and validate
all four macros, basis and energy coherence from explicit OCR evidence.
"""

import re

from mercadona_nutrition_label_structural_repair import (
    LabelReadResult,
    read_nutrition_label as _read_nutrition_label,
)

READER_VERSION = "1.0.0"

_NUTRITION_HEADING = re.compile(
    r"(?i)(?:informaci[oó]n\s*(?:/\s*informa[cç][aã]o)?\s+nutricional|"
    r"declaraci[oó]n\s+nutricional|valores?\s+nutricionales?)"
)
_INGREDIENT_FAT_PERCENT_AT_LINE_START = re.compile(
    r"(?im)^([ \t]*[\[|]?[ \t]*)grasa([ \t]*\([ \t]*"
    r"\d{1,3}(?:[.,]\d{1,2})?[ \t]*%[ \t]*\))"
)


def guard_interleaved_ingredient_fat_percent(text: str) -> tuple[str, bool]:
    """Disable only a post-heading singular ``grasa (<percent>%)`` false row.

    ``grasa`` is rewritten to ``grasa_ingrediente``. The underscore deliberately
    removes the word boundary required by the downstream fat-row regex while
    retaining the original percentage and surrounding OCR text for audit.
    Legitimate rows such as ``Grasas 33.5 g (48%)`` are untouched because the
    percentage is not immediately after the row label.
    """
    original = text or ""
    heading = _NUTRITION_HEADING.search(original)
    if heading is None:
        return original, False

    prefix = original[:heading.start()]
    tail = original[heading.start():]
    repaired, count = _INGREDIENT_FAT_PERCENT_AT_LINE_START.subn(
        lambda match: f"{match.group(1)}grasa_ingrediente{match.group(2)}",
        tail,
    )
    return prefix + repaired, bool(count)


def read_nutrition_label(text: str, *, extraction_confidence: float = 1.0) -> LabelReadResult:
    guarded, _ = guard_interleaved_ingredient_fat_percent(text)
    return _read_nutrition_label(
        guarded,
        extraction_confidence=extraction_confidence,
    )
