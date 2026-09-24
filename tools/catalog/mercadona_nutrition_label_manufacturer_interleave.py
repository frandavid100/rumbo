from __future__ import annotations

"""Narrow Mercadona repairs/guards for OCR-linearised nutrition rows.

Two first-party layouts are handled conservatively here rather than weakening the
generic label parser:

* product 21649: PP-OCRv6 linearises the protein value as ``6.7 g /
  Fabricado/Producido por: ... / Proteínas`` while fat and carbohydrate remain
  ordinary value-before-label rows. The existing repair can promote only that
  tightly constrained, fully explicit and energy-coherent tuple.
* product 3680: column reading order becomes ``6 g / Grasas / 2.2 g / de las
  cuales saturadas`` and ``19 g / Proteínas / 0.20 g / Sal``. In that shape the
  generic row parser can mis-attach the subrow/salt values to total fat/protein.
  The guard below only withholds those suspect partial fields; it never supplies
  the preceding values and therefore cannot create usable nutrition.
* whole-package Mercadona OCR can read printed prose such as ``100% MALTA`` as
  ``1009 MALTA``. Basis recovery therefore prefers an explicit contextual
  ``por/per/cada 100 ml|g`` heading and accepts loose OCR unit glyphs only when
  they are a standalone basis row. This prevents package prose from changing a
  per-100-ml table into a per-100-g record.
"""

import re

from mercadona_nutrition_label_percentage_guard import (
    LabelReadResult,
    read_nutrition_label as _read_nutrition_label,
)
from nutrition_label_reader import _fold, _number_immediately_before, _nutrition_block

READER_VERSION = "1.1.1"

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
_SHIFT_REASON = "MERCADONA_SHIFTED_SUBROW_VALUE_WITHHELD"
_BASIS_CORRECTED_REASON = "MERCADONA_CONTEXTUAL_BASIS_CORRECTED"
_BASIS_WITHHELD_REASON = "MERCADONA_NONCONTEXTUAL_BASIS_WITHHELD"


def _mercadona_basis(text: str) -> str | None:
    """Recover a per-100 basis without treating inline package prose as a unit.

    ``9/q/y/yg`` remain accepted OCR substitutions for a printed ``g``, but only
    with a contextual basis prefix or as a complete standalone row. In
    particular, inline text such as ``1009 MALTA`` is not a 100-g basis.
    Explicit ml/g headings are checked before standalone OCR fallbacks so a real
    ``por 100 ml`` heading cannot be overridden by unrelated package text.
    """
    folded = _fold(text)
    prefix = r"(?:por|cada|per|pr|valores? medios? por)"
    gram = r"(?:g|9|q|yg|y)"
    millilitre = r"m(?:l|i|1)"

    explicit_ml = bool(re.search(
        rf"\b{prefix}\s*100\s*{millilitre}\b",
        folded,
        flags=re.I,
    ))
    explicit_g = bool(re.search(
        rf"\b{prefix}\s*100\s*{gram}\b",
        folded,
        flags=re.I,
    ))
    if explicit_ml != explicit_g:
        return "100_ml" if explicit_ml else "100_g"
    if explicit_ml and explicit_g:
        return None

    standalone_ml = bool(re.search(
        rf"(?im)^\s*100\s*{millilitre}\s*$",
        folded,
    ))
    standalone_g = bool(re.search(
        rf"(?im)^\s*100\s*{gram}\s*$",
        folded,
    ))
    if standalone_ml != standalone_g:
        return "100_ml" if standalone_ml else "100_g"
    return None


def _apply_mercadona_basis_guard(result: LabelReadResult) -> LabelReadResult:
    """Correct or withhold only the basis; never manufacture nutrition values."""
    contextual = _mercadona_basis(result.normalized_text)
    if contextual == result.basis:
        return result

    if contextual is None:
        if result.basis is None:
            return result
        reasons = tuple(result.reasons) + (_BASIS_WITHHELD_REASON,)
        return LabelReadResult(
            status="REVIEW",
            basis=None,
            nutrition=result.nutrition,
            confidence=min(result.confidence, .75),
            reasons=reasons,
            normalized_text=result.normalized_text,
        )

    reasons = tuple(result.reasons) + (_BASIS_CORRECTED_REASON,)
    return LabelReadResult(
        status=result.status,
        basis=contextual,
        nutrition=result.nutrition,
        confidence=result.confidence,
        reasons=reasons,
        normalized_text=result.normalized_text,
    )


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


