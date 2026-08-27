from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

READER_VERSION = "1.4.0"


@dataclass(frozen=True)
class LabelReadResult:
    status: str
    basis: str | None
    nutrition: dict[str, float] | None
    confidence: float
    reasons: tuple[str, ...]
    normalized_text: str

    @property
    def declared_usable(self) -> bool:
        return self.status == "DECLARED" and self.nutrition is not None


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    text = text.replace(",", ".")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _nutrition_block(text: str) -> str:
    """Restrict parsing to the declared nutrition section when it is visible.

    Better OCR engines read the whole package, including ingredients. Searching
    the entire package for words such as 'grasa' can therefore bind a macro to
    an ingredient percentage before the nutrition table. Once a nutrition
    heading is present, only that section is eligible for canonical parsing.
    """
    folded = _fold(text)
    starts = []
    for pattern in (r"informacion nutricional", r"declaracion nutricional", r"valores nutricionales"):
        m = re.search(pattern, folded, flags=re.I)
        if m:
            starts.append(m.start())
    if not starts:
        return text
    start = min(starts)
    tail = text[start:]
    folded_tail = _fold(tail)
    # Common packaging sections after the table. Stop conservatively only when
    # the marker is well after the heading so rows are not clipped accidentally.
    ends = []
    for pattern in (
        r"\npreparacion\b", r"\nconservacion\b", r"\ncondiciones de conservacion\b",
        r"\nmodo de empleo\b", r"\nfabricado por\b", r"\nconsumir preferentemente\b",
    ):
        m = re.search(pattern, folded_tail, flags=re.I)
        if m and m.start() > 80:
            ends.append(m.start())
    return tail[:min(ends)] if ends else tail


def _repair_ocr_number(raw: str) -> float | None:
    """Repair only a narrow, observed OCR error: terminal `g` read as `9`."""
    try:
        value = float(raw)
    except ValueError:
        return None
    if "." not in raw and value > 100 and raw.endswith("9") and len(raw) >= 3:
        try:
            repaired = float(raw[:-1])
        except ValueError:
            repaired = value
        if 0 <= repaired <= 100:
            return repaired
    return value


def _strip_ocr_unit_parentheses(text: str) -> str:
    """Remove observed one-character OCR renderings of a parenthesized g unit.

    PP-OCR/Tesseract often read `(g)` as `(9)`, `(0)`, `(o)`, `(q)` or `(y)`.
    Those tokens are metadata, not nutrient values, and otherwise become the
    first digit after a row label.
    """
    return re.sub(r"[\(\[]\s*(?:g|q|9|o|0|y)\s*[\)\]]", " ", text, flags=re.I)


def _number_after(label_patterns: tuple[str, ...], text: str) -> float | None:
    folded = _strip_ocr_unit_parentheses(_fold(text))
    # Stop rather than borrowing a number from the next nutrition/packaging row
    # when the value cell itself was not read. This is deliberately conservative.
    blockers = (
        "de las cuales", "de los cuales", "saturad", "azucar", "sal",
        "preparacion", "conservacion", "consumir", "fabricado", "envasado",
        "hidratos", "proteinas", "grasas", "valor energetico", "energia",
    )
    for label in label_patterns:
        for label_match in re.finditer(label, folded, flags=re.I):
            tail = folded[label_match.end():label_match.end() + 90]
            number = re.search(r"([<>]?)\s*(\d{1,4}(?:\.\d{1,2})?)\s*(?:g\b|gramos?\b)?", tail)
            if not number:
                continue
            prefix = tail[:number.start()].strip()
            if any(marker in prefix for marker in blockers):
                continue
            # An upper/lower bound is useful evidence but is not an exact macro.
            # Keep the whole row in REVIEW instead of silently promoting 0.5.
            if number.group(1) in ("<", ">"):
                return None
            value = _repair_ocr_number(number.group(2))
            if value is not None:
                return value
    return None


def _interleaved_carbohydrate(text: str) -> float | None:
    """Handle a recurrent OCR reading order without guessing across rows.

    In narrow Mercadona tables the visual text `Hidratos de Carbono | 2.0 g`
    is often linearised as `Hidratos de / 2.0 g / Carbono`. The value is safe
    only when it is literally bracketed by the two halves of that same label.
    """
    folded = _strip_ocr_unit_parentheses(_fold(text))
    m = re.search(
        r"hidratos?\s+de\s+([<>]?)\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:g|9|y|q)?\s+carbono\b",
        folded,
        flags=re.I,
    )
    if not m or m.group(1) in ("<", ">"):
        return None
    return _repair_ocr_number(m.group(2))


def _energy_kcal(text: str) -> float | None:
    folded = _fold(text)
    # Some labels put the units in the heading and the values on the next line:
    # `Valor energético (kJ/kcal) 442/106`. In that exact layout the second
    # declared value is unambiguously kcal.
    header_pair = re.search(
        r"(?:valor energetico|energia)[\s\S]{0,70}?k\s*j\s*/\s*kcal"
        r"[\s\S]{0,35}?(\d{2,4}(?:\.\d{1,2})?)\s*[/\\|]\s*(\d{1,4}(?:\.\d{1,2})?)",
        folded,
        flags=re.I,
    )
    if header_pair:
        return float(header_pair.group(2))

    patterns = [
        r"valor energetico[\s\S]{0,90}?(\d{2,4}(?:\.\d{1,2})?)\s*kcal",
        r"energia[\s\S]{0,90}?(\d{2,4}(?:\.\d{1,2})?)\s*kcal",
        r"(\d{2,4}(?:\.\d{1,2})?)\s*kcal",
    ]
    for pattern in patterns:
        m = re.search(pattern, folded, flags=re.I)
        if m:
            return float(m.group(1))
    return None


