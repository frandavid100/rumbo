from __future__ import annotations

import re

from nutrition_label_reader import (
    LabelReadResult,
    _number_immediately_before,
    _nutrition_block,
    read_nutrition_label as _read_nutrition_label,
)

READER_VERSION = "1.0.7"


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


def _estimated_energy(nutrition: dict[str, float]) -> float:
    return (
        9 * nutrition["fat_g"]
        + 4 * nutrition["carbohydrate_g"]
        + 4 * nutrition["protein_g"]
    )


def _energy_residual(nutrition: dict[str, float]) -> float:
    return abs(_estimated_energy(nutrition) - nutrition["calories"])


def _strict_energy_macro_mismatch(result: LabelReadResult) -> str | None:
    """Block complete Mercadona OCR tuples with a material energy mismatch.

    The generic reader keeps a wider tolerance because labelled energy can
    legitimately include fibre/polyols/organic acids. Mercadona OCR promotion
    is deliberately stricter: a complete tuple that differs by more than the
    larger of 8 kcal or 6% is not safe automatic evidence. Suppress its numeric
    tuple so multiple OCR engines cannot corroborate the same internally
    inconsistent reading into DECLARED.
    """
    if result.status != "DECLARED" or result.nutrition is None:
        return None
    required = ("calories", "fat_g", "carbohydrate_g", "protein_g")
    if any(result.nutrition.get(key) is None for key in required):
        return None
    nutrition = {key: float(result.nutrition[key]) for key in required}
    tolerance = max(8.0, nutrition["calories"] * 0.06)
    if _energy_residual(nutrition) <= tolerance:
        return None
    return f"ENERGY_MACRO_MISMATCH_STRICT:{_estimated_energy(nutrition):.1f}"


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


def _complete_value_before_label_rescue(
    result: LabelReadResult,
    *,
    extraction_confidence: float,
) -> LabelReadResult | None:
    """Recover one fully evidenced single-column value-before-label layout.

    PP-OCR can linearise a single visual nutrition table by reading the numeric
    column immediately before each macro label. A later parser improvement may
    correctly recover one of those reversed rows while leaving another macro
    missing; that partial REVIEW must not disable the all-or-nothing rescue.

    Accept the reversed layout only when all three macro rows independently
    expose exact standalone gram values immediately before their labels, the
    basis and calories are explicit, the source extraction itself meets the
    DECLARED confidence floor, and the resulting four-field tuple is near-exactly
    energy coherent. For a REVIEW input, only a plain missing-core/energy-mismatch
    or conservative single-reversed-macro candidate result is eligible;
    multicolumn, impossible-value, low-confidence and other safety reviews remain blocked.
    """
    if result.status not in {"DECLARED", "REVIEW"} or result.nutrition is None:
        return None
    if result.basis not in {"100_g", "100_ml"}:
        return None
    if extraction_confidence < .85:
        return None
    if result.nutrition.get("calories") is None:
        return None

    if result.status == "REVIEW":
        recoverable_reversed_evidence = any(
            reason.startswith("MISSING_CORE:")
            or reason.startswith("SINGLE_REVERSED_MACRO_CANDIDATE:")
            for reason in result.reasons
        )
        if not recoverable_reversed_evidence:
            return None
        if any(
            not (
                reason.startswith("MISSING_CORE:")
                or reason.startswith("ENERGY_MACRO_MISMATCH:")
                or reason.startswith("SINGLE_REVERSED_MACRO_CANDIDATE:")
            )
            for reason in result.reasons
        ):
            return None

    block = _nutrition_block(result.normalized_text)
    preceding = {
        key: _number_immediately_before(patterns, block)
        for key, patterns in _MACRO_PATTERNS.items()
    }
    if any(value is None for value in preceding.values()):
        return None

    rescued = {
        "calories": float(result.nutrition["calories"]),
        **{key: float(value) for key, value in preceding.items()},
    }
    if any(rescued[key] < 0 or rescued[key] > 100 for key in _MACRO_PATTERNS):
        return None

    rescued_residual = _energy_residual(rescued)
    near_exact = rescued_residual <= max(6.0, rescued["calories"] * 0.03)
    if not near_exact:
        return None

    if result.status == "DECLARED":
        required = ("calories", "fat_g", "carbohydrate_g", "protein_g")
        if any(result.nutrition.get(key) is None for key in required):
            return None
        current = {key: float(result.nutrition[key]) for key in required}
        if all(abs(rescued[key] - current[key]) <= 0.05 for key in _MACRO_PATTERNS):
            return None
        current_residual = _energy_residual(current)
        material_improvement = (
            current_residual - rescued_residual
            >= max(6.0, rescued["calories"] * 0.02)
        )
        if not material_improvement:
            return None

    return LabelReadResult(
        status="DECLARED",
        basis=result.basis,
        nutrition=rescued,
        confidence=min(1.0, extraction_confidence),
        reasons=tuple(result.reasons) + ("VALUE_BEFORE_LABEL_RESCUED",),
        normalized_text=result.normalized_text,
    )


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

    rescued = _complete_value_before_label_rescue(
        result,
        extraction_confidence=extraction_confidence,
    )
    candidate = rescued if rescued is not None else result
    strict_mismatch = _strict_energy_macro_mismatch(candidate)
    if strict_mismatch is not None:
        return LabelReadResult(
            status="REVIEW",
            basis=candidate.basis,
            nutrition=None,
            confidence=min(candidate.confidence, 0.65),
            reasons=tuple(candidate.reasons) + (strict_mismatch,),
            normalized_text=candidate.normalized_text,
        )
    if rescued is not None:
        return rescued

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
