from __future__ import annotations

from dataclasses import dataclass, replace
import re
import unicodedata

from mercadona_nutrition_label_percentage_guard import LabelReadResult, read_nutrition_label


CORE_FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")


@dataclass(frozen=True)
class ExplicitServingColumnProjection:
    """A conservative projection of an explicit per-100 + serving-size table.

    Both columns must be visibly present in one OCR observation.  This object
    never invents a missing value: it merely identifies which of two observed
    values is the explicit per-100 value after checking the printed serving-size
    ratio on every core row.
    """

    result: LabelReadResult
    serving_amount: float
    serving_unit: str
    observed_pairs: dict[str, tuple[float, float]]


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _clean_lines(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text or "").replace(",", ".")
    return [line.strip() for line in normalized.splitlines() if line.strip()]


def _header(line: str):
    match = re.fullmatch(r"(\d{1,3}(?:\.\d{1,2})?)\s*(g|ml)", _fold(line).strip())
    if not match:
        return None
    return float(match.group(1)), match.group(2)


def _numeric_cell(line: str, unit: str):
    folded = _fold(line).strip()
    expected = "kcal" if unit == "kcal" else "g"
    match = re.fullmatch(rf"(\d{{1,4}}(?:\.\d{{1,2}})?)\s*{expected}", folded)
    if not match:
        return None
    return float(match.group(1))


def _label_indices(lines: list[str], field: str) -> list[int]:
    folded = [_fold(line) for line in lines]
    if field == "calories":
        return [i for i, line in enumerate(folded) if "energet" in line or re.search(r"\benergia\b", line)]
    if field == "fat_g":
        return [
            i for i, line in enumerate(folded)
            if re.search(r"\bgrasas?\b", line) or re.search(r"\blipidos?\b", line)
        ]
    if field == "carbohydrate_g":
        return [
            i for i, line in enumerate(folded)
            if "hidratos de carbono" in line or re.search(r"\bcarbohidratos?\b", line)
        ]
    if field == "protein_g":
        return [i for i, line in enumerate(folded) if re.search(r"\bproteinas?\b", line)]
    raise ValueError(field)


def _row_pair(lines: list[str], label_index: int, unit: str):
    """Read exactly two explicit cells adjacent to one row label.

    Normal OCR order is label/value/value.  One observed Mercadona layout emits
    the serving-size cell immediately before the row label and the per-100 cell
    immediately after it.  That reversed shape is allowed only when there is
    exactly one post-label cell; arbitrary prose or a third numeric cell makes
    the row ineligible.
    """

    after: list[float] = []
    for line in lines[label_index + 1:label_index + 4]:
        value = _numeric_cell(line, unit)
        if value is not None:
            after.append(value)
    if len(after) == 2:
        return after[0], after[1]
    if len(after) != 1 or label_index == 0:
        return None
    before = _numeric_cell(lines[label_index - 1], unit)
    if before is None:
        return None
    return before, after[0]


def _orient_pair(field: str, pair: tuple[float, float], fraction: float):
    a, b = pair
    abs_floor = 2.0 if field == "calories" else 0.20

    def fits(per100: float, serving: float) -> bool:
        expected = per100 * fraction
        tolerance = max(abs_floor, 0.05 * max(abs(expected), 1.0))
        return abs(serving - expected) <= tolerance

    options: list[tuple[float, float]] = []
    if fits(a, b):
        options.append((a, b))
    if fits(b, a):
        options.append((b, a))

    if not options:
        return None
    unique = {(round(per100, 8), round(serving, 8)) for per100, serving in options}
    if len(unique) == 1:
        return options[0]
    # Equal/zero cells can legitimately fit in both orientations; the observed
    # per-100 value is identical either way, so no numeric choice is being made.
    if a == b:
        return a, b
    return None


def project_explicit_serving_column(
    text: str,
    *,
    extraction_confidence: float = 1.0,
) -> ExplicitServingColumnProjection | None:
    """Project only an explicitly labelled, internally scaled serving column.

    Safety contract:
    - exactly two standalone weight/volume headers occur before the first core row;
    - the first is 100 g/ml and the second is a smaller serving in the same unit;
    - all four core rows contain two observed values in that same OCR reading;
    - every serving value independently matches the printed serving fraction;
    - at least two rows carry non-trivial scaling evidence; and
    - the existing Mercadona parser must accept the projected per-100 tuple,
      including its ordinary energy/macro coherence checks.

    If any part is ambiguous, return ``None`` and preserve REVIEW.
    """

    lines = _clean_lines(text)
    if len(lines) < 10:
        return None

    labels = {field: _label_indices(lines, field) for field in CORE_FIELDS}
    if any(len(indices) != 1 for indices in labels.values()):
        return None
    first_label = min(indices[0] for indices in labels.values())

    headers = []
    for i, line in enumerate(lines[:first_label]):
        parsed = _header(line)
        if parsed is not None:
            headers.append((i, *parsed))
    if len(headers) != 2:
        return None
    (first_i, first_amount, first_unit), (second_i, serving_amount, serving_unit) = headers
    if first_amount != 100.0 or first_unit != serving_unit:
        return None
    if not (0.0 < serving_amount < 100.0):
        return None
    if second_i - first_i > 2:
        return None

    fraction = serving_amount / 100.0
    per100: dict[str, float] = {}
    observed_pairs: dict[str, tuple[float, float]] = {}
    informative = 0

    for field in CORE_FIELDS:
        unit = "kcal" if field == "calories" else "g"
        pair = _row_pair(lines, labels[field][0], unit)
        if pair is None:
            return None
        oriented = _orient_pair(field, pair, fraction)
        if oriented is None:
            return None
        per100_value, serving_value = oriented
        per100[field] = per100_value
        observed_pairs[field] = (per100_value, serving_value)
        if per100_value >= (5.0 if field == "calories" else 1.0):
            informative += 1

    if informative < 2:
        return None

    basis_text = f"100 {serving_unit}"
    projected = (
        f"Información nutricional por {basis_text}\n"
        f"Valor energético {per100['calories']:g} kcal\n"
        f"Grasas {per100['fat_g']:g} g\n"
        f"Hidratos de carbono {per100['carbohydrate_g']:g} g\n"
        f"Proteínas {per100['protein_g']:g} g\n"
    )
    parsed = read_nutrition_label(projected, extraction_confidence=extraction_confidence)
    if parsed.status != "DECLARED" or parsed.nutrition is None:
        return None
    if any(abs(float(parsed.nutrition[field]) - per100[field]) > 1e-9 for field in CORE_FIELDS):
        return None

    original = "\n".join(lines)
    marker = f"EXPLICIT_SERVING_COLUMN_PROJECTION serving={serving_amount:g}{serving_unit}"
    audited_text = f"{original}\n\n[{marker}]\n{parsed.normalized_text}"
    parsed = replace(
        parsed,
        reasons=tuple(dict.fromkeys((*parsed.reasons, marker))),
        normalized_text=audited_text,
    )
    return ExplicitServingColumnProjection(
        result=parsed,
        serving_amount=serving_amount,
        serving_unit=serving_unit,
        observed_pairs=observed_pairs,
    )
