from pathlib import Path


path = Path(__file__).with_name("nutrition_label_reader.py")
text = path.read_text(encoding="utf-8")

old_version = 'READER_VERSION = "1.4.9"'
if text.count(old_version) != 1:
    raise SystemExit("reader version drift")
text = text.replace(old_version, 'READER_VERSION = "1.4.10"', 1)

old = '''    # A visual table can be linearised value-before-label. Use that layout only
    # when at least two macro fields are missing, every missing macro has an
    # explicit immediately-preceding gram value, and the completed four-field
    # tuple independently passes the strict energy/macronutrient coherence test.
    # Single-field backfills remain REVIEW because a preceding sugar/saturate
    # value can otherwise be mistaken for the next row in ordinary reading order.
    macro_patterns = {
        "fat_g": fat_patterns,
        "carbohydrate_g": carb_patterns,
        "protein_g": protein_patterns,
    }
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
'''
new = '''    # A visual table can be linearised value-before-label. Multi-field reversed
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
'''
if text.count(old) != 1:
    raise SystemExit("reverse-layout block drift")
text = text.replace(old, new, 1)

old_tail = '''    plausible, plausibility_reasons = _plausible(nutrition)
    reasons.extend(plausibility_reasons)
    if not plausible:
        return LabelReadResult("REVIEW", basis, nutrition, min(extraction_confidence, .65), tuple(reasons), normalized)

    if extraction_confidence < .85:
'''
new_tail = '''    plausible, plausibility_reasons = _plausible(nutrition)
    reasons.extend(plausibility_reasons)
    if not plausible:
        return LabelReadResult("REVIEW", basis, nutrition, min(extraction_confidence, .65), tuple(reasons), normalized)

    if single_reversed_macro_candidate is not None:
        reasons.append(f"SINGLE_REVERSED_MACRO_CANDIDATE:{single_reversed_macro_candidate}")
        return LabelReadResult(
            "REVIEW", basis, nutrition, min(extraction_confidence, .84), tuple(reasons), normalized
        )

    if extraction_confidence < .85:
'''
if text.count(old_tail) != 1:
    raise SystemExit("post-plausibility block drift")
text = text.replace(old_tail, new_tail, 1)

path.write_text(text, encoding="utf-8")

mercadona_path = Path(__file__).with_name("mercadona_nutrition_label_reader.py")
mercadona = mercadona_path.read_text(encoding="utf-8")
mercadona_old_version = 'READER_VERSION = "1.0.5"'
if mercadona.count(mercadona_old_version) != 1:
    raise SystemExit("mercadona reader version drift")
mercadona = mercadona.replace(mercadona_old_version, 'READER_VERSION = "1.0.6"', 1)

old_doc = '''    energy coherent. For a REVIEW input, only a plain missing-core/energy-mismatch
    result is eligible; multicolumn, impossible-value, low-confidence and other
    safety reviews remain blocked.
'''
new_doc = '''    energy coherent. For a REVIEW input, only a plain missing-core/energy-mismatch
    or conservative single-reversed-macro candidate result is eligible;
    multicolumn, impossible-value, low-confidence and other safety reviews remain blocked.
'''
if mercadona.count(old_doc) != 1:
    raise SystemExit("mercadona rescue doc drift")
mercadona = mercadona.replace(old_doc, new_doc, 1)

old_review_gate = '''    if result.status == "REVIEW":
        if not any(reason.startswith("MISSING_CORE:") for reason in result.reasons):
            return None
        if any(
            not (
                reason.startswith("MISSING_CORE:")
                or reason.startswith("ENERGY_MACRO_MISMATCH:")
            )
            for reason in result.reasons
        ):
            return None
'''
new_review_gate = '''    if result.status == "REVIEW":
        recoverable_reversed_evidence = any(
            reason.startswith("MISSING_CORE:")
            or reason.startswith("SINGLE_REVERSED_MACRO_CANDIDATE:")
            for reason in result.reasons
        )
        if not recoverable_reversed_evidence:
            return None
        if any(
            not (
                reason.startswith("MISSING_CORE:")
                or reason.startswith("ENERGY_MACRO_MISMATCH:")
                or reason.startswith("SINGLE_REVERSED_MACRO_CANDIDATE:")
            )
            for reason in result.reasons
        ):
            return None
'''
if mercadona.count(old_review_gate) != 1:
    raise SystemExit("mercadona rescue review gate drift")
mercadona = mercadona.replace(old_review_gate, new_review_gate, 1)
mercadona_path.write_text(mercadona, encoding="utf-8")
