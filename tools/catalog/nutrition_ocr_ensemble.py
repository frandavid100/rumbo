from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import re
import unicodedata
from typing import Iterable

from nutrition_label_reader import LabelReadResult, read_nutrition_label

ENSEMBLE_VERSION = "1.3.8"
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


def _fold_ocr_text(text: str) -> str:
    folded = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(char for char in folded if unicodedata.category(char) != "Mn")


def _incoherent_explicit_energy_pair(reading: ParsedOCRReading) -> bool:
    """Veto calories when a credible OCR read exposes incompatible kJ/kcal.

    This is deliberately observation-wide and fail-closed. Other OCR families
    are not allowed to outvote an explicit physical contradiction by repeating
    the same misread kcal glyph. The pair must be unique in that OCR text;
    multi-column/multi-energy layouts remain governed by the existing ambiguity
    gates instead of being paired heuristically. No value is inferred or fixed.
    """
    if reading.result.status == "NOT_NUTRITION_LABEL" or reading.confidence < .70:
        return False
    text = _fold_ocr_text(reading.result.normalized_text)
    if not text:
        return False
    kj_values = re.findall(
        r"(?<![\d.])(\d{1,5}(?:\.\d{1,2})?)\s*k\s*j\b",
        text,
        flags=re.I,
    )
    kcal_values = re.findall(
        r"(?<![\d.])(\d{1,4}(?:\.\d{1,2})?)\s*kcal\b",
        text,
        flags=re.I,
    )
    if len(kj_values) != 1 or len(kcal_values) != 1:
        return False
    kj = float(kj_values[0])
    kcal = float(kcal_values[0])
    expected_kj = kcal * 4.184
    tolerance_kj = max(2.0, expected_kj * 0.08)
    return abs(kj - expected_kj) > tolerance_kj


_BOUNDED_ROW_LABELS = {
    "calories": (r"valor\s+energetico", r"energia"),
    "fat_g": (r"grasas?", r"lipidos?", r"grasa\s+total"),
    "carbohydrate_g": (r"hidratos?\s+de\s+carbono", r"carbohidratos?"),
    "protein_g": (r"proteinas?", r"prote_nas?"),
}


def _bounded_core_fields(reading: ParsedOCRReading) -> set[str]:
    """Return core fields whose OCR text explicitly declares a numeric bound.

    A printed `<1.0 g` is not an exact `1.0 g`. One Mercadona back label exposed
    a subtle failure mode where one OCR family preserved the inequality while
    another lost the `<` glyph and a reversed-row rescue then surfaced 1.0 as an
    exact candidate. Because the project prefers precision over recall, any
    credible family that sees an inequality anchored directly to a core row keeps
    that field non-exact for the whole fresh ensemble observation.

    Matching is deliberately narrow: the inequality must be on the same row,
    the immediately following value row, or the immediately preceding reversed
    value row. A Mercadona label has also been observed with OCR layout wrapping
    `Hidratos de` and `Carbono` around the bounded value itself; that exact
    split-label geometry is accepted too. Bounds on saturated fat, sugars, salt,
    ingredients, or distant prose therefore cannot veto a core macro.
    """
    if reading.result.status == "NOT_NUTRITION_LABEL" or reading.confidence < .70:
        return set()
    text = _fold_ocr_text(reading.result.normalized_text)
    if not text:
        return set()

    number = r"[<>]\s*\d{1,4}(?:[.,]\d{1,2})?"
    unit = r"(?:\s*(?:kcal|g|9|q|yg|y))?"
    bounded: set[str] = set()
    for field, labels in _BOUNDED_ROW_LABELS.items():
        label = "(?:" + "|".join(labels) + ")"
        same_row = rf"(?:^|\n)\s*[\[|]?\s*{label}\b[^\n]*?{number}{unit}(?=\s|$)"
        next_row = rf"(?:^|\n)\s*[\[|]?\s*{label}\b[^\n]*\n\s*{number}{unit}(?=\s|$)"
        reversed_row = rf"(?:^|\n)\s*{number}{unit}\s*\n\s*[\[|]?\s*{label}\b"
        split_carbohydrate_label = None
        if field == "carbohydrate_g":
            # Real first-party OCR sample (Mercadona product 25184):
            #   Hidratos de
            #   <0.5 g
            #   0               # occasional OCR layout artefact
            #   Carbono
            # This is still an explicitly bounded carbohydrate row, not an exact
            # 0.5 g observation. Keep the geometry intentionally narrow so a bound
            # on the following sugars row cannot be misattributed to carbohydrates.
            split_carbohydrate_label = (
                rf"(?:^|\n)\s*[\[|]?\s*hidratos?\s+de\s*\n\s*"
                rf"{number}{unit}(?=\s|$)\s*(?:\n\s*[0o]\s*)?\n\s*carbono\b"
            )
        if (
            re.search(same_row, text, flags=re.I)
            or re.search(next_row, text, flags=re.I)
            or re.search(reversed_row, text, flags=re.I)
            or (
                split_carbohydrate_label is not None
                and re.search(split_carbohydrate_label, text, flags=re.I)
            )
        ):
            bounded.add(field)
    return bounded