def _has_shifted_fat_subrow(block: str) -> bool:
    """Detect only ``value / Grasas / value / de las cuales saturadas``."""
    folded = _fold(block)
    for label in _FAT_PATTERNS:
        for match in re.finditer(label, folded, flags=re.I):
            if _number_immediately_before((label,), block) is None:
                continue
            tail = folded[match.end():match.end() + 120]
            if re.match(
                r"\s*[:;|]?\s*[<>]?\s*\d{1,3}(?:\.\d{1,2})?\s*"
                r"(?:g|9|q|yg|y)?\s*\n\s*de\s+las\s+cuales\s+saturad",
                tail,
                flags=re.I,
            ):
                return True
    return False


def _has_shifted_protein_salt_row(block: str) -> bool:
    """Detect ``value / Proteínas / value / Sal`` when Sal has no own value cell.

    The value after ``Proteínas`` is then structurally ambiguous and must not be
    exposed as protein evidence. We deliberately do not adopt the explicit value
    before the label here; that requires independent OCR corroboration downstream.
    """
    folded = _fold(block)
    cell = r"[<>]?\s*\d{1,3}(?:\.\d{1,2})?\s*(?:g|9|q|yg|y)"
    for label in _PROTEIN_PATTERNS:
        for match in re.finditer(label, folded, flags=re.I):
            if _number_immediately_before((label,), block) is None:
                continue
            tail = folded[match.end():match.end() + 140]
            forward_then_salt = re.match(
                rf"\s*[:;|]?\s*{cell}\s*\n\s*sal\s*[:;|]?(?=\s*\n|\s*$)",
                tail,
                flags=re.I,
            )
            if not forward_then_salt:
                continue
            after_salt = tail[forward_then_salt.end():]
            if re.match(rf"\s*\n?\s*{cell}(?:\s|$)", after_salt, flags=re.I):
                continue
            return True
    return False


def _withhold_shifted_subrow_values(result: LabelReadResult) -> LabelReadResult:
    """Remove only structurally mis-attached fat/protein partial evidence.

    This guard is safety-only: it never fills a missing field and always returns
    REVIEW when it changes anything, even if the generic parser happened to emit
    DECLARED. Thus it can reduce recall but cannot promote a REVIEW observation.
    """
    if not result.nutrition:
        return result
    block = _nutrition_block(result.normalized_text)
    suspect: list[str] = []
    if "fat_g" in result.nutrition and _has_shifted_fat_subrow(block):
        suspect.append("fat_g")
    if "protein_g" in result.nutrition and _has_shifted_protein_salt_row(block):
        suspect.append("protein_g")
    if not suspect:
        return result

    nutrition = dict(result.nutrition)
    for field in suspect:
        nutrition.pop(field, None)
    reasons = tuple(result.reasons) + tuple(f"{_SHIFT_REASON}:{field}" for field in suspect)
    missing = [field for field in ("calories", "fat_g", "carbohydrate_g", "protein_g") if field not in nutrition]
    if missing and not any(str(reason).startswith("MISSING_CORE:") for reason in reasons):
        reasons += ("MISSING_CORE:" + ",".join(missing),)
    return LabelReadResult(
        status="REVIEW",
        basis=result.basis,
        nutrition=nutrition or None,
        confidence=min(result.confidence, .60),
        reasons=reasons,
        normalized_text=result.normalized_text,
    )


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
    result = _apply_mercadona_basis_guard(result)
    result = _withhold_shifted_subrow_values(result)
    repaired = _repair_manufacturer_interleave(
        result,
        extraction_confidence=extraction_confidence,
    )
    return repaired if repaired is not None else result
