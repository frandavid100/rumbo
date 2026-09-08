from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

READER_VERSION = "1.4.15"


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

    # Narrow OCR token repairs observed repeatedly in Mercadona nutrition-label
    # evidence. These alter no numeric value and are accepted only in structural
    # contexts that identify a nutrition token rather than free prose.
    text = re.sub(
        r"(?i)(\b\d{1,4}(?:\.\d{1,2})?)[ \t]*(?:keal|kcai|kcall|kcali)(?![a-z0-9])",
        r"\1 kcal",
        text,
    )

    # A rarer OCR failure drops the leading `k` from kcal (`Ícal`/`ical`).
    # Repair it only when a numeric kJ token is visible on that same line, so a
    # standalone prose-like token can never manufacture an energy observation.
    text = re.sub(
        r"(?im)^([^\n]*\b\d{2,4}(?:\.\d+)?[ \t]*k[ \t]*j\b[^\n]*?)"
        r"(\b\d{1,4}(?:\.\d{1,2})?)[ \t]*[ií]cal(?![a-z0-9])",
        r"\1\2 kcal",
        text,
    )

    # Exact standalone row-label substitutions observed in PP-OCR/Tesseract.
    # Deliberately do not repair looser strings or prose such as `a las brasas`.
    text = re.sub(
        r"(?im)^([ \t]*)(?:brasas|vrasas)([ \t]*)$",
        r"\1Grasas\2",
        text,
    )
    # EasyOCR has also emitted `Crasas;` for the printed total-fat row.
    # Repair only an entire standalone row label (with optional row punctuation);
    # prose containing the token remains untouched.
    text = re.sub(
        r"(?im)^([ \t]*)crasas([ \t]*[:;]?[ \t]*)$",
        r"\1Grasas\2",
        text,
    )
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

    # Multilingual beverage labels can put the explicit `per 100 ml` basis on
    # the line immediately before the Spanish nutrition heading. Starting the
    # block at the heading would discard that structural evidence. Preserve only
    # that single preceding line, and only when it independently contains a
    # recognised per-100 basis; ingredient prose farther above remains excluded.
    line_start = text.rfind("\n", 0, start)
    if line_start >= 0:
        previous_line_start = text.rfind("\n", 0, line_start)
        previous_line = text[previous_line_start + 1:line_start]
        if _basis(previous_line) is not None:
            start = previous_line_start + 1

    tail = text[start:]
    folded_tail = _fold(tail)
    # Common packaging sections after the table. Stop conservatively only when
    # the marker is well after the heading so rows are not clipped accidentally.
    ends = []
    for pattern in (
        r"\npreparacion\b", r"\nconservacion\b", r"\ncondiciones de conservacion\b",
        r"\nmodo de empleo\b", r"\nconsumir preferentemente\b",
    ):
        m = re.search(pattern, folded_tail, flags=re.I)
        if m and m.start() > 80:
            ends.append(m.start())

    # Whole-package OCR can interleave a manufacturer/address column in the
    # middle of the nutrition table. `Fabricado por:` is therefore an end marker
    # only when no explicit core nutrient row follows shortly afterwards.
    for m in re.finditer(r"\nfabricado por\b", folded_tail, flags=re.I):
        if m.start() <= 80:
            continue
        after = folded_tail[m.end():m.end() + 260]
        if re.search(
            r"(?:^|\n)\s*(?:grasas?|lipidos?|hidratos? de carbono|carbohidratos?|proteinas?)\b",
            after,
            flags=re.I,
        ):
            continue
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
            # Exact EasyOCR failure observed on Mercadona zero-macro cells: printed `0 g`
            # can become `09`. Treat it as zero only when it is the complete value cell
            # immediately after a recognised nutrient row; do not rewrite arbitrary `09`
            # tokens and do not alter ordinary values such as 9.29 or a bare 9.
            zero_unit_glyph = re.match(
                r"\s*[:;|]?\s*([<>]?)\s*(?:0\s*9|o\s*g)(?:\s*\(\s*\d{1,3}(?:\.\d+)?\s*%\s*\))?\s*(?:\n|$)",
                tail,
                flags=re.I,
            )
            if zero_unit_glyph:
                if zero_unit_glyph.group(1) in ("<", ">"):
                    return None
                return 0.0
            number = re.search(r"([<>]?)\s*(\d{1,4}(?:\.\d{1,2})?)\s*(?:g\b|gramos?\b)?", tail)
            if not number:
                continue
            prefix = tail[:number.start()].strip()
            if any(marker in prefix for marker in blockers):
                continue
            # If prose occurs between the row label and the first number, this
            # is not a numeric nutrition cell. Whole-package OCR can otherwise
            # bind an ingredients line such as `Proteínas de leite ... E-331`
            # to the additive number 331 and hide the real table row later on.
            if re.search(r"[a-z]", prefix, flags=re.I):
                continue
            # An upper/lower bound is useful evidence but is not an exact macro.
            # Keep the whole row in REVIEW instead of silently promoting 0.5.
            if number.group(1) in ("<", ">"):
                return None
            value = _repair_ocr_number(number.group(2))
            if value is not None:
                return value
    return None


