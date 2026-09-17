from __future__ import annotations

"""Mercadona-only guard against ingredient percentages masquerading as fat rows.

Whole-pack OCR can interleave an ingredients column around the visible nutrition
table. A line such as ``grasa (16%). emulgente ...`` can then start at a line
boundary and look like a total-fat label even though the number is an ingredient
percentage, not grams per 100 g/ml.

This module changes no number and invents no value. It only makes a conservative
singular ``grasa (<percent>%)`` ingredient shape ineligible as a nutrition-row
label; the ordinary Mercadona structural reader must still recover and validate
all four macros, basis and energy coherence from explicit OCR evidence.
"""

import re

from mercadona_nutrition_label_structural_repair import (
    LabelReadResult,
    read_nutrition_label as _read_nutrition_label,
)

READER_VERSION = "1.0.1"

_NUTRITION_HEADING = re.compile(
    r"(?i)(?:informaci[oó]n\s*(?:/\s*informa[cç][aã]o)?\s+nutricional|"
    r"declaraci[oó]n\s+nutricional|valores?\s+nutricionales?)"
)
_INGREDIENT_FAT_PERCENT_AT_LINE_START = re.compile(
    r"(?im)^([ \t]*[\[|]?[ \t]*)grasa([ \t]*\([ \t]*"
    r"\d{1,3}(?:[.,]\d{1,2})?[ \t]*%[ \t]*\))"
)
_INGREDIENT_CONTINUATION = re.compile(
    r"(?i)^[ \t]*(?:[.,;:)\]}|-]+[ \t]*)*"
    r"(?:emulgente|emulsionante|lecitina|preparad[oa]|prepara[cç][aã]o|"
    r"humectante|gasificante|espesante|espessante)\b"
)


def _guard_strong_ingredient_context(text: str) -> tuple[str, int]:
    """Guard an OCR-reordered ingredient percentage even before the heading.

    Some OCR layouts emit the ingredient fragment before ``INFORMACIÓN
    NUTRICIONAL``/``Valores medios`` while the downstream structural reader still
    sees the whole image text. In that ordering, position relative to the heading
    is not a reliable safety boundary. We therefore also guard the same singular
    ``grasa (<percent>%)`` shape when the *same OCR line* immediately continues
    with strong ingredient vocabulary such as ``emulgente`` or ``preparado``.

    A bare pre-heading percentage remains untouched. Likewise a genuine nutrition
    row such as ``Grasas 33.5 g (48%)`` does not match this singular immediate
    parenthesized-percentage shape.
    """
    source = text or ""
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        line_end = source.find("\n", match.end())
        if line_end < 0:
            line_end = len(source)
        remainder = source[match.end():line_end]
        if _INGREDIENT_CONTINUATION.match(remainder) is None:
            return match.group(0)
        changed += 1
        return f"{match.group(1)}grasa_ingrediente{match.group(2)}"

    return _INGREDIENT_FAT_PERCENT_AT_LINE_START.sub(replace, source), changed


def guard_interleaved_ingredient_fat_percent(text: str) -> tuple[str, bool]:
    """Disable only a singular ingredient ``grasa (<percent>%)`` false row.

    ``grasa`` is rewritten to ``grasa_ingrediente``. The underscore deliberately
    removes the word boundary required by the downstream fat-row regex while
    retaining the original percentage and surrounding OCR text for audit.

    The first pass handles OCR-reordered lines only when they have strong
    ingredient continuation context. The second, older pass preserves the broader
    post-heading protection because once the nutrition heading has already been
    emitted, a line-start singular ``grasa (<percent>%)`` is structurally
    impossible as a normal total-fat row. No numeric token is changed.
    """
    original = text or ""
    context_guarded, context_count = _guard_strong_ingredient_context(original)

    heading = _NUTRITION_HEADING.search(context_guarded)
    if heading is None:
        return context_guarded, bool(context_count)

    prefix = context_guarded[:heading.start()]
    tail = context_guarded[heading.start():]
    repaired, post_heading_count = _INGREDIENT_FAT_PERCENT_AT_LINE_START.subn(
        lambda match: f"{match.group(1)}grasa_ingrediente{match.group(2)}",
        tail,
    )
    return prefix + repaired, bool(context_count or post_heading_count)


def read_nutrition_label(text: str, *, extraction_confidence: float = 1.0) -> LabelReadResult:
    guarded, _ = guard_interleaved_ingredient_fat_percent(text)
    return _read_nutrition_label(
        guarded,
        extraction_confidence=extraction_confidence,
    )
