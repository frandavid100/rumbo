from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import argparse
import json
from pathlib import Path
import re
import unicodedata

VERSION = "1.0.1"
CORE_FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")


@dataclass(frozen=True)
class RescueRead:
    basis: str | None
    nutrition: dict[str, float]
    reasons: tuple[str, ...]


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.replace(",", ".")


def _repair_numeric_token(raw: str, *, has_unit: bool) -> float | None:
    raw = raw.strip().replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None
    # Observed Tesseract failure: terminal printed `g` merged into an integer,
    # e.g. `259` for `25g`. Only repair when no separate unit glyph survived.
    if not has_unit and "." not in raw and raw.endswith("9") and len(raw) >= 3:
        try:
            repaired = float(raw[:-1])
        except ValueError:
            repaired = value
        if 0 <= repaired <= 100:
            return repaired
    return value


def _close(field: str, a: float, b: float) -> bool:
    a, b = float(a), float(b)
    tolerance = (
        max(5.0, .04 * max(abs(a), abs(b), 1.0))
        if field == "calories"
        else max(.6, .10 * max(abs(a), abs(b), 1.0))
    )
    return abs(a - b) <= tolerance


def _coherent(values: dict[str, float]) -> bool:
    if any(field not in values for field in CORE_FIELDS):
        return False
    if values["calories"] < 0 or values["calories"] > 1000:
        return False
    if any(values[field] < 0 or values[field] > 100 for field in CORE_FIELDS[1:]):
        return False
    estimated = 9 * values["fat_g"] + 4 * values["carbohydrate_g"] + 4 * values["protein_g"]
    tolerance = max(8.0, values["calories"] * .10)
    return abs(estimated - values["calories"]) <= tolerance


def _nutrition_tail(text: str) -> str | None:
    folded = _fold(text)
    starts = []
    for pattern in (
        r"\binformacion\s*(?:/\s*informacao)?\s+nutricional\b",
        r"\bnformacion\s+nutricional\b",
        r"\bdeclaracion\s+nutricional\b",
        r"\bvalores\s+nutricionales\b",
    ):
        match = re.search(pattern, folded, flags=re.I)
        if match:
            starts.append(match.start())
    if not starts:
        return None
    # Deliberately do not stop at packaging headings such as CONSERVACIÓN.
    # Column OCR can interleave those headings in the middle of a nutrition
    # table. Safety comes from exact row evidence + independent-family agreement.
    return text[min(starts):min(len(text), min(starts) + 7000)]


def _basis(text: str) -> str | None:
    folded = _fold(text)
    g = bool(re.search(r"\b100\s*(?:g|9|q|y)\b", folded))
    ml = bool(re.search(r"\b100\s*m(?:l|i|1)\b", folded))
    if g and ml:
        return None
    if g:
        return "100_g"
    if ml:
        return "100_ml"
    return None


def _explicit_parallel_columns(text: str) -> bool:
    folded = _fold(text)
    # Reject only explicit adjacent column headings such as `100 ml\n250 ml`.
    # Ordinary macro rows like `12 g` must not be mistaken for a second column.
    if re.search(
        r"\b100\s*(?:g|9|q|y|m(?:l|i|1))\b\s*[\n|/]+\s*"
        r"\d{2,4}\s*(?:g|9|q|y|m(?:l|i|1))\b",
        folded,
        flags=re.I,
    ):
        return True
    return len(re.findall(r"\bpor\s+100\s*(?:g|9|q|y|m(?:l|i|1))\b", folded)) > 1


def _value_token(fragment: str, *, require_unit: bool = True) -> float | None:
    folded = _fold(fragment).strip()
    # Dot leaders and common OCR punctuation are structural noise only.
    folded = re.sub(r"^[\s._:;|·…-]+", "", folded)
    folded = re.sub(r"[\s._:;|·…-]+$", "", folded)
    match = re.fullmatch(
        r"([<>]?)\s*(\d{1,4}(?:\.\d{1,2})?)\s*(g|9|q|y)?",
        folded,
        flags=re.I,
    )
    if not match or match.group(1) in ("<", ">"):
        return None
    unit = match.group(3)
    if require_unit and unit is None:
        raw = match.group(2)
        if not (raw.endswith("9") and "." not in raw and len(raw) >= 3):
            return None
    return _repair_numeric_token(match.group(2), has_unit=unit is not None)


