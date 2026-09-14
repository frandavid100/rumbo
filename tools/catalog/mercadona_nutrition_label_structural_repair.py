from __future__ import annotations

"""Mercadona-only structural OCR repairs backed by observed label layouts.

Keep these repairs out of the generic nutrition parser: they are narrow recovery
rules for first-party Mercadona label OCR. No numeric value is invented. A value
is exposed only when it is present in the OCR text as a dedicated gram-like cell.
"""

import re

from mercadona_nutrition_label_reader import (
    LabelReadResult,
    read_nutrition_label as _read_nutrition_label,
)
from nutrition_label_reader import _fold, _number_immediately_before, _nutrition_block

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
_HARD_REASON_PREFIXES = (
    "MULTIPLE_NUTRITION_COLUMNS",
    "ENERGY_MACRO_MISMATCH_STRICT",
)
# Exact observed product-21649 failure: after the reversed carbohydrate cell,
# whole-pack OCR emits `500 g / Peso Neto`. The forward row reader can bind that
# package weight to Hidratos de Carbono and correctly flags it impossible. It is
# safe to discard only this specific forward failure when all three core macro
# rows independently expose dedicated immediately-preceding gram cells and the
# resulting tuple is near-exactly energy coherent. Other impossible values remain
# hard blockers.
_ALLOWED_FORWARD_NOISE_REASONS = frozenset({"IMPOSSIBLE_CARBOHYDRATE_G"})


def _repair_observed_row_label_typos(text: str) -> str:
    """Repair only entire OCR row labels observed on product 27905.

    In particular, do not rewrite inline `Proleinas 9`: Tesseract sometimes loses
    the printed zero and leaves only a g-like `9` glyph. Turning that line into a
    recognised protein row would manufacture a false 9 g observation.
    """
    text = re.sub(
        r"(?im)^([ \t]*)prole[ií]nas?([ \t]*[:;]?[ \t]*)$",
        r"\1Proteinas\2",
        text or "",
    )
    text = re.sub(
        r"(?im)^([ \t]*)hidralos? de carbono([ \t]*[:;]?[ \t]*)$",
        r"\1Hidratos de Carbono\2",
        text,
    )
    return text


def _energy_residual(nutrition: dict[str, float]) -> float:
    estimated = (
        9.0 * nutrition["fat_g"]
        + 4.0 * nutrition["carbohydrate_g"]
        + 4.0 * nutrition["protein_g"]
    )
    return abs(estimated - nutrition["calories"])


def _contiguous_preceding_gram_cells(
    label_patterns: tuple[str, ...],
    text: str,
    *,
    max_cells: int = 2,
) -> tuple[float, ...]:
    """Return only contiguous dedicated gram-like cells before a row label.

    Product 4491 exposed a two-column OCR ordering where the per-100-g protein
    cell and the whole-pack protein cell were emitted as two consecutive lines
    immediately before `Proteínas`. The generic single-cell helper necessarily
    sees only the nearest (whole-pack) value. This helper is deliberately bounded
    to at most two contiguous numeric cells and never skips prose or another row.
    """
    folded = _fold(text)
    for label in label_patterns:
        for label_match in re.finditer(label, folded, flags=re.I):
            head = folded[max(0, label_match.start() - 120):label_match.start()].rstrip()
            lines = head.splitlines()
            values: list[float] = []
            for line in reversed(lines):
                if len(values) >= max_cells:
                    break
                cell = re.fullmatch(
                    r"\s*([<>]?)\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:g|9|q|yg|y)\s*",
                    line,
                    flags=re.I,
                )
                if cell is None:
                    break
                if cell.group(1) in ("<", ">"):
                    return tuple()
                value = float(cell.group(2))
                if not 0.0 <= value <= 100.0:
                    return tuple()
                values.append(value)
            if values:
                return tuple(values)
    return tuple()


def _single_macro_two_cell_value_before_label_evidence(
    result: LabelReadResult,
    *,
    extraction_confidence: float,
) -> LabelReadResult | None:
    """Expose one uniquely coherent per-100 macro from a two-cell reversed row.

    This never makes a single OCR reading usable. It only turns an otherwise
    missing macro into REVIEW evidence when exactly two dedicated gram cells sit
    immediately before the one missing macro label and exactly one of those two
    values yields a near-exact energy-coherent complete tuple. A later independent
    OCR family must still corroborate the field before ensemble promotion.
    """
    if result.status != "REVIEW":
        return None
    if result.basis not in {"100_g", "100_ml"} or extraction_confidence < .85:
        return None
    if any(
        not str(reason).startswith("MISSING_CORE:")
        for reason in result.reasons
    ):
        return None

    nutrition = dict(result.nutrition or {})
    calories = nutrition.get("calories")
    if not isinstance(calories, (int, float)):
        return None

    missing = [key for key in _MACRO_PATTERNS if key not in nutrition]
    if len(missing) != 1:
        return None
    key = missing[0]

    block = _nutrition_block(result.normalized_text)
    cells = _contiguous_preceding_gram_cells(_MACRO_PATTERNS[key], block, max_cells=2)
    if len(cells) != 2:
        return None

    coherent_values: list[float] = []
    for value in cells:
        complete = dict(nutrition)
        complete[key] = value
        if any(field not in complete for field in ("calories", "fat_g", "carbohydrate_g", "protein_g")):
            continue
        complete_nutrition = {
            field: float(complete[field])
            for field in ("calories", "fat_g", "carbohydrate_g", "protein_g")
        }
        if _energy_residual(complete_nutrition) <= max(6.0, complete_nutrition["calories"] * .03):
            coherent_values.append(value)

    unique = sorted(set(coherent_values))
    if len(unique) != 1:
        return None

    nutrition[key] = unique[0]
    cleaned_reasons = tuple(
        reason for reason in result.reasons
        if not str(reason).startswith("MISSING_CORE:")
    )
    return LabelReadResult(
        status="REVIEW",
        basis=result.basis,
        nutrition={
            field: float(nutrition[field])
            for field in ("calories", "fat_g", "carbohydrate_g", "protein_g")
        },
        confidence=min(extraction_confidence, .84),
        reasons=cleaned_reasons + (
            f"SINGLE_REVERSED_MACRO_CANDIDATE:{key}",
            f"MERCADONA_TWO_CELL_VALUE_BEFORE_LABEL_EVIDENCE:{key}",
        ),
        normalized_text=result.normalized_text,
    )