def _basis(text: str) -> str | None:
    folded = _fold(text)
    # q/y/9/yg are observed OCR substitutions around the printed `g` glyph.
    if re.search(r"(?:por|cada|valores? medios? por)?\s*100\s*(?:g|9|q|yg|y)\b", folded):
        return "100_g"
    if re.search(r"(?:por|cada|valores? medios? por)?\s*100\s*m(?:l|i|1)\b", folded):
        return "100_ml"
    return None


def _basis_heading_count(text: str) -> int:
    """Count explicit per-100 column headings, not incidental '100 g' text.

    Two explicit `por 100 g/ml` headings usually mean parallel nutrition
    columns (e.g. net weight vs drained weight). The v1 parser is row-oriented,
    so it must review rather than silently mix those columns.
    """
    folded = _fold(text)
    return len(re.findall(
        r"\bpor\s+100\s*(?:g\b|9\b|q\b|yg\b|y\b|m(?:l|i|1)\b)",
        folded,
        flags=re.I,
    ))


def _plausible(n: dict[str, float]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for key in ("fat_g", "carbohydrate_g", "protein_g"):
        value = n[key]
        if value < 0 or value > 100:
            reasons.append(f"IMPOSSIBLE_{key.upper()}")
    if n["calories"] < 0 or n["calories"] > 1000:
        reasons.append("IMPOSSIBLE_CALORIES")

    estimated = 9 * n["fat_g"] + 4 * n["carbohydrate_g"] + 4 * n["protein_g"]
    # OCR false positives frequently combine individually plausible values from
    # adjacent rows/columns. For an automatically usable OCR record we prefer
    # precision over recall: allow ordinary label rounding, but route wider
    # discrepancies to REVIEW. Products whose energy includes fibre/polyols/
    # organic acids may therefore require review rather than unsafe inference.
    tolerance = max(8.0, n["calories"] * 0.10)
    if abs(estimated - n["calories"]) > tolerance:
        reasons.append(f"ENERGY_MACRO_MISMATCH:{estimated:.1f}")
    return not reasons, reasons


def read_nutrition_label(text: str, *, extraction_confidence: float = 1.0) -> LabelReadResult:
    normalized = normalize_text(text)
    reasons: list[str] = []
    folded_all = _fold(normalized)

    nutrition_markers = sum(1 for marker in (
        "valor energetico", "energia", "grasas", "lipidos", "hidratos", "proteinas", "sal"
    ) if marker in folded_all)
    if nutrition_markers < 3:
        return LabelReadResult("NOT_NUTRITION_LABEL", None, None, 0.0,
                               ("INSUFFICIENT_NUTRITION_MARKERS",), normalized)

    block = _nutrition_block(normalized)
    if _basis_heading_count(block) > 1:
        return LabelReadResult(
            "REVIEW", _basis(block), None, min(extraction_confidence, .65),
            ("MULTIPLE_NUTRITION_COLUMNS",), normalized,
        )

    basis = _basis(block)
    if basis is None:
        reasons.append("MISSING_100G_100ML_BASIS")

    calories = _energy_kcal(block)
    fat = _number_after((r"grasas?", r"lipidos?", r"grasa total"), block)
    carbs = _interleaved_carbohydrate(block)
    if carbs is None:
        carbs = _number_after((r"hidratos? de carbono", r"carbohidratos?"), block)
    protein = _number_after((r"proteinas?",), block)

    values = {"calories": calories, "fat_g": fat, "carbohydrate_g": carbs, "protein_g": protein}
    missing = [k for k, v in values.items() if v is None]
    if missing:
        reasons.append("MISSING_CORE:" + ",".join(missing))
        partial = {k: float(v) for k, v in values.items() if v is not None}
        return LabelReadResult("REVIEW", basis, partial or None, min(extraction_confidence, .60), tuple(reasons), normalized)

    nutrition = {k: float(v) for k, v in values.items()}
    plausible, plausibility_reasons = _plausible(nutrition)
    reasons.extend(plausibility_reasons)
    if not plausible:
        return LabelReadResult("REVIEW", basis, nutrition, min(extraction_confidence, .65), tuple(reasons), normalized)

    if extraction_confidence < .85:
        reasons.append("LOW_EXTRACTION_CONFIDENCE")
        return LabelReadResult("REVIEW", basis, nutrition, extraction_confidence, tuple(reasons), normalized)

    if basis is None:
        return LabelReadResult("REVIEW", None, nutrition, min(extraction_confidence, .75), tuple(reasons), normalized)

    return LabelReadResult("DECLARED", basis, nutrition, min(1.0, extraction_confidence), tuple(reasons), normalized)