def _line_value_after(lines: list[str], index: int) -> float | None:
    label_line = lines[index]
    # Same-line value after an exact nutrient row label. A unit is not mandatory
    # here because OCR often merges/drops the printed g; row identity is explicit.
    colon = re.split(r"\b(?:grasas?|giasas|lipidos?|grasa\s+total|hidratos?\s+de\s+carbono|carbohidratos?|proteinas?)\b", _fold(label_line), maxsplit=1)
    if len(colon) == 2:
        tail = colon[1]
        # Stop at subordinate rows so saturated/sugar values cannot be borrowed.
        tail = re.split(r"\b(?:de\s+las\s+cuales|de\s+los\s+cuales|saturad|azucar|sal)\b", tail, maxsplit=1)[0]
        candidates = re.findall(r"[<>]?\s*\d{1,4}(?:\.\d{1,2})?\s*(?:g|9|q|y)?", tail)
        parsed = [v for token in candidates if (v := _value_token(token, require_unit=False)) is not None]
        if len(parsed) == 1:
            return parsed[0]
        if len(parsed) > 1:
            return None

    # Value on the immediately following dedicated line. Do not skip prose.
    if index + 1 < len(lines):
        value = _value_token(lines[index + 1], require_unit=True)
        if value is not None:
            return value
    return None


def _line_value_before(lines: list[str], index: int) -> float | None:
    if index == 0:
        return None
    value = _value_token(lines[index - 1], require_unit=True)
    if value is None:
        return None
    # Two consecutive numeric rows immediately before a label are a strong sign
    # of parallel columns (`0.1 g`, `0.3 g`, `Grasas`). Reject rather than choose.
    if index >= 2 and _value_token(lines[index - 2], require_unit=True) is not None:
        return None
    return value


def _macro_from_lines(lines: list[str], field: str, *, allow_before: bool) -> float | None:
    patterns = {
        "fat_g": r"^(?:grasas?|giasas|lipidos?|grasa\s+total)(?:\s*/\s*lipidos?)?\b",
        "carbohydrate_g": r"^(?:hidratos?\s+de\s+carbono|carbohidratos?)\b",
        "protein_g": r"^proteinas?\b",
    }
    pattern = patterns[field]
    values: list[float] = []
    for index, raw_line in enumerate(lines):
        line = _fold(raw_line).strip()
        # Inline tables commonly prefix rows with `-` or `;`.
        line = re.sub(r"^[\s|;:.-]+", "", line)
        if not re.search(pattern, line, flags=re.I):
            continue
        value = _line_value_after(lines, index)
        if value is None and allow_before:
            value = _line_value_before(lines, index)
        if value is not None:
            values.append(value)
    if not values:
        return None
    first = values[0]
    if any(not _close(field, first, other) for other in values[1:]):
        return None
    return first


def _macro_inline(text: str, field: str) -> float | None:
    folded = _fold(text)
    labels = {
        "fat_g": r"(?:grasas?|giasas|lipidos?|grasa\s+total)",
        "carbohydrate_g": r"(?:hidratos?\s+de\s+carbono|carbohidratos?)",
        "protein_g": r"proteinas?",
    }
    pattern = re.compile(
        rf"(?:^|[\n;|]|\s-\s*)\s*{labels[field]}\s*(?:/\s*lipidos?)?\s*[:._-]*\s*"
        r"([<>]?)\s*(\d{1,4}(?:\.\d{1,2})?)\s*(g|9|q|y)?",
        flags=re.I,
    )
    values: list[float] = []
    for match in pattern.finditer(folded):
        if match.group(1) in ("<", ">"):
            continue
        raw = match.group(2)
        unit = match.group(3)
        value = _repair_numeric_token(raw, has_unit=unit is not None)
        if value is not None:
            values.append(value)
    if not values:
        return None
    first = values[0]
    if any(not _close(field, first, other) for other in values[1:]):
        return None
    return first


def _energy(text: str) -> float | None:
    folded = _fold(text)
    values = [float(value) for value in re.findall(r"\b(\d{1,4}(?:\.\d{1,2})?)\s*kcal\b", folded)]
    if not values:
        return None
    # A nutrition section may contain a serving column as well as per-100 values.
    # Do not guess between distinct energy values.
    first = values[0]
    if any(not _close("calories", first, other) for other in values[1:]):
        return None
    return first