def _anchored_single_digit_kcal(text: str) -> float | None:
    """Recover an exact one-digit kcal cell only from an unambiguous energy row.

    The generic label parser deliberately requires at least two kcal digits to
    avoid package-text false positives. Real Mercadona labels can legitimately
    declare e.g. `3 kcal / 100 ml`. At ensemble level we can recover that value
    more safely because it still needs independent OCR-family corroboration.

    The rescue is intentionally narrow: the value must occur after an explicit
    `Valor energético`/`Energía` anchor and before the next core nutrient row.
    If that energy span contains two one-digit kcal values (parallel columns such
    as the observed `2 kcal` / `6 kcal` labels), or different anchored readings
    in the same OCR text disagree, the observation remains ambiguous.
    """
    folded = _fold_ocr_text(text)
    if not folded:
        return None
    anchors = list(re.finditer(r"(?:valor\s+energetico|energia)\b", folded, flags=re.I))
    if not anchors:
        return None

    observed: list[float] = []
    next_core = re.compile(
        r"(?:^|\n)\s*[\[|]?\s*(?:grasas?|lipidos?|grasa\s+total|"
        r"hidratos?|carbohidratos?|proteinas?|prote_nas?|sal)\b",
        flags=re.I,
    )
    single_kcal = re.compile(r"(?<![\d.])(\d)(?![\d.])\s*kcal\b", flags=re.I)
    for anchor in anchors:
        tail = folded[anchor.end():anchor.end() + 180]
        stop = next_core.search(tail)
        if stop:
            tail = tail[:stop.start()]
        tokens = single_kcal.findall(tail)
        if len(tokens) > 1:
            return None
        if len(tokens) == 1:
            observed.append(float(tokens[0]))

    if not observed or len(set(observed)) != 1:
        return None
    return observed[0]


def _field_candidates(readings: Iterable[ParsedOCRReading], field: str):
    out = []
    for reading in readings:
        result = reading.result
        confidence = reading.confidence
        if result.status == "NOT_NUTRITION_LABEL" or confidence < .70 or not result.nutrition:
            continue
        # A bound is useful evidence that the printed value is non-exact, but it
        # is never an exact numeric candidate. This also blocks a reversed-row
        # rescue from reintroducing the numeric part after the `<`/`>` glyph was
        # observed elsewhere in the same OCR text.
        if field in _bounded_core_fields(reading):
            continue
        value = result.nutrition.get(field)
        if field == "calories" and not isinstance(value, (int, float)):
            value = _anchored_single_digit_kcal(result.normalized_text)
        if isinstance(value, (int, float)):
            out.append((float(value), confidence, reading.strategy, reading.family))
    return out


def _family_representative(field: str, family_candidates):
    """Reduce correlated layouts to one value without letting one OCR outlier veto a majority.

    Multiple Tesseract PSM layouts are not independent evidence, but they are useful
    repeated observations from the same engine family. When a unique strict majority
    of those layouts agrees within the ordinary field tolerance, an isolated layout
    outlier may be discarded. A 1-vs-1 split, two equally large compatible clusters,
    or any other ambiguous family remains a hard same-engine conflict unless two
    other independent OCR families already agree on the field.
    """
    family_candidates = tuple(family_candidates)
    if not family_candidates:
        return None
    if len(family_candidates) == 1:
        return family_candidates[0]

    for size in range(len(family_candidates), 1, -1):
        compatible = []
        for group in combinations(family_candidates, size):
            if all(_close(field, a[0], b[0]) for a, b in combinations(group, 2)):
                compatible.append(group)
        if not compatible:
            continue
        # More than one maximum-size compatible cluster means the family itself
        # is ambiguous. Do not choose by confidence in that situation.
        if len(compatible) != 1:
            return None
        group = compatible[0]
        # A majority is required to overrule excluded layouts. With three PSM
        # modes, two matching reads can reject one outlier; two disagreeing reads
        # cannot choose a winner.
        if len(group) * 2 <= len(family_candidates):
            return None
        return max(group, key=lambda x: x[1])
    return None


def _exact_cross_family_consensus(candidates, representative_families):
    """Return an exact value only when every clean OCR family observed it.

    Near-value tolerance is useful inside one OCR family to cluster correlated
    layouts, but it must never manufacture cross-family agreement. In particular,
    a printed unit glyph can be misread as a trailing digit by more than one OCR
    engine (for example `3.2 g` -> `3.29`). If another clean family sees `3.2`,
    the observation is conflicting rather than approximately corroborated.
    """
    eligible = tuple(x for x in candidates if x[3] in representative_families)
    support = {}
    for candidate in eligible:
        support.setdefault(candidate[0], set()).add(candidate[3])
    if len(representative_families) < 2:
        return None
    winners = [
        value for value, families in support.items()
        if families == representative_families
    ]
    if len(winners) != 1:
        return None
    matching = [candidate for candidate in eligible if candidate[0] == winners[0]]
    return max(matching, key=lambda x: x[1])