def _full_value_before_label_evidence(
    result: LabelReadResult,
    *,
    extraction_confidence: float,
) -> LabelReadResult | None:
    """Recover an all-three-macro value-before-label OCR ordering.

    The gate is structural rather than inferential: every core macro label must
    have its own dedicated gram-like cell on the immediately preceding OCR line.
    That cannot be satisfied by the usual forward label/value layout because the
    first macro row (fat) follows energy rather than a standalone gram cell.

    A complete tuple is usable only with explicit basis, high extraction
    confidence and near-exact energy coherence. Otherwise the observed reversed
    macro cells remain REVIEW evidence only, so a separate OCR family must still
    corroborate them before ensemble promotion.
    """
    if result.status == "NOT_NUTRITION_LABEL":
        return None
    if any(str(reason).startswith(_HARD_REASON_PREFIXES) for reason in result.reasons):
        return None

    impossible_reasons = {
        str(reason)
        for reason in result.reasons
        if str(reason).startswith("IMPOSSIBLE_")
    }
    if impossible_reasons - _ALLOWED_FORWARD_NOISE_REASONS:
        return None

    block = _nutrition_block(result.normalized_text)
    preceding = {
        key: _number_immediately_before(patterns, block)
        for key, patterns in _MACRO_PATTERNS.items()
    }
    if any(value is None for value in preceding.values()):
        return None

    nutrition = dict(result.nutrition or {})
    nutrition.update({key: float(value) for key, value in preceding.items()})
    if any(not (0.0 <= nutrition[key] <= 100.0) for key in _MACRO_PATTERNS):
        return None

    cleaned_reasons = tuple(
        reason for reason in result.reasons
        if not (
            reason.startswith("MISSING_CORE:")
            or reason.startswith("ENERGY_MACRO_MISMATCH:")
            or reason.startswith("SINGLE_REVERSED_MACRO_CANDIDATE:")
            or reason in _ALLOWED_FORWARD_NOISE_REASONS
        )
    )
    discarded_forward_noise = tuple(
        f"FORWARD_{reason}_DISCARDED"
        for reason in sorted(impossible_reasons & _ALLOWED_FORWARD_NOISE_REASONS)
    )

    calories = nutrition.get("calories")
    if isinstance(calories, (int, float)):
        complete = {
            "calories": float(calories),
            "fat_g": float(nutrition["fat_g"]),
            "carbohydrate_g": float(nutrition["carbohydrate_g"]),
            "protein_g": float(nutrition["protein_g"]),
        }
        near_exact = _energy_residual(complete) <= max(6.0, complete["calories"] * 0.03)
        if not near_exact:
            return None
        if result.basis in {"100_g", "100_ml"} and extraction_confidence >= .85:
            return LabelReadResult(
                status="DECLARED",
                basis=result.basis,
                nutrition=complete,
                confidence=min(1.0, extraction_confidence),
                reasons=cleaned_reasons + discarded_forward_noise + ("FULL_VALUE_BEFORE_LABEL_STRUCTURE",),
                normalized_text=result.normalized_text,
            )
        nutrition = complete

    return LabelReadResult(
        status="REVIEW",
        basis=result.basis,
        nutrition=nutrition or None,
        confidence=min(result.confidence, extraction_confidence, .84),
        reasons=cleaned_reasons + discarded_forward_noise + ("FULL_VALUE_BEFORE_LABEL_PARTIAL_EVIDENCE",),
        normalized_text=result.normalized_text,
    )


def read_nutrition_label(text: str, *, extraction_confidence: float = 1.0) -> LabelReadResult:
    repaired_text = _repair_observed_row_label_typos(text)
    result = _read_nutrition_label(
        repaired_text,
        extraction_confidence=extraction_confidence,
    )
    structural = _full_value_before_label_evidence(
        result,
        extraction_confidence=extraction_confidence,
    )
    if structural is not None:
        return structural
    two_cell = _single_macro_two_cell_value_before_label_evidence(
        result,
        extraction_confidence=extraction_confidence,
    )
    return two_cell if two_cell is not None else result
