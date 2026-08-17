from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from nutrition_label_reader import LabelReadResult, read_nutrition_label

ENSEMBLE_VERSION = "1.0.0"
FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")


@dataclass(frozen=True)
class ParsedOCRReading:
    strategy: str
    result: LabelReadResult


@dataclass(frozen=True)
class EnsembleField:
    name: str
    value: float
    strategies: tuple[str, ...]
    confidences: tuple[float, ...]
    corroborated: bool


@dataclass(frozen=True)
class OCREnsembleResult:
    status: str
    basis: str | None
    nutrition: dict[str, float] | None
    confidence: float
    fields: tuple[EnsembleField, ...]
    corroborated_fields: int
    reasons: tuple[str, ...]

    @property
    def declared_usable(self) -> bool:
        return self.status == "DECLARED" and self.nutrition is not None


def _close(field: str, a: float, b: float) -> bool:
    if field == "calories":
        tolerance = max(5.0, 0.04 * max(abs(a), abs(b), 1.0))
    else:
        tolerance = max(0.6, 0.10 * max(abs(a), abs(b), 1.0))
    return abs(a - b) <= tolerance


def _field_candidates(readings: Iterable[ParsedOCRReading], field: str):
    out = []
    for reading in readings:
        result = reading.result
        if result.status == "NOT_NUTRITION_LABEL" or result.confidence < .70 or not result.nutrition:
            continue
        value = result.nutrition.get(field)
        if isinstance(value, (int, float)):
            out.append((float(value), result.confidence, reading.strategy))
    return out


def _choose_field(field: str, candidates):
    if not candidates:
        return None, None
    # Build agreement groups around each observed value. We never average
    # materially conflicting OCR values.
    groups = []
    for anchor in candidates:
        group = [x for x in candidates if _close(field, anchor[0], x[0])]
        groups.append(group)
    groups.sort(key=lambda g: (len(g), sum(x[1] for x in g)), reverse=True)
    best = groups[0]
    # If two equally supported groups disagree materially, review rather than
    # choosing whichever happened to appear first.
    if len(groups) > 1:
        second = groups[1]
        if len(second) == len(best) and not _close(field, best[0][0], second[0][0]):
            return None, f"OCR_FIELD_CONFLICT:{field}"
    selected = max(best, key=lambda x: x[1])
    strategies = tuple(sorted({x[2] for x in best}))
    confidences = tuple(x[1] for x in best)
    return EnsembleField(field, selected[0], strategies, confidences, len(strategies) >= 2), None


def fuse_ocr_readings(readings: Iterable[ParsedOCRReading]) -> OCREnsembleResult:
    readings = tuple(readings)
    reasons: list[str] = []

    bases = [(x.result.basis, x.result.confidence, x.strategy) for x in readings
             if x.result.basis and x.result.confidence >= .70]
    unique_bases = {x[0] for x in bases}
    if len(unique_bases) > 1:
        return OCREnsembleResult("REVIEW", None, None, 0.0, tuple(), 0,
                                 ("OCR_BASIS_CONFLICT",))
    basis = next(iter(unique_bases), None)

    fields: list[EnsembleField] = []
    for field in FIELDS:
        chosen, error = _choose_field(field, _field_candidates(readings, field))
        if error:
            reasons.append(error)
        if chosen:
            fields.append(chosen)

    nutrition = {x.name: x.value for x in fields}
    missing = [x for x in FIELDS if x not in nutrition]
    if missing:
        reasons.append("MISSING_CORE:" + ",".join(missing))
        return OCREnsembleResult("REVIEW", basis, nutrition or None, 0.0,
                                 tuple(fields), sum(x.corroborated for x in fields), tuple(reasons))
    if basis is None:
        reasons.append("MISSING_100G_100ML_BASIS")

    corroborated = sum(x.corroborated for x in fields)
    complete_sources = [x.result for x in readings
                        if x.result.nutrition and all(k in x.result.nutrition for k in FIELDS)]
    best_complete = max((x.confidence for x in complete_sources), default=0.0)

    # Two independently segmented OCR passes confirming >=2 core fields can
    # promote an almost-high-confidence complete reading. This is deliberately
    # narrow: field-only synthesis without a nearly complete source remains
    # review, even if the final arithmetic happens to be plausible.
    if best_complete >= .80 and corroborated >= 2:
        ensemble_confidence = min(.99, best_complete + .02)
    else:
        ensemble_confidence = min((max(x.confidences) for x in fields), default=0.0)
        ensemble_confidence = min(ensemble_confidence, .84)

    synthetic_basis = "100 g" if basis == "100_g" else "100 ml" if basis == "100_ml" else ""
    synthetic = (
        f"Información nutricional por {synthetic_basis}\n"
        f"Valor energético {nutrition['calories']} kcal\n"
        f"Grasas {nutrition['fat_g']} g\n"
        f"Hidratos de carbono {nutrition['carbohydrate_g']} g\n"
        f"Proteínas {nutrition['protein_g']} g\n"
    )
    validated = read_nutrition_label(synthetic, extraction_confidence=ensemble_confidence)
    reasons.extend(validated.reasons)
    if validated.status == "DECLARED" and basis is not None and not any(r.startswith("OCR_FIELD_CONFLICT") for r in reasons):
        return OCREnsembleResult("DECLARED", basis, nutrition, ensemble_confidence,
                                 tuple(fields), corroborated, tuple(dict.fromkeys(reasons)))
    return OCREnsembleResult("REVIEW", basis, nutrition, ensemble_confidence,
                             tuple(fields), corroborated, tuple(dict.fromkeys(reasons)))
