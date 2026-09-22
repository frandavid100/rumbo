from __future__ import annotations

import re


# Narrow repair for a real Mercadona/Tesseract failure mode in which the printed
# terminal `g` unit is read as `8`, producing tokens such as `12.208` from
# `12.20 g` or `1.008` from `1.00 g`. This is deliberately not a generic decimal
# repair. It is allowed only on an exact core-nutrient row, requires another
# explicit gram unit elsewhere in the same OCR observation, and rejects bounds,
# suffixes, prose and non-core rows.
_CORE_LABEL = r"(?:grasas?|hidratos?\s+de\s+carbono|carbohidratos?|prote[ií]nas?)"
_STANDALONE_LABEL_RE = re.compile(rf"^\s*{_CORE_LABEL}\s*:?[ \t]*$", re.I)
_STANDALONE_VALUE_RE = re.compile(r"^(\s*)(\d{1,3}[\.,]\d{1,2})8(\s*)$")
_SAME_LINE_RE = re.compile(
    rf"^(\s*{_CORE_LABEL}\s*:?[ \t]+)(\d{{1,3}}[\.,]\d{{1,2}})8(\s*)$",
    re.I,
)
_EXPLICIT_GRAM_ELSEWHERE_RE = re.compile(r"\b\d{1,3}(?:[\.,]\d{1,3})?\s*g\b", re.I)


def repair_observed_trailing_g_as_eight(text: str) -> str:
    """Repair only row-anchored Tesseract `g` -> `8` unit substitutions.

    No missing numeric value is inferred: the complete numeric token is already
    present and only the observed unit glyph is normalized. Three-decimal values
    outside an exact core nutrition row are preserved verbatim.
    """
    if not text or not _EXPLICIT_GRAM_ELSEWHERE_RE.search(text):
        return text

    lines = text.splitlines(keepends=True)
    out: list[str] = []
    previous_core_label = False

    for line in lines:
        newline = ""
        body = line
        if line.endswith("\r\n"):
            body, newline = line[:-2], "\r\n"
        elif line.endswith("\n"):
            body, newline = line[:-1], "\n"
        elif line.endswith("\r"):
            body, newline = line[:-1], "\r"

        same_line = _SAME_LINE_RE.fullmatch(body)
        if same_line:
            body = f"{same_line.group(1)}{same_line.group(2)} g{same_line.group(3)}"
            previous_core_label = False
            out.append(body + newline)
            continue

        standalone_value = _STANDALONE_VALUE_RE.fullmatch(body)
        if previous_core_label and standalone_value:
            body = f"{standalone_value.group(1)}{standalone_value.group(2)} g{standalone_value.group(3)}"

        current_core_label = bool(_STANDALONE_LABEL_RE.fullmatch(body))
        # Adjacency is strict: blank/prose/other rows break the relationship.
        previous_core_label = current_core_label
        out.append(body + newline)

    return "".join(out)