def _number_immediately_before(label_patterns: tuple[str, ...], text: str) -> float | None:
    """Read a value placed on the immediately preceding OCR line.

    Column-aware OCR occasionally linearises a two-column nutrition table as
    `12.2 g / Hidratos de Carbono` and `12.4 g / Proteínas`. This helper is
    intentionally narrow: it requires a dedicated numeric line, an explicit
    gram-like unit glyph, no inequality and no intervening prose. Callers must
    still require whole-tuple energy coherence before using these values.
    """
    folded = _fold(text)
    for label in label_patterns:
        for label_match in re.finditer(label, folded, flags=re.I):
            head = folded[max(0, label_match.start() - 60):label_match.start()]
            number = re.search(
                r"(?:^|\n)\s*([<>]?)\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:g|9|q|yg|y)\s*$",
                head,
                flags=re.I,
            )
            if not number or number.group(1) in ("<", ">"):
                continue
            value = _repair_ocr_number(number.group(2))
            if value is not None:
                return value
    return None


def _fat_value(label_patterns: tuple[str, ...], text: str) -> float | None:
    """Avoid treating a saturated-fat cell as total fat after OCR row reversal.

    A real Mercadona label was linearised as `8.9g / Grasas / 3.20 /
    - Baturadas`. The generic row reader correctly sees 3.20 after `Grasas`, but
    that cell belongs to the saturated-fat subrow. Reinterpret the row only when
    an explicit gram value is immediately before `Grasas` *and* the value after
    `Grasas` is immediately followed by a saturate-like row label. Otherwise
    keep the ordinary row-oriented behaviour unchanged.
    """
    ordinary = _number_after(label_patterns, text)
    folded = _strip_ocr_unit_parentheses(_fold(text))
    for label in label_patterns:
        for label_match in re.finditer(label, folded, flags=re.I):
            before = _number_immediately_before((label,), text)
            if before is None:
                continue
            tail = folded[label_match.end():label_match.end() + 90]
            # EasyOCR can linearise a printed total-fat `0 g` cell as the
            # standalone token `09` immediately *before* `Grasas`, while the
            # saturated-fat subrow remains immediately after the label. Accept
            # that reversed value only under this exact three-row structure.
            # This deliberately does not rewrite arbitrary `09` tokens.
            if re.match(
                r"\s*de\s*las\s+cuales\s*:?\s*\n"
                r"\s*(?:[<>]?\s*\d{1,3}(?:\.\d{1,2})?\s*(?:g|q|yg|y)|0\s*9)\s*\n"
                r"\s*[-–—]?\s*(?:saturad|baturad)",
                tail,
                flags=re.I,
            ):
                return before
            if re.match(
                r"\s*[<>]?\s*\d{1,3}(?:\.\d{1,2})?\s*(?:g|9|q|yg|y)?\s*\n\s*[-–—]?\s*(?:saturad|baturad)",
                tail,
                flags=re.I,
            ):
                return before
    # Tesseract can interleave a manufacturer/ingredients column between the
    # printed total-fat label and its value cells. Rescue only the exact zero-fat
    # case when an explicit saturated-fat subrow closes the span and every
    # dedicated gram-like cell before it is zero. This handles two-column labels
    # whose total-fat values are both zero without choosing between conflicting
    # columns or borrowing a saturated-fat value.
    if ordinary is None:
        for label in label_patterns:
            for label_match in re.finditer(label, folded, flags=re.I):
                tail = folded[label_match.end():label_match.end() + 260]
                saturated = re.search(r"\b(?:saturad|baturad)[a-z]*\b", tail, flags=re.I)
                if not saturated:
                    continue
                before_saturated = tail[:saturated.start()]
                cells = list(re.finditer(
                    r"(?m)^\s*([<>]?)\s*(\d{1,3}(?:\.\d{1,2})?)\s*"
                    r"(?:g|9|q|yg|y)\s*(?:\(\s*\d{1,3}(?:\.\d+)?\s*%?\s*\))?\s*$",
                    before_saturated,
                    flags=re.I,
                ))
                if not cells or any(m.group(1) in ("<", ">") for m in cells):
                    continue
                values = [_repair_ocr_number(m.group(2)) for m in cells]
                if values and all(v == 0.0 for v in values):
                    return 0.0
    return ordinary


