from __future__ import annotations

import re

from nutrition_label_reader import (
    LabelReadResult,
    _number_immediately_before,
    _nutrition_block,
    read_nutrition_label as _read_nutrition_label,
)

READER_VERSION = "1.0.3"


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
_BARE_QUANTITY_LINE_RE = re.compile(
    r"^\s*(\d{1,3}(?:\.\d{1,2})?)\s*(g|ml)\s*$",
    flags=re.I,
)
_MACRO_LABEL_LINE_RE = re.compile(
    r"^\s*(?:grasas?|l[ií]pidos?|grasa\s+total|hidratos?\s+de\s+carbono|carbohidratos?|prote[ií]nas?)\b",
    flags=re.I,
)
_ENERGY_CUE_RE = re.compile(
    r"\b(?:valor|energ[eé]tico|energ[ií]a|energia)\b",
    flags=re.I,
)
_KCAL_TOKEN_RE = re.compile(r"\b\d{1,4}(?:\.\d{1,2})?\s*kcal\b", flags=re.I)
_KJ_TOKEN_RE = re.compile(r"\b\d{1,5}(?:\.\d{1,2})?\s*k\s*j\b", flags=re.I)


def _energy_residual(nutrition: dict[str, float]) -> float:
    estimated = (
        9 * nutrition["fat_g"]
        + 4 * nutrition["carbohydrate_g"]
        + 4 * nutrition["protein_g"]
    )
    return abs(estimated - nutrition["calories"])


def _bare_multicolumn_ambiguity(result: LabelReadResult) -> bool:
    """Detect a narrow linearised two-column nutrition-table layout.

    PP-OCR can emit visual column headings such as `100 g | 26 g` as separate
    bare lines and then emit each row's two cells one after another. It can also
    split the energy label around those cells (`Valor ... Energético/Energia`).
    A normal label->next-number parser can consequently expose the serving value
    as a partial per-100-g observation. REVIEW partials are ensemble evidence, so
    the ambiguous tuple must be suppressed rather than allowed to corroborate a
    second OCR engine.

    Keep this deliberately narrow: require a bare 100 g/ml heading plus a
    different bare quantity of the same unit within the next few lines, then
    require an energy cue and duplicated explicit kJ or kcal observations before
    the first macro row. This avoids treating an unrelated package weight as a
    second nutrition column.
    """
    block = _nutrition_block(result.normalized_text)
    lines = block.splitlines()
    headings: list[tuple[int, float, str]] = []
    for index, line in enumerate(lines):
        match = _BARE_QUANTITY_LINE_RE.fullmatch(line)
        if match:
            headings.append((index, float(match.group(1)), match.group(2).lower()))

    for index, value, unit in headings:
        if abs(value - 100.0) > 0.01:
            continue
        serving_indexes = [
            other_index
            for other_index, other_value, other_unit in headings
            if other_unit == unit
            and 0 < other_index - index <= 4
            and abs(other_value - 100.0) > 0.01
        ]
        if not serving_indexes:
            continue

        last_heading = max(serving_indexes)
        end = min(len(lines), last_heading + 14)
        for probe in range(last_heading + 1, end):
            if _MACRO_LABEL_LINE_RE.search(lines[probe]):
                end = probe
                break
        energy_window = "\n".join(lines[last_heading + 1:end])
        if not _ENERGY_CUE_RE.search(energy_window):
            continue
        if (
            len(_KCAL_TOKEN_RE.findall(energy_window)) >= 2
            or len(_KJ_TOKEN_RE.findall(energy_window)) >= 2
        ):
            return True
    return False


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
    if _bare_multicolumn_ambiguity(result):
        reasons = result.reasons
        if "MULTIPLE_NUTRITION_COLUMNS" not in reasons:
            reasons = tuple(reasons) + ("MULTIPLE_NUTRITION_COLUMNS",)
        # As with row-order ambiguity below, do not leave a partial tuple that
        # another OCR engine could accidentally corroborate.
        return LabelReadResult(
            status="REVIEW",
            basis=result.basis,
            nutrition=None,
            confidence=min(result.confidence, 0.65),
            reasons=tuple(reasons),
            normalized_text=result.normalized_text,
        )

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
