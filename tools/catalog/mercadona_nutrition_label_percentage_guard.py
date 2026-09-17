from __future__ import annotations

"""Mercadona-only guards against ingredient OCR noise masquerading as fat rows.

Whole-pack OCR can interleave an ingredients column around the visible nutrition
table. A line such as ``grasa (16%). emulgente ...`` can then start at a line
boundary and look like a total-fat label even though the number is an ingredient
percentage, not grams per 100 g/ml. Likewise an additive fragment such as
``129 E129:`` can be emitted immediately after ``Grasas/Lípidos`` and a generic
OCR repair can otherwise mistake ``129`` for damaged ``12 g``.

These guards invent no nutrition value and do not infer a missing macro. They
only make narrowly identified ingredient shapes ineligible as nutrition-row
values; the ordinary Mercadona structural reader must still recover and validate
all four macros, basis and energy coherence from explicit OCR evidence.
"""

import re

from mercadona_nutrition_label_structural_repair import (
    LabelReadResult,
    read_nutrition_label as _read_nutrition_label,
)

READER_VERSION = "1.0.2"

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
_INTERLEAVED_E_NUMBER_AFTER_FAT_LABEL = re.compile(
    r"(?im)^([ \t]*[\[|]?[ \t]*(?:grasas?|l[ií]pidos)"
    r"(?:[ \t]*/[ \t]*(?:grasas?|l[ií]pidos))?[ \t]*\n)"
    r"([ \t]*)(\d{2,3})([ \t]+E[ \t]*\3[ \t]*:)"
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


def _guard_interleaved_e_number_after_fat_label(text: str) -> tuple[str, int]:
    """Mark a mirrored additive token as prose without changing its numbers.

    The narrowly observed shape is a fat label followed on the next OCR line by
    ``NNN ENNN:``. The repeated number is characteristic of an ingredient
    additive code, not a nutrition cell. Prefixing that line with ``ingrediente``
    causes the downstream parser's existing prose guard to reject it. Both the
    numeric token and the E-code remain verbatim in normalized OCR evidence.
    """
    return _INTERLEAVED_E_NUMBER_AFTER_FAT_LABEL.subn(
        lambda match: (
            f"{match.group(1)}{match.group(2)}ingrediente "
            f"{match.group(3)}{match.group(4)}"
        ),
        text or "",
    )


def guard_interleaved_ingredient_fat_percent(text: str) -> tuple[str, bool]:
    """Disable only narrow ingredient shapes that can imitate total-fat rows.

    ``grasa (<percent>%)`` is rewritten to ``grasa_ingrediente``. The underscore
    deliberately removes the word boundary required by the downstream fat-row
    regex while retaining the original percentage and surrounding OCR text for
    audit. A mirrored ``NNN ENNN:`` line after a fat label instead receives only
    an ``ingrediente`` prose marker, preserving both numeric tokens verbatim.

    No macro is supplied by these guards. The structural reader and ordinary
    energy/tuple checks remain solely responsible for acceptance.
    """
    original = text or ""
    e_number_guarded, e_number_count = _guard_interleaved_e_number_after_fat_label(original)
    context_guarded, context_count = _guard_strong_ingredient_context(e_number_guarded)

    heading = _NUTRITION_HEADING.search(context_guarded)
    if heading is None:
        return context_guarded, bool(e_number_count or context_count)

    prefix = context_guarded[:heading.start()]
    tail = context_guarded[heading.start():]
    repaired, post_heading_count = _INGREDIENT_FAT_PERCENT_AT_LINE_START.subn(
        lambda match: f"{match.group(1)}grasa_ingrediente{match.group(2)}",
        tail,
    )
    return prefix + repaired, bool(e_number_count or context_count or post_heading_count)


def read_nutrition_label(text: str, *, extraction_confidence: float = 1.0) -> LabelReadResult:
    guarded, _ = guard_interleaved_ingredient_fat_percent(text)
    return _read_nutrition_label(
        guarded,
        extraction_confidence=extraction_confidence,
    )
