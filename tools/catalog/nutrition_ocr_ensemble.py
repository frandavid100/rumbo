from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from nutrition_label_reader import LabelReadResult, read_nutrition_label

ENSEMBLE_VERSION = "1.2.0"
FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")


@dataclass(frozen=True)
class ParsedOCRReading:
    strategy: str
    result: LabelReadResult
    extraction_confidence: float | None = None
    engine_family: str | None = None

    @property
    def confidence(self) -> float:
        return self.result.confidence if self.extraction_confidence is None else self.extraction_confidence

    @property
    def family(self) -> str:
        if self.engine_family:
            return self.engine_family.strip().lower()
        strategy = self.strategy.strip().lower()
        if "tesseract" in strategy or strategy.startswith("psm"):
            return "tesseract"
        if "paddle" in strategy or "pp-ocr" in strategy:
            return "paddleocr"
        if "easyocr" in strategy:
            return "easyocr"
        return strategy.split(":", 1)[0] or "unknown"


@dataclass(frozen=True)
class EnsembleField:
    name: str
    value: float
    strategies: tuple[str, ...]
    confidences: tuple[float, ...]
    engine_families: tuple[str, ...]
    corroborated: bool


@dataclass(frozen=True)
class OCREnsembleResult:
    status: str
    basis: str | None
    nutrition: dict[str, float] | None
    confidence: float
    fields: tuple[EnsembleField, ...]
    corroborated_fields: int
    independent_engine_families: int
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
        confidence = reading.confidence
        if result.status == "NOT_NUTRITION_LABEL" or confidence < .70 or not result.nutrition:
            continue
        value = result.nutrition.get(field)
        if isinstance(value, (int, float)):
            out.append((float(value), confidence, reading.strategy, reading.family))
    return out


def _choose_field(field: str, candidates):
    if not candidates:
        return None, None

    # OCR layouts/crops from the same engine are correlated observations, not
    # independent evidence. First reduce each engine family to one internally
    # consistent representative. If a family contradicts itself, the field is
    # unsafe and must remain review-only.
    by_family: dict[str, list[tuple[float, float, str, str]]] = {}
    for candidate in candidates:
        by_family.setdefault(candidate[3], []).append(candidate)

    representatives = []
    for family, family_candidates in sorted(by_family.items()):
        selected = max(family_candidates, key=lambda x: x[1])
        if any(not _close(field, selected[0], other[0]) for other in family_candidates):
            return None, f"OCR_SAME_ENGINE_CONFLICT:{field}:{family}"
        representatives.append(selected)

    selected = max(representatives, key=lambda x: x[1])
    if len(representatives) >= 2 and any(
        not _close(field, selected[0], other[0]) for other in representatives
    ):
        return None, f"OCR_FIELD_CONFLICT:{field}"

    agreeing = [x for x in candidates if _close(field, selected[0], x[0])]
    strategies = tuple(sorted({x[2] for x in agreeing}))
    confidences = tuple(x[1] for x in agreeing)
    families = tuple(sorted({x[3] for x in representatives}))
    return EnsembleField(
        field, selected[0], strategies, confidences, families, len(families) >= 2
    ), None


def fuse_ocr_readings(readings: Iterable[ParsedOCRReading]) -> OCREnsembleResult:
    readings = tuple(readings)
    reasons: list[str] = []
    eligible_readings = tuple(
        x for x in readings
        if x.result.status != "NOT_NUTRITION_LABEL" and x.confidence >= .70 and x.result.nutrition
    )
    independent_families = len({x.family for x in eligible_readings})

    bases = [(x.result.basis, x.confidence, x.strategy, x.family) for x in readings
             if x.result.basis and x.confidence >= .70]
    unique_bases = {x[0] for x in bases}
    if len(unique_bases) > 1:
        return OCREnsembleResult(
            "REVIEW", None, None, 0.0, tuple(), 0, independent_families,
            ("OCR_BASIS_CONFLICT",),
        )
    basis = next(iter(unique_bases), None)
    basis_families = {x[3] for x in bases}

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
        return OCREnsembleResult(
            "REVIEW", basis, nutrition or None, 0.0,
            tuple(fields), sum(x.corroborated for x in fields), independent_families,
            tuple(dict.fromkeys(reasons)),
        )
    if basis is None:
        reasons.append("MISSING_100G_100ML_BASIS")

    corroborated = sum(x.corroborated for x in fields)
    if independent_families < 2:
        reasons.append("INSUFFICIENT_INDEPENDENT_OCR_ENGINES")
    if basis is not None and len(basis_families) < 2:
        reasons.append("UNCORROBORATED_BASIS")
    if corroborated < len(FIELDS):
        reasons.append("UNCORROBORATED_CORE_FIELDS")

    complete_sources = [x for x in readings
                        if x.result.nutrition and all(k in x.result.nutrition for k in FIELDS)]
    best_complete = max((x.confidence for x in complete_sources), default=0.0)
    if independent_families >= 2 and corroborated == len(FIELDS):
        ensemble_confidence = min(.99, max(.85, best_complete) + .02)
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
    hard_conflict = any(
        r.startswith("OCR_FIELD_CONFLICT") or r.startswith("OCR_SAME_ENGINE_CONFLICT")
        for r in reasons
    )
    safely_corroborated = (
        independent_families >= 2
        and len(basis_families) >= 2
        and corroborated == len(FIELDS)
    )
    if validated.status == "DECLARED" and basis is not None and safely_corroborated and not hard_conflict:
        return OCREnsembleResult(
            "DECLARED", basis, nutrition, ensemble_confidence,
            tuple(fields), corroborated, independent_families, tuple(dict.fromkeys(reasons)),
        )
    return OCREnsembleResult(
        "REVIEW", basis, nutrition, ensemble_confidence,
        tuple(fields), corroborated, independent_families, tuple(dict.fromkeys(reasons)),
    )
