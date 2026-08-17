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


CLASSIFIER_VERSION = "4.6.1-quality"

FISH = r"atun|atún|anchoa|anchoas|caballa|caballas|bonito|sardina|sardinas|salmon|salmón|lubina|dorada|merluza|bacalao|pescado|sepia|calamar|calamares|chipiron|chipirón|chipirones|gamba|gambas|langostino|langostinos|mejillon|mejillón|mejillones|melva|pulpo"
VEGETABLE = r"pimiento|pimientos|tomate|tomates|calabacin|calabacín|berenjena|berenjenas|cebolla|cebollas|zanahoria|zanahorias|brocoli|brócoli|coliflor|esparrago|espárrago|guisante|guisantes|pepino|pepinos|lechuga|espinaca|espinacas|alcachofa|alcachofas|champinon|champiñón|seta|setas|puerro|puerros|repollo"


def _override(value: str, rule_id: str, p: str) -> Assignment:
    return _a(value, .98, rule_id, f"name/legal:{p}")


def classify_type(f: ProductFeatures) -> Assignment | None:
    """Resolve the whole product before reacting to ingredient/flavour words."""
    p = product_text(f)
    family = (f.family or "").lower()

    # Heterogeneous or ready preparations take priority over their ingredients.
    prepared = (
        r"\b(arroz a banda|arroz tres delicias|arroz negro preparado|paella preparada|"
        r"macarrones? bolo(?:n|ñ)esa|espaguetis? bolo(?:n|ñ)esa|"
        r"sopa de |caldo (?:casero|natural|de |reducido|bajo)|fumet|gazpacho|"
        r"crema (?:casera )?de |alb[oó]ndigas|costillas? .* con salsa|"
        r"plato preparado|listo para comer)\b"
    )
    if re.search(prepared, p) or re.search(r"^tarrito\b", p) or re.search(r"^pizza\b", p):
        return _override("PREPARED_DISH", "type.context.prepared_dish", p)

    # Whole-product supports before words naming flavours or fillings.
    if re.search(r"^pan\b", p):
        return _override("BREAD", "type.context.bread_head", p)
    if re.search(r"\b(mermelada|confitura|fruta para untar|untable de)\b", p):
        return _override("SPREAD", "type.context.spread", p)
    if re.search(r"\b(fresas? de goma|geles? dulces|gominolas?)\b", p):
        return _override("SNACK_DESSERT", "type.context.gummy_sweet", p)
    if re.search(r"^bebida de (?:maracuya|maracuyá|melocoton|melocotón|mango|frutas?|naranja|manzana|pera)\b", p):
        return _override("BEVERAGE", "type.context.fruit_beverage", p)

    # Condiments before ingredient words such as arroz, tomate or fruta.
    if re.search(r"^(?:crema al )?vinagre\b|\bvinagre de arroz\b|^salsa\b|^k[eé]tchup\b|^mayonesa\b|^mostaza\b|\btomate frito\b", p):
        return _override("SAUCE", "type.context.sauce_head", p)

    # Fish identity before preservation medium (oil) or preparation qualifier.
    if re.search(rf"\b(?:{FISH})\b", p) and not re.search(r"\bsabor (?:a |de )?(?:atun|atún|salmon|salmón|pescado)\b", p):
        if re.search(rf"^(?:filetes? de |lomos? de |ventresca de |trozos? de |carne de )?(?:{FISH})\b", p) or re.search(r"\bmarisco y pescado\b", family):
            return _override("MAIN_FISH", "type.context.fish_head", p)
        if re.search(r"\b(conservas|aceite, especias y salsas)\b", family) and re.search(rf"\b(?:{FISH})\b", p[:90]):
            return _override("MAIN_FISH", "type.context.conserved_fish", p)

    if re.search(r"^(?:jamon cocido|jamón cocido|fiambre cocido)\b", p):
        return _override("CURED_MEAT", "type.context.cooked_cold_cut", p)

    # Culinary oil only when oil is the product itself, never merely an ingredient.
    oil_head = re.search(r"^(?:aceite de (?:oliva|girasol|coco|aguacate|sesamo|sésamo|vegetal)|aove)\b", p)
    if oil_head:
        return _override("CULINARY_OIL", "type.context.oil_head", p)

    # Kits are ingredients/preparation systems rather than their seasoning words.
    if re.search(r"\bkit\b", p):
        return _override("COOKING_INGREDIENT", "type.context.kit", p)

    legacy = legacy_classify_type(f)
    if legacy is None:
        return None

    # Defensive corrections for legacy keyword collisions.
    if legacy.value == "CULINARY_OIL" and not oil_head:
        if re.search(rf"\b(?:{FISH})\b", p):
            return _override("MAIN_FISH", "type.context.fish_over_oil", p)
        if re.search(r"\b(tomate frito|salsa|vinagre)\b", p):
            return _override("SAUCE", "type.context.sauce_over_oil", p)
        if re.search(rf"\b(?:{VEGETABLE})\b", p):
            return _override("VEGETABLE", "type.context.vegetable_over_oil", p)
        if re.search(r"\b(pan|picos?|regaña|regana)\b", p):
            return _override("BREAD", "type.context.bread_over_oil", p)
        if re.search(r"\b(caldo|sopa|crema|gazpacho|fumet)\b", p):
            return _override("PREPARED_DISH", "type.context.prepared_over_oil", p)
        # Unknown head: safer to review than to claim the product itself is oil.
        return None
    if legacy.value == "DRY_RICE" and re.search(r"\bvinagre\b", p):
        return _override("SAUCE", "type.context.vinegar_over_rice", p)
    if legacy.value == "FRUIT" and re.search(r"\b(mermelada|confitura|gelatina|golosina|caramelo|goma|untable|para untar)\b", p):
        return _override("SPREAD" if re.search(r"\b(mermelada|confitura|untable|para untar)\b", p) else "SNACK_DESSERT", "type.context.processed_fruit", p)
    if legacy.value == "MAIN_EGG" and re.search(rf"\b(?:{FISH})\b", p):
        return _override("MAIN_FISH", "type.context.fish_over_egg", p)
    if legacy.value == "MAIN_MEAT" and re.search(r"\b(caldo|sopa|crema)\b", p):
        return _override("PREPARED_DISH", "type.context.prepared_over_meat", p)
    if legacy.value == "SAUCE" and re.search(r"\b(alb[oó]ndigas|costillas?|pollo|pechuga|carne)\b", p):
        return _override("PREPARED_DISH", "type.context.prepared_over_sauce", p)
    if legacy.value == "DRY_PASTA" and re.search(r"\b(bolo(?:n|ñ)esa|tarrito|sopa|plato preparado|listo para comer)\b", p):
        return _override("PREPARED_DISH", "type.context.prepared_over_pasta", p)
    if legacy.value == "DRY_RICE" and re.search(r"\b(arroz a banda|arroz tres delicias|tarrito|paella preparada|listo para comer)\b", p):
        return _override("PREPARED_DISH", "type.context.prepared_over_rice", p)
    if legacy.value == "FRESH_STARCH" and re.search(r"^pan\b", p):
        return _override("BREAD", "type.context.bread_over_potato", p)
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
