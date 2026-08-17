from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Iterable

RESOLVER_VERSION = "1.0.1"
CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")


def norm(value: str | None) -> str:
    text = unicodedata.normalize("NFD", (value or "").lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def tokens(value: str | None) -> set[str]:
    return {x for x in norm(value).split() if len(x) > 1 and x not in {"de", "del", "la", "el", "con", "sin", "hacendado"}}


@dataclass(frozen=True)
class ProductIdentity:
    name: str
    brand: str | None = None
    gtin: str | None = None
    format: str | None = None
    ingredients: str | None = None


@dataclass(frozen=True)
class NutritionCandidate:
    identity: ProductIdentity
    nutrition: dict[str, float | None]
    source: str
    source_url: str
    source_record_id: str | None = None
    observed_at: str | None = None
    upstream_license: str | None = None
    redistribution_allowed: bool = False
    source_family: str | None = None
    claim: str | None = None

    @property
    def complete(self) -> bool:
        return all(isinstance(self.nutrition.get(k), (int, float)) for k in CORE)


@dataclass(frozen=True)
class Match:
    candidate: NutritionCandidate
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Resolution:
    status: str
    level: str
    nutrition: dict[str, float | None] | None
    matches: tuple[Match, ...]
    publishable: bool
    reason: str | None = None


def _ingredient_similarity(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return None
    return len(ta & tb) / len(ta | tb)


def score(target: ProductIdentity, candidate: ProductIdentity) -> tuple[float, tuple[str, ...]]:
    reasons: list[str] = []
    if target.gtin and candidate.gtin:
        if target.gtin != candidate.gtin:
            return 0.0, ("GTIN_CONFLICT",)
        reasons.append("GTIN_EXACT")
        base = 100.0
    else:
        a, b = norm(target.name), norm(candidate.name)
        name_ratio = SequenceMatcher(None, a, b).ratio()
        overlap = len(tokens(a) & tokens(b)) / max(1, len(tokens(a) | tokens(b)))
        base = 45.0 * name_ratio + 35.0 * overlap
        reasons += [f"NAME_RATIO={name_ratio:.3f}", f"TOKEN_OVERLAP={overlap:.3f}"]
    if target.brand and candidate.brand:
        if norm(target.brand) == norm(candidate.brand):
            base += 10.0; reasons.append("BRAND_EXACT")
        else:
            base -= 25.0; reasons.append("BRAND_CONFLICT")
    if target.format and candidate.format:
        if norm(target.format) == norm(candidate.format):
            base += 5.0; reasons.append("FORMAT_EXACT")
        else:
            base -= 10.0; reasons.append("FORMAT_CONFLICT")
    ingredient_similarity = _ingredient_similarity(target.ingredients, candidate.ingredients)
    if ingredient_similarity is not None:
        base += 10.0 * ingredient_similarity
        reasons.append(f"INGREDIENT_SIMILARITY={ingredient_similarity:.3f}")
        if ingredient_similarity < 0.35:
            base -= 30.0; reasons.append("INGREDIENT_CONFLICT")
    return max(0.0, min(110.0, base)), tuple(reasons)


def _nutrition_close(a: dict[str, float | None], b: dict[str, float | None]) -> bool:
    for key in CORE:
        av, bv = a.get(key), b.get(key)
        if not isinstance(av, (int, float)) or not isinstance(bv, (int, float)):
            return False
        tolerance = max(1.0, 0.10 * max(abs(float(av)), abs(float(bv)), 1.0))
        if abs(float(av) - float(bv)) > tolerance:
            return False
    return True


def resolve(target: ProductIdentity, candidates: Iterable[NutritionCandidate], *, require_publishable: bool = True) -> Resolution:
    matches = [Match(c, *score(target, c.identity)) for c in candidates if c.complete]
    matches = [m for m in matches if m.score >= 80.0]
    matches.sort(key=lambda m: m.score, reverse=True)
    if not matches:
        return Resolution("UNRESOLVED", "UNKNOWN", None, tuple(), False, "NO_HIGH_CONFIDENCE_MATCH")

    top = matches[0]
    strong = [m for m in matches if m.score >= max(80.0, top.score - 10.0)]
    families: dict[str, Match] = {}
    for match in strong:
        family = match.candidate.source_family or match.candidate.source
        families.setdefault(family, match)

    if len(families) >= 2:
        independent = list(families.values())
        if any(not _nutrition_close(independent[0].candidate.nutrition, m.candidate.nutrition) for m in independent[1:]):
            return Resolution("REVIEW", "UNKNOWN", None, tuple(strong), False, "NUTRITION_CONFLICT")
        selected = independent[0]
        level = "CORROBORATED"
        publishable = any(m.candidate.redistribution_allowed for m in independent)
    else:
        selected = top
        level = "MATCHED"
        publishable = selected.candidate.redistribution_allowed

    if require_publishable and not publishable:
        return Resolution("BUILD_ONLY", level, selected.candidate.nutrition, tuple(strong), False, "RIGHTS_NOT_CLEARED")
    return Resolution("RESOLVED", level, selected.candidate.nutrition, tuple(strong), publishable, None)