def rescue_read(text: str) -> RescueRead:
    tail = _nutrition_tail(text)
    if tail is None:
        return RescueRead(None, {}, ("NO_EXPLICIT_NUTRITION_SECTION",))
    parallel = _explicit_parallel_columns(tail)
    basis = _basis(tail)
    lines = tail.splitlines()
    nutrition: dict[str, float] = {}
    energy = _energy(tail)
    if energy is not None:
        nutrition["calories"] = energy
    for field in ("fat_g", "carbohydrate_g", "protein_g"):
        value = _macro_from_lines(lines, field, allow_before=not parallel)
        if value is None:
            value = _macro_inline(tail, field)
        if value is not None:
            nutrition[field] = value
    reasons = []
    if parallel:
        reasons.append("PARALLEL_COLUMN_SIGNAL")
    return RescueRead(basis, nutrition, tuple(reasons))


def _stable_family_values(engine_rows: list[tuple[str, dict]], field: str) -> dict[str, float]:
    by_family: dict[str, list[float]] = defaultdict(list)
    for strategy, engine in engine_rows:
        family = "paddleocr" if strategy.startswith("paddleocr") else "tesseract" if strategy.startswith("tesseract") else strategy.split("-", 1)[0]
        original = engine.get("nutrition") or {}
        value = original.get(field)
        if value is None:
            value = rescue_read(engine.get("normalized_ocr_text") or "").nutrition.get(field)
        if value is not None:
            by_family[family].append(float(value))
    stable: dict[str, float] = {}
    for family, values in by_family.items():
        first = values[0]
        if all(_close(field, first, other) for other in values[1:]):
            stable[family] = first
    return stable


def rescue_product(row: dict, baseline: dict) -> dict | None:
    engine_rows: list[tuple[str, dict]] = []
    explicit_bases: set[str] = set()
    for attempt in row.get("attempts") or []:
        for strategy, engine in (attempt.get("engines") or {}).items():
            engine_rows.append((strategy, engine))
            read = rescue_read(engine.get("normalized_ocr_text") or "")
            if read.basis:
                explicit_bases.add(read.basis)
    if not engine_rows:
        return None
    expected_basis = baseline.get("basis")
    if expected_basis not in ("100_g", "100_ml") or any(basis != expected_basis for basis in explicit_bases):
        return None
    if expected_basis not in explicit_bases:
        return None

    final: dict[str, float] = {}
    families_by_field: dict[str, list[str]] = {}
    prior = baseline.get("nutrition") or {}
    for field in CORE_FIELDS:
        stable = _stable_family_values(engine_rows, field)
        if "paddleocr" not in stable or "tesseract" not in stable:
            return None
        if not _close(field, stable["paddleocr"], stable["tesseract"]):
            return None
        prior_value = prior.get(field)
        if prior_value is not None:
            if not _close(field, float(prior_value), stable["paddleocr"]):
                return None
            final[field] = float(prior_value)
        else:
            final[field] = float(stable["paddleocr"])
        families_by_field[field] = ["paddleocr", "tesseract"]

    if not _coherent(final):
        return None
    missing = sorted(baseline.get("missing_core_fields") or [])
    if len(missing) != 2 or any(field not in CORE_FIELDS for field in missing):
        return None
    return {
        "product_id": str(row.get("product_id") or ""),
        "ean": row.get("ean"),
        "name": row.get("name"),
        "basis": expected_basis,
        "nutrition": final,
        "recovered_core_fields": missing,
        "families_by_field": families_by_field,
        "parser": f"mercadona_ocr_continuity_rescue/{VERSION}",
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }


def audit(results_path: Path, baseline_path: Path, out_dir: Path) -> dict:
    rows = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    baseline_rows = [json.loads(line) for line in baseline_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    baseline = {str(row.get("product_id") or ""): row for row in baseline_rows}
    promotions = []
    for row in rows:
        pid = str(row.get("product_id") or "")
        prior = baseline.get(pid)
        if prior is None:
            continue
        promoted = rescue_product(row, prior)
        if promoted is not None:
            promotions.append(promoted)

    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "parser": f"mercadona_ocr_continuity_rescue/{VERSION}",
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "processed": len(rows),
        "safe_promotion_products": len(promotions),
        "safe_promotion_product_ids": sorted(item["product_id"] for item in promotions),
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
        "cumulative_after_replay": {
            "catalog_total": 4280,
            "processed": 2943,
            "DECLARED_complete": 262 + len(promotions),
            "REVIEW": 2681 - len(promotions),
            "complete_usable_coverage_pct": round(100.0 * (262 + len(promotions)) / 4280, 4),
            "processed_coverage_pct": round(100.0 * 2943 / 4280, 4),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "safe-promotions.json").write_text(json.dumps(promotions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary = audit(args.results, args.baseline, args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
