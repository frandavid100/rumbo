from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

MULTICOLUMN_READER_VERSION = "1.0.0"


@dataclass(frozen=True)
class NutritionColumn:
    key: str
    label: str
    basis: str
    nutrition: dict[str, float]


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _num(token: str) -> float | None:
    token = token.strip().replace(",", ".").replace("<", "")
    m = re.search(r"\d+(?:\.\d+)?", token)
    return float(m.group(0)) if m else None


def read_two_column_nutrition(text: str) -> tuple[NutritionColumn, NutritionColumn] | None:
    """Parse a common two-column EU nutrition table without selecting a winner.

    This is deliberately narrow. It recognizes tables where the headers explicitly
    distinguish `peso neto` and `peso escurrido`. Both columns are returned and
    callers must choose through an explicit consumption policy; this function never
    silently mixes or prefers one column.
    """
    folded = _fold(text)
    if "por 100 g" not in folded or "peso neto" not in folded or "peso escurrido" not in folded:
        return None

    def pair(label: str, next_label: str | None = None) -> tuple[float, float] | None:
        start = folded.find(label)
        if start < 0:
            return None
        end = len(text)
        if next_label:
            candidate = folded.find(next_label, start + len(label))
            if candidate >= 0:
                end = candidate
        chunk = text[start:end]
        nums = re.findall(r"<?\s*\d+(?:[\.,]\d+)?\s*g?", chunk, flags=re.I)
        values = [_num(x) for x in nums]
        values = [x for x in values if x is not None]
        return (values[0], values[1]) if len(values) >= 2 else None

    energy_matches = re.search(
        r"valor\s+energetico[\s\S]{0,90}?(\d{2,4})\s*kcal[\s\S]{0,50}?(\d{2,4})\s*kcal",
        folded,
        flags=re.I,
    )
    fat = pair("grasas", "de las cuales saturadas")
    carbs = pair("hidratos de carbono", "de los cuales azucares")
    protein = pair("proteinas", "sal")
    if not energy_matches or fat is None or carbs is None or protein is None:
        return None

    net = NutritionColumn(
        key="NET_WEIGHT",
        label="por 100 g de peso neto",
        basis="100_g",
        nutrition={
            "calories": float(energy_matches.group(1)),
            "fat_g": fat[0],
            "carbohydrate_g": carbs[0],
            "protein_g": protein[0],
        },
    )
    drained = NutritionColumn(
        key="DRAINED_WEIGHT",
        label="por 100 g de peso escurrido",
        basis="100_g",
        nutrition={
            "calories": float(energy_matches.group(2)),
            "fat_g": fat[1],
            "carbohydrate_g": carbs[1],
            "protein_g": protein[1],
        },
    )
    return net, drained


def select_column(columns: tuple[NutritionColumn, ...], *, policy: str | None) -> NutritionColumn | None:
    """Select only when the caller states an explicit consumption policy."""
    if policy is None:
        return None
    wanted = {
        "NET_WEIGHT": "NET_WEIGHT",
        "DRAINED_WEIGHT": "DRAINED_WEIGHT",
    }.get(policy)
    if wanted is None:
        raise ValueError(f"Unknown nutrition column policy: {policy}")
    return next((column for column in columns if column.key == wanted), None)