def _interleaved_carbohydrate(text: str) -> float | None:
    """Handle a recurrent OCR reading order without guessing across rows.

    In narrow Mercadona tables the visual text `Hidratos de Carbono | 2.0 g`
    is often linearised as `Hidratos de / 2.0 g / Carbono`. The value is safe
    only when it is literally bracketed by the two halves of that same label.
    Observed OCR unit glyphs include g, 9, y, q and the two-character `yg`.
    """
    folded = _strip_ocr_unit_parentheses(_fold(text))
    m = re.search(
        r"(?:^|\n)\s*hidratos?\s+de\s+([<>]?)\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:g|9|yg|y|q)?\s+carbono\b",
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

    # Consume only well-known translations that are printed inline after the
    # Spanish row label. This keeps _number_after's prose guard intact while
    # supporting bilingual/multilingual tables such as `Grasas / Fat 0 g`.
    fat_patterns = (
        r"(?:^|\n)\s*[\[|]?\s*grasas?(?:\s*/?\s*(?:lipidos?|ilipidos?|lapidos?|ipidos?|fat|graisses?)(?:\s+totais?)?)?\b",
        r"(?:^|\n)\s*[\[|]?\s*lipidos?\b",
        r"(?:^|\n)\s*[\[|]?\s*grasa total\b",
    )
    carb_patterns = (
        r"(?:^|\n)\s*[\[|]?\s*hidratos? de carbono(?:\s*/\s*(?:carbohydrates?|glucides?))?\b",
        r"(?:^|\n)\s*[\[|]?\s*carbohidratos?\b",
    )
    protein_patterns = (
        r"(?:^|\n)\s*[\[|]?\s*(?:proteinas?|prote_nas?)(?:\s*/\s*(?:protein|proteines?))?(?=[\s._:;|]|$)",
    )

    calories = _energy_kcal(block)
    fat = _fat_value(fat_patterns, block)
    carbs = _interleaved_carbohydrate(block)
    if carbs is None:
        carbs = _number_after(carb_patterns, block)
    protein = _number_after(protein_patterns, block)

    values = {"calories": calories, "fat_g": fat, "carbohydrate_g": carbs, "protein_g": protein}

    # A visual table can be linearised value-before-label. Multi-field reversed
    # layouts can still be completed exactly as before when every missing macro
    # has an explicit immediately-preceding gram value and the full tuple is
    # energy-coherent. A newly observed Mercadona failure mode leaves exactly one
    # macro in that reversed layout. Expose that one value only as REVIEW evidence:
    # it may help a later independent OCR family corroborate the field, but this
    # parser must never promote the single reversed observation by itself.
    macro_patterns = {
        "fat_g": fat_patterns,
        "carbohydrate_g": carb_patterns,
        "protein_g": protein_patterns,
    }
    single_reversed_macro_candidate: str | None = None
    missing_macros = [key for key in macro_patterns if values[key] is None]
    if calories is not None and len(missing_macros) >= 2:
        reversed_values = {
            key: _number_immediately_before(macro_patterns[key], block)
            for key in missing_macros
        }
        if all(value is not None for value in reversed_values.values()):
            completed = dict(values)
            completed.update(reversed_values)
            if all(completed.get(key) is not None for key in ("calories", "fat_g", "carbohydrate_g", "protein_g")):
                completed_nutrition = {key: float(completed[key]) for key in ("calories", "fat_g", "carbohydrate_g", "protein_g")}
                coherent, _ = _plausible(completed_nutrition)
                if coherent:
                    values.update(reversed_values)
    elif calories is not None and len(missing_macros) == 1:
        key = missing_macros[0]
        reversed_value = _number_immediately_before(macro_patterns[key], block)
        if reversed_value is not None:
            completed = dict(values)
            completed[key] = reversed_value
            if all(completed.get(field) is not None for field in ("calories", "fat_g", "carbohydrate_g", "protein_g")):
                completed_nutrition = {
                    field: float(completed[field])
                    for field in ("calories", "fat_g", "carbohydrate_g", "protein_g")
                }
                coherent, _ = _plausible(completed_nutrition)
                if coherent:
                    values[key] = reversed_value
                    single_reversed_macro_candidate = key

    # A forward OCR number outside physical per-100 macro bounds can be package
    # noise immediately after the row label. If all core fields are otherwise
    # present and exactly one macro is impossible, allow an explicit dedicated
    # gram cell immediately before that label to replace the noise only when the
    # completed tuple is energy-coherent. It remains REVIEW evidence until an
    # independent OCR family corroborates it.
    if calories is not None and not missing_macros:
        impossible_forward_macros = [
            key for key in macro_patterns
            if values[key] is not None and (values[key] < 0 or values[key] > 100)
        ]
        if len(impossible_forward_macros) == 1:
            key = impossible_forward_macros[0]
            reversed_value = _number_immediately_before(macro_patterns[key], block)
            if reversed_value is not None:
                completed = dict(values)
                completed[key] = reversed_value
                if all(completed.get(field) is not None for field in ("calories", "fat_g", "carbohydrate_g", "protein_g")):
                    completed_nutrition = {
                        field: float(completed[field])
                        for field in ("calories", "fat_g", "carbohydrate_g", "protein_g")
                    }
                    coherent, _ = _plausible(completed_nutrition)
                    if coherent:
                        values[key] = reversed_value
                        single_reversed_macro_candidate = key

    # Reject individually impossible OCR values before returning a partial read.
    # Previously plausibility checks ran only after all four core fields existed,
    # so a partial `4106 kcal` or `222 g protein` could contaminate the ensemble
    # and create a false conflict against a correct independent engine.
    partial: dict[str, float] = {}
    for key, value in values.items():
        if value is None:
            continue
        if key == "calories":
            if value < 0 or value > 1000:
                reasons.append("IMPOSSIBLE_CALORIES")
                continue
        elif value < 0 or value > 100:
            reasons.append(f"IMPOSSIBLE_{key.upper()}")
            continue
        partial[key] = float(value)

    missing = [k for k in values if k not in partial]
    if missing:
        reasons.append("MISSING_CORE:" + ",".join(missing))
        return LabelReadResult("REVIEW", basis, partial or None, min(extraction_confidence, .60), tuple(reasons), normalized)

    nutrition = partial
    plausible, plausibility_reasons = _plausible(nutrition)
    reasons.extend(plausibility_reasons)
    if not plausible:
        return LabelReadResult("REVIEW", basis, nutrition, min(extraction_confidence, .65), tuple(reasons), normalized)

    if single_reversed_macro_candidate is not None:
        reasons.append(f"SINGLE_REVERSED_MACRO_CANDIDATE:{single_reversed_macro_candidate}")
        return LabelReadResult(
            "REVIEW", basis, nutrition, min(extraction_confidence, .84), tuple(reasons), normalized
        )

    if extraction_confidence < .85:
        reasons.append("LOW_EXTRACTION_CONFIDENCE")
        return LabelReadResult("REVIEW", basis, nutrition, extraction_confidence, tuple(reasons), normalized)

    if basis is None:
        return LabelReadResult("REVIEW", None, nutrition, min(extraction_confidence, .75), tuple(reasons), normalized)

    return LabelReadResult("DECLARED", basis, nutrition, min(1.0, extraction_confidence), tuple(reasons), normalized)
