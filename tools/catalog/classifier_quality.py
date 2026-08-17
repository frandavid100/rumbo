from __future__ import annotations

import re

from classifier import (
    Assignment,
    ClassificationResult,
    ProductFeatures,
    TYPE_POLICIES,
    _a,
    classify_type as legacy_classify_type,
    culinary_roles,
    nutritional_roles,
    product_text,
    relations_for,
)
from nutrition_validation import validate_nutrition


CLASSIFIER_VERSION = "4.6.0-quality"

FISH = r"atun|atún|anchoa|anchoas|caballa|caballas|bonito|sardina|sardinas|salmon|salmón|lubina|dorada|merluza|bacalao|pescado|sepia|calamar|calamares|chipiron|chipirón|chipirones|gamba|gambas|langostino|langostinos|mejillon|mejillón|mejillones|melva|pulpo"


def _override(value: str, rule_id: str, p: str) -> Assignment:
    return _a(value, .98, rule_id, f"name/legal:{p}")


def classify_type(f: ProductFeatures) -> Assignment | None:
    """Context-aware type resolution.

    Whole-product descriptors and head nouns take precedence over ingredient or
    flavour words. This prevents e.g. tuna *in olive oil* becoming CULINARY_OIL
    or rice vinegar becoming DRY_RICE.
    """
    p = product_text(f)

    # Products whose global preparation is more important than an ingredient
    # appearing in the name. PREPARED_DISH remains review-blocked downstream.
    prepared = (
        r"\b(arroz a banda|arroz tres delicias|arroz negro preparado|paella preparada|"
        r"macarrones? bolo(?:n|ñ)esa|espaguetis? bolo(?:n|ñ)esa|"
        r"tarrito .*?(?:arroz|pasta|espagueti|macarron)|"
        r"sopa de |caldo (?:casero|natural|de pollo|de carne|de verduras|de pescado)|"
        r"crema de (?:verduras|calabaza|calabacin|calabacín|jamon|jamón|pollo)|"
        r"plato preparado)\b"
    )
    if re.search(prepared, p):
        return _override("PREPARED_DISH", "type.context.prepared_dish", p)

    # Spreads before the fruit names they contain.
    if re.search(r"\b(mermelada|confitura)\b", p):
        return _override("SPREAD", "type.context.fruit_spread", p)

    # Condiments before ingredient words such as arroz, tomate or fruta.
    if re.search(r"^(?:crema al )?vinagre\b|\bvinagre de arroz\b|^salsa\b|^k[eé]tchup\b|^mayonesa\b|^mostaza\b", p):
        return _override("SAUCE", "type.context.sauce_head", p)

    # Fish identity before preservation medium (oil) or preparation qualifier
    # (e.g. merluza al huevo).
    if re.search(rf"\b(?:{FISH})\b", p) and not re.search(r"\bsabor (?:a |de )?(?:atun|atún|salmon|salmón|pescado)\b", p):
        if re.search(rf"^(?:filetes? de |lomos? de |ventresca de |trozos? de )?(?:{FISH})\b", p) or re.search(r"\bmarisco y pescado\b", (f.family or "").lower()):
            return _override("MAIN_FISH", "type.context.fish_head", p)
        # Conserved fish in categories where the head may include marketing text.
        if re.search(r"\b(conservas|aceite, especias y salsas)\b", (f.family or "").lower()) and re.search(rf"\b(?:{FISH})\b", p[:90]):
            return _override("MAIN_FISH", "type.context.conserved_fish", p)

    # Culinary oil only when oil is the product itself, not merely an ingredient.
    if re.search(r"^(?:aceite de (?:oliva|girasol|coco|aguacate|sesamo|sésamo|vegetal)|aove)\b", p):
        return _override("CULINARY_OIL", "type.context.oil_head", p)

    legacy = legacy_classify_type(f)
    if legacy is None:
        return None

    # Defensive corrections for legacy keyword collisions.
    if legacy.value == "CULINARY_OIL" and re.search(rf"\b(?:{FISH})\b", p):
        return _override("MAIN_FISH", "type.context.fish_over_oil", p)
    if legacy.value == "DRY_RICE" and re.search(r"\bvinagre\b", p):
        return _override("SAUCE", "type.context.vinegar_over_rice", p)
    if legacy.value == "FRUIT" and re.search(r"\b(mermelada|confitura|gelatina|golosina|caramelo)\b", p):
        return _override("SPREAD" if re.search(r"\b(mermelada|confitura)\b", p) else "SNACK_DESSERT", "type.context.processed_fruit", p)
    if legacy.value == "MAIN_EGG" and re.search(rf"\b(?:{FISH})\b", p):
        return _override("MAIN_FISH", "type.context.fish_over_egg", p)
    if legacy.value == "MAIN_MEAT" and re.search(r"\b(caldo|sopa|crema)\b", p):
        return _override("PREPARED_DISH", "type.context.prepared_over_meat", p)
    if legacy.value == "DRY_PASTA" and re.search(r"\b(bolo(?:n|ñ)esa|tarrito|plato preparado|listo para comer)\b", p):
        return _override("PREPARED_DISH", "type.context.prepared_over_pasta", p)
    if legacy.value == "DRY_RICE" and re.search(r"\b(arroz a banda|arroz tres delicias|paella preparada|listo para comer)\b", p):
        return _override("PREPARED_DISH", "type.context.prepared_over_rice", p)
    return legacy


def classify(f: ProductFeatures) -> ClassificationResult:
    r = ClassificationResult()
    typ = classify_type(f)
    if typ is None:
        r.review_reasons.append("UNKNOWN_CULINARY_TYPE")
        return r

    r.culinary_type = typ
    pref, mi, ma = TYPE_POLICIES[typ.value]
    r.preferred_grams, r.minimum_grams, r.maximum_grams = pref, mi, ma
    r.nutritional_roles = nutritional_roles(f, typ.value, pref)
    r.culinary_roles = culinary_roles(typ.value)
    r.relations = relations_for(r.culinary_roles)
    rv = {x.value for x in r.culinary_roles}
    r.properties = {
        "standalone_allowed": bool(rv & {"STANDALONE", "BEVERAGE", "DESSERT", "PLATE_CENTER", "PLATE_BASE", "SIDE"}),
        "requires_cooking": typ.value in {"DRY_RICE", "DRY_PASTA", "FRESH_FILLED_PASTA", "MAIN_MEAT", "MAIN_FISH", "MAIN_EGG", "LEGUME"},
        "requires_preparation": typ.value in {"BREWED_DRINK_BASE", "COOKING_INGREDIENT"},
        "divisible": True,
    }

    if not r.culinary_roles:
        r.review_reasons.append("NO_CULINARY_ROLE")

    nutrition_check = validate_nutrition(f.calories, f.protein_g, f.carbohydrate_g, f.fat_g, f.fiber_g)
    r.review_reasons.extend(x for x in nutrition_check.reasons if x not in r.review_reasons)

    # Heterogeneous prepared dishes remain review-blocked, per the catalog spec.
    if typ.value == "PREPARED_DISH":
        r.review_reasons.append("PREPARED_DISH_NEEDS_PORTION_REVIEW")
    if "CEREAL_MIX_IN" in rv and not any(x["target_role"] == "CEREAL_BASE" for x in r.relations):
        r.review_reasons.append("MISSING_CEREAL_BASE_REQUIREMENT")
    if "POWDER_MIX_IN" in rv and not any(x["target_role"] == "POWDER_BASE" for x in r.relations):
        r.review_reasons.append("MISSING_POWDER_BASE_REQUIREMENT")
    return r