def _choose_field(field: str, candidates):
    if not candidates:
        return None, None

    # OCR layouts/crops from the same engine are correlated observations, not
    # independent evidence. First reduce each engine family to one internally
    # consistent representative. An ambiguous family cannot manufacture evidence
    # and normally keeps the field in REVIEW. The one safe exception is when at
    # least two *other* independent families already agree: in that case the
    # ambiguous family is ignored instead of being allowed to veto corroborated
    # evidence from two clean families.
    by_family: dict[str, list[tuple[float, float, str, str]]] = {}
    for candidate in candidates:
        by_family.setdefault(candidate[3], []).append(candidate)

    representatives = []
    ambiguous_families = []
    for family, family_candidates in sorted(by_family.items()):
        selected = _family_representative(field, family_candidates)
        if selected is None:
            ambiguous_families.append(family)
            continue
        representatives.append(selected)

    if not representatives:
        family = ambiguous_families[0] if ambiguous_families else "unknown"
        return None, f"OCR_SAME_ENGINE_CONFLICT:{field}:{family}"

    selected = max(representatives, key=lambda x: x[1])
    if len(representatives) >= 2 and any(
        not _close(field, selected[0], other[0]) for other in representatives
    ):
        return None, f"OCR_FIELD_CONFLICT:{field}"

    representative_families = {x[3] for x in representatives}
    if ambiguous_families and len(representative_families) < 2:
        return None, f"OCR_SAME_ENGINE_CONFLICT:{field}:{','.join(sorted(ambiguous_families))}"

    exact_consensus = _exact_cross_family_consensus(candidates, representative_families)
    if exact_consensus is not None:
        selected = exact_consensus
    elif len(representatives) >= 2 and len({x[0] for x in representatives}) > 1:
        # All clean families must expose one identical numeric token somewhere in
        # their accepted layouts. A merely nearby value is not an exact label
        # declaration and must not become usable nutrition through tolerance.
        return None, f"OCR_FIELD_CONFLICT:{field}"

    agreeing = [
        x for x in candidates
        if x[3] in representative_families and x[0] == selected[0]
    ]
    strategies = tuple(sorted({x[2] for x in agreeing}))
    confidences = tuple(x[1] for x in agreeing)
    families = tuple(sorted({x[3] for x in agreeing}))
    note = None
    if ambiguous_families:
        note = f"IGNORED_AMBIGUOUS_ENGINE_FAMILY:{field}:{','.join(sorted(ambiguous_families))}"
    return EnsembleField(
        field, selected[0], strategies, confidences, families, len(families) >= 2
    ), note


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
    complete_basis_families = {
        x.family for x in readings
        if x.result.basis == basis
        and basis is not None
        and x.confidence >= .70
        and x.result.nutrition
        and all(field in x.result.nutrition for field in FIELDS)
    }

    bounded_families: dict[str, set[str]] = {field: set() for field in FIELDS}
    for reading in readings:
        for field in _bounded_core_fields(reading):
            bounded_families[field].add(reading.family)

    incoherent_energy_families = {
        reading.family
        for reading in readings
        if _incoherent_explicit_energy_pair(reading)
    }

    fields: list[EnsembleField] = []
    for field in FIELDS:
        if field == "calories" and incoherent_energy_families:
            reasons.append(
                "OCR_ENERGY_UNIT_MISMATCH:" + ",".join(sorted(incoherent_energy_families))
            )
            # A visible kJ/kcal contradiction is hard evidence that at least one
            # energy glyph was misread. Do not let repeated OCR of the suspect
            # kcal token become an exact ensemble value. A later fresh crop may
            # recover a coherent printed pair; this observation remains REVIEW.
            continue
        if bounded_families[field]:
            reasons.append(
                f"OCR_BOUNDED_CORE_VALUE:{field}:{','.join(sorted(bounded_families[field]))}"
            )
            # Do not choose an exact value for a field for which any credible
            # OCR family saw a printed inequality. REVIEW is intentional: a
            # later fresh observation may resolve the glyph, but arithmetic or
            # majority voting must never turn a bound into an exact macro.
            continue
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
        if complete_basis_families and independent_families >= 2 and corroborated == len(FIELDS):
            # A real observed Mercadona failure mode is losing only the `100 g`
            # glyph in one OCR engine while both independent engines agree on
            # every core value. A single explicit basis is acceptable only when
            # it belongs to a complete source and the whole value tuple is
            # independently corroborated, with no competing explicit basis.
            reasons.append("SINGLE_ENGINE_BASIS_WITH_FULL_CORE_CORROBORATION")
        else:
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
    # The label parser intentionally required at least two energy digits in its
    # generic kcal matcher to reduce OCR false positives. This synthetic tuple is
    # already numeric ensemble evidence, so zero/single-digit energy must not be
    # turned back into a false MISSING_CORE during the independent coherence pass.
    synthetic_calories = f"{nutrition['calories']:.1f}".rjust(4, "0")
    synthetic = (
        f"Información nutricional por {synthetic_basis}\n"
        f"Valor energético {synthetic_calories} kcal\n"
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
    basis_is_safely_observed = (
        len(basis_families) >= 2
        or bool(complete_basis_families)
    )
    safely_corroborated = (
        independent_families >= 2
        and basis_is_safely_observed
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