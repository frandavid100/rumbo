from __future__ import annotations

"""Narrow Mercadona OCR rescue for vinegar energy carried by explicit acidity.

The generic nutrition parser intentionally treats a kcal/core-macro discrepancy
as REVIEW because fibre, polyols, alcohol and organic acids are not part of the
four persisted core fields. For vinegar, however, the label can itself expose
an acidity percentage. Regulation (EU) 1169/2011 Annex XIV assigns organic acids
3 kcal/g. This module therefore permits one bounded rescue only when independent
OCR families read the same vinegar/acidity/kJ/kcal evidence and that explicit
acid contribution accounts for the otherwise unexplained energy.

No missing macro is inferred, no numeric OCR value is edited, and any safety
blocker other than the energy/core-macro mismatch keeps the observation REVIEW.
"""

import re

import mercadona_safety_blocked_ocr_expansion as base
from nutrition_ocr_ensemble import OCREnsembleResult


CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
ORGANIC_ACID_KCAL_PER_G = 3.0
ALLOWED_REVIEW_PREFIXES = (
    "ENERGY_MACRO_MISMATCH",
    "ENERGY_MACRO_MISMATCH_STRICT",
)

_ACIDITY_RE = re.compile(r"\bacidez\s*[:;]?\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*%", re.I)
_KJ_RE = re.compile(r"(?<![\d.])(\d{1,4}(?:[.,]\d{1,2})?)\s*k\s*j\b", re.I)
_KCAL_RE = re.compile(r"(?<![\d.])(\d{1,4}(?:[.,]\d{1,2})?)\s*kcal\b", re.I)
_VINEGAR_RE = re.compile(r"\bvinagre\b", re.I)


def _number(token: str) -> float:
    return float(token.replace(",", "."))


def _family_observation(text: str):
    if not _VINEGAR_RE.search(text or ""):
        return None
    acidity = _ACIDITY_RE.search(text or "")
    kj = _KJ_RE.search(text or "")
    kcal = _KCAL_RE.search(text or "")
    if not (acidity and kj and kcal):
        return None
    return (_number(acidity.group(1)), _number(kj.group(1)), _number(kcal.group(1)))


def _reading_text(reading) -> str:
    parsed = getattr(reading, "parsed", reading)
    return str(getattr(parsed, "normalized_text", "") or "")


def _explicit_family_observations(readings):
    by_family: dict[str, list[tuple[float, float, float]]] = {}
    for _strategy, family, reading in readings:
        observed = _family_observation(_reading_text(reading))
        if observed is not None:
            by_family.setdefault(str(family).strip().lower(), []).append(observed)

    representatives: dict[str, tuple[float, float, float]] = {}
    for family, observations in by_family.items():
        unique = []
        for observed in observations:
            if not any(
                abs(observed[0] - other[0]) <= .1
                and abs(observed[1] - other[1]) <= 1.0
                and abs(observed[2] - other[2]) <= 1.0
                for other in unique
            ):
                unique.append(observed)
        if len(unique) == 1:
            representatives[family] = unique[0]
    return representatives


def promote_explicit_vinegar_acidity(ensemble, readings):
    """Promote a fully corroborated vinegar tuple only when acidity explains kcal.

    The check is deliberately narrower than the generic parser:
    - explicit 100 ml basis;
    - all four core values already present and independently corroborated;
    - fat/carbohydrate/protein are explicitly zero;
    - the only blocker is energy/core-macro mismatch;
    - at least two OCR families independently read `vinagre`, `Acidez N%`, kJ and
      kcal from the same bounded first-party label image;
    - kJ and kcal agree, the families agree, and 3 kcal/g * acidity explains the
      declared kcal within a tight rounding allowance.
    """
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return ensemble
    if ensemble.basis != "100_ml":
        return ensemble
    nutrition = ensemble.nutrition or {}
    if any(field not in nutrition for field in CORE):
        return ensemble
    if int(getattr(ensemble, "corroborated_fields", 0) or 0) != len(CORE):
        return ensemble
    if int(getattr(ensemble, "independent_engine_families", 0) or 0) < 2:
        return ensemble
    if any(float(nutrition[field]) != 0.0 for field in ("fat_g", "carbohydrate_g", "protein_g")):
        return ensemble

    reasons = tuple(str(reason) for reason in ensemble.reasons)
    if not reasons or any(
        not any(reason.startswith(prefix) for prefix in ALLOWED_REVIEW_PREFIXES)
        for reason in reasons
    ):
        return ensemble

    observations = _explicit_family_observations(readings)
    if len(observations) < 2:
        return ensemble

    values = list(observations.values())
    acidity0, kj0, kcal0 = values[0]
    for acidity, kj, kcal in values[1:]:
        if abs(acidity - acidity0) > .1 or abs(kj - kj0) > 1.0 or abs(kcal - kcal0) > 1.0:
            return ensemble

    declared_kcal = float(nutrition["calories"])
    if abs(kcal0 - declared_kcal) > 1.0:
        return ensemble
    if abs(kj0 / 4.184 - declared_kcal) > 1.5:
        return ensemble

    acid_kcal = acidity0 * ORGANIC_ACID_KCAL_PER_G
    if abs(acid_kcal - declared_kcal) > max(3.0, declared_kcal * .10):
        return ensemble

    note = f"EXPLICIT_VINEGAR_ACIDITY_ENERGY_COHERENCE:{acidity0:g}%"
    return OCREnsembleResult(
        status="DECLARED",
        basis=ensemble.basis,
        nutrition=dict(nutrition),
        confidence=ensemble.confidence,
        fields=ensemble.fields,
        corroborated_fields=ensemble.corroborated_fields,
        independent_engine_families=ensemble.independent_engine_families,
        reasons=(note,),
    )


_ORIGINAL_TRY_FUSE = base._try_fuse


def _try_fuse(readings, target_kind: str):
    candidate = _ORIGINAL_TRY_FUSE(readings, target_kind)
    return promote_explicit_vinegar_acidity(candidate, readings)


def main() -> int:
    base._try_fuse = _try_fuse
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
