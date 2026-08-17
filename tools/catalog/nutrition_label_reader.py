from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

READER_VERSION = "1.0.0"


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


def _number_after(label_patterns: tuple[str, ...], text: str) -> float | None:
    folded = _fold(text)
    for label in label_patterns:
        # Allows OCR punctuation/noise between label and number while avoiding
        # values from a later row.
        pattern = rf"(?:{label})[^\n\r\d]{{0,35}}(\d{{1,4}}(?:\.\d{{1,2}})?)\s*(?:g\b|gramos?\b)?"
        m = re.search(pattern, folded, flags=re.I)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
    return None


def _energy_kcal(text: str) -> float | None:
    folded = _fold(text)
    # Prefer kcal explicitly. EU labels frequently show kJ / kcal together.
    patterns = [
        r"valor energetico[^\n\r]{0,60}?(\d{2,4}(?:\.\d{1,2})?)\s*kcal",
        r"energia[^\n\r]{0,60}?(\d{2,4}(?:\.\d{1,2})?)\s*kcal",
        r"(\d{2,4}(?:\.\d{1,2})?)\s*kcal",
    ]
    for pattern in patterns:
        m = re.search(pattern, folded, flags=re.I)
        if m:
            return float(m.group(1))
    return None


def _basis(text: str) -> str | None:
    folded = _fold(text)
    if re.search(r"(?:por|cada|valores? medios? por)?\s*100\s*g\b", folded):
        return "100_g"
    if re.search(r"(?:por|cada|valores? medios? por)?\s*100\s*ml\b", folded):
        return "100_ml"
    return None


def _plausible(n: dict[str, float]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for key in ("fat_g", "carbohydrate_g", "protein_g"):
        value = n[key]
        if value < 0 or value > 100:
            reasons.append(f"IMPOSSIBLE_{key.upper()}")
    if n["calories"] < 0 or n["calories"] > 1000:
        reasons.append("IMPOSSIBLE_CALORIES")

    estimated = 9 * n["fat_g"] + 4 * n["carbohydrate_g"] + 4 * n["protein_g"]
    # Labels may include fibre, polyols, organic acids or alcohol; use a broad
    # but blocking tolerance only for material inconsistencies/OCR errors.
    tolerance = max(35.0, n["calories"] * 0.25)
    if abs(estimated - n["calories"]) > tolerance:
        reasons.append(f"ENERGY_MACRO_MISMATCH:{estimated:.1f}")
    return not reasons, reasons


def read_nutrition_label(text: str, *, extraction_confidence: float = 1.0) -> LabelReadResult:
    normalized = normalize_text(text)
    reasons: list[str] = []
    folded = _fold(normalized)

    nutrition_markers = sum(1 for marker in (
        "valor energetico", "energia", "grasas", "hidratos", "proteinas", "sal"
    ) if marker in folded)
    if nutrition_markers < 3:
        return LabelReadResult("NOT_NUTRITION_LABEL", None, None, 0.0,
                               ("INSUFFICIENT_NUTRITION_MARKERS",), normalized)

    basis = _basis(normalized)
    if basis is None:
        reasons.append("MISSING_100G_100ML_BASIS")

    calories = _energy_kcal(normalized)
    fat = _number_after((r"grasas?", r"grasa total"), normalized)
    carbs = _number_after((r"hidratos? de carbono", r"carbohidratos?"), normalized)
    protein = _number_after((r"proteinas?",), normalized)

    values = {
        "calories": calories,
        "fat_g": fat,
        "carbohydrate_g": carbs,
        "protein_g": protein,
    }
    missing = [k for k, v in values.items() if v is None]
    if missing:
        reasons.append("MISSING_CORE:" + ",".join(missing))
        return LabelReadResult("REVIEW", basis, None, min(extraction_confidence, .60), tuple(reasons), normalized)

    nutrition = {k: float(v) for k, v in values.items()}
    plausible, plausibility_reasons = _plausible(nutrition)
    reasons.extend(plausibility_reasons)
    if not plausible:
        return LabelReadResult("REVIEW", basis, nutrition, min(extraction_confidence, .65), tuple(reasons), normalized)

    # A vision engine confidence below 0.85 never becomes DECLARED automatically.
    if extraction_confidence < .85:
        reasons.append("LOW_EXTRACTION_CONFIDENCE")
        return LabelReadResult("REVIEW", basis, nutrition, extraction_confidence, tuple(reasons), normalized)

    if basis is None:
        return LabelReadResult("REVIEW", None, nutrition, min(extraction_confidence, .75), tuple(reasons), normalized)

    return LabelReadResult("DECLARED", basis, nutrition, min(1.0, extraction_confidence), tuple(reasons), normalized)
