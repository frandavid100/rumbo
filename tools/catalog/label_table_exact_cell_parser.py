from __future__ import annotations

"""Exact parser for geometry-isolated nutrition table cells.

It accepts only values explicitly printed inside an already-isolated cell. It
never repairs missing decimal punctuation, converts kJ to kcal, promotes bounds,
or chooses between multiple numeric candidates.
"""

import re
import unicodedata

EXACT_CELL_PARSER_VERSION = "1.0.0"
CORE_FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")

_NUMBER = r"(?:0|[1-9]\d{0,4})(?:[.,]\d{1,2})?"
_NUMERIC_LEXEME_RE = re.compile(r"(?<!\d)\d+(?:[.,]\d+)?")
_COMPARATOR_RE = re.compile(r"[<>≤≥]")


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    normalized = normalized.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _value(raw: str) -> float:
    return float(raw.replace(",", "."))


def _ambiguous_leading_zero(raw: str) -> bool:
    integer = re.split(r"[.,]", raw, maxsplit=1)[0]
    return len(integer) > 1 and integer.startswith("0")


def _result(*, field: str, raw_text: str, status: str,
            value: float | None = None, unit: str | None = None,
            reason: str | None = None,
            corroborating_kj: float | None = None) -> dict[str, object]:
    result: dict[str, object] = {
        "parser_version": EXACT_CELL_PARSER_VERSION,
        "field": field,
        "raw_text": raw_text,
        "status": status,
        "exact_value": value,
        "unit": unit,
        "missing_value_inferred": False,
        "decimal_repaired": False,
        "unit_converted": False,
    }
    if reason is not None:
        result["reason"] = reason
    if corroborating_kj is not None:
        result["corroborating_kj"] = corroborating_kj
    return result


def _reject(field: str, raw_text: str, reason: str) -> dict[str, object]:
    return _result(field=field, raw_text=raw_text, status="REJECTED", reason=reason)


def _coherent_kj_kcal_pair(kj: float, kcal: float) -> bool:
    if kj < 0 or kcal < 0:
        return False
    expected_kj = kcal * 4.184
    tolerance_kj = max(2.0, expected_kj * 0.08)
    return abs(kj - expected_kj) <= tolerance_kj


def _parse_macro(field: str, raw_text: str, normalized: str) -> dict[str, object]:
    if _COMPARATOR_RE.search(normalized):
        return _reject(field, raw_text, "NON_EXACT_COMPARATOR")

    match = re.fullmatch(rf"({_NUMBER})\s*g", normalized, flags=re.I)
    if not match:
        numeric_count = len(_NUMERIC_LEXEME_RE.findall(normalized))
        if numeric_count > 1:
            return _reject(field, raw_text, "MULTIPLE_NUMERIC_CANDIDATES")
        if numeric_count == 1:
            return _reject(field, raw_text, "MISSING_OR_UNSUPPORTED_GRAM_UNIT")
        return _reject(field, raw_text, "NO_EXPLICIT_NUMERIC_VALUE")

    raw_number = match.group(1)
    if _ambiguous_leading_zero(raw_number):
        return _reject(field, raw_text, "AMBIGUOUS_LEADING_ZERO")

    value = _value(raw_number)
    if value > 100:
        return _reject(field, raw_text, "OUT_OF_RANGE_MACRO")
    return _result(field=field, raw_text=raw_text, status="EXACT_VALUE",
                   value=value, unit="g")


def _parse_energy(field: str, raw_text: str, normalized: str) -> dict[str, object]:
    if _COMPARATOR_RE.search(normalized):
        return _reject(field, raw_text, "NON_EXACT_COMPARATOR")

    kj_unit = r"k\s*j"
    kcal_unit = r"k\s*cal"
    forward = re.fullmatch(
        rf"({_NUMBER})\s*{kj_unit}\s*(?:[/\\|]\s*)?({_NUMBER})\s*{kcal_unit}",
        normalized,
        flags=re.I,
    )
    reverse = re.fullmatch(
        rf"({_NUMBER})\s*{kcal_unit}\s*(?:[/\\|]\s*)?({_NUMBER})\s*{kj_unit}",
        normalized,
        flags=re.I,
    )
    if forward or reverse:
        if forward:
            raw_kj, raw_kcal = forward.group(1), forward.group(2)
        else:
            raw_kcal, raw_kj = reverse.group(1), reverse.group(2)
        if _ambiguous_leading_zero(raw_kj) or _ambiguous_leading_zero(raw_kcal):
            return _reject(field, raw_text, "AMBIGUOUS_LEADING_ZERO")
        kj = _value(raw_kj)
        kcal = _value(raw_kcal)
        if kcal > 1000 or kj > 5000:
            return _reject(field, raw_text, "OUT_OF_RANGE_ENERGY")
        if not _coherent_kj_kcal_pair(kj, kcal):
            return _reject(field, raw_text, "INCOHERENT_KJ_KCAL_PAIR")
        return _result(
            field=field,
            raw_text=raw_text,
            status="EXACT_VALUE",
            value=kcal,
            unit="kcal",
            corroborating_kj=kj,
        )

    single = re.fullmatch(rf"({_NUMBER})\s*{kcal_unit}", normalized, flags=re.I)
    if single:
        raw_kcal = single.group(1)
        if _ambiguous_leading_zero(raw_kcal):
            return _reject(field, raw_text, "AMBIGUOUS_LEADING_ZERO")
        kcal = _value(raw_kcal)
        if kcal > 1000:
            return _reject(field, raw_text, "OUT_OF_RANGE_ENERGY")
        if kcal < 10:
            return _reject(field, raw_text, "LOW_KCAL_REQUIRES_COHERENT_KJ_PAIR")
        return _result(field=field, raw_text=raw_text, status="EXACT_VALUE",
                       value=kcal, unit="kcal")

    numeric_count = len(_NUMERIC_LEXEME_RE.findall(normalized))
    if numeric_count > 1:
        return _reject(field, raw_text, "MULTIPLE_OR_UNSUPPORTED_ENERGY_NUMBERS")
    if numeric_count == 1:
        return _reject(field, raw_text, "MISSING_OR_UNSUPPORTED_KCAL_UNIT")
    return _reject(field, raw_text, "NO_EXPLICIT_NUMERIC_VALUE")


def parse_exact_nutrition_cell(field: str, raw_text: str) -> dict[str, object]:
    """Parse one geometry-isolated cell without inference or candidate selection."""
    if field not in CORE_FIELDS:
        raise ValueError(f"unsupported nutrition field: {field!r}")
    normalized = _normalize(raw_text)
    if not normalized:
        return _reject(field, str(raw_text or ""), "EMPTY_CELL")
    if field == "calories":
        return _parse_energy(field, str(raw_text), normalized)
    return _parse_macro(field, str(raw_text), normalized)
