from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    nutritional_roles: tuple[str, ...]
    culinary_roles: tuple[str, ...]
    food_family: str | None
    portion_basis_grams: float
    confidence: float
    status: str
    rule_ids: tuple[str, ...]


FAMILIES = {
    "pollo": ("pollo", "pechuga de pollo"),
    "pavo": ("pavo",), "cerdo": ("cerdo", "lomo", "jamon"),
    "vacuno": ("ternera", "vacuno", "buey"), "cordero": ("cordero",),
    "conejo": ("conejo",), "huevo": ("huevo",),
    "atun": ("atun",), "salmon": ("salmon",), "sardina": ("sardina",),
    "merluza": ("merluza",), "bacalao": ("bacalao",), "lubina": ("lubina",),
    "dorada": ("dorada",), "leche": ("leche",), "yogur": ("yogur",),
    "queso": ("queso",), "arroz": ("arroz",), "trigo": ("trigo", "pan", "pasta", "macarron", "espagueti"),
    "avena": ("avena",), "maiz": ("maiz",), "centeno": ("centeno",),
    "patata": ("patata",), "boniato": ("boniato", "batata"),
    "lenteja": ("lenteja",), "garbanzo": ("garbanzo",), "alubia": ("alubia", "judia blanca"),
    "guisante": ("guisante",), "soja": ("soja",), "almendra": ("almendra",),
    "cacahuete": ("cacahuete",), "nuez": ("nuez",), "avellana": ("avellana",),
    "aceituna": ("aceituna", "aceite de oliva"), "tomate": ("tomate",),
    "pimiento": ("pimiento",), "calabacin": ("calabacin",), "berenjena": ("berenjena",),
    "zanahoria": ("zanahoria",), "cebolla": ("cebolla",), "ajo": ("ajo",),
    "brocoli": ("brocoli",), "coliflor": ("coliflor",), "espinaca": ("espinaca",),
    "lechuga": ("lechuga",), "manzana": ("manzana",), "platano": ("platano",),
    "naranja": ("naranja",), "pera": ("pera",), "melocoton": ("melocoton",),
    "fresa": ("fresa",), "uva": ("uva",), "sandia": ("sandia",), "melon": ("melon",),
    "kiwi": ("kiwi",), "aguacate": ("aguacate",),
}


def normalized(text: str) -> str:
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def classify(name: str, group_id: str, nutrition: dict[str, float | None]) -> Classification:
    n = normalized(name)
    portion, portion_rule = _portion(n, group_id)
    culinary, culinary_rule = _culinary(n, group_id)
    family = _family(n)
    roles: set[str] = set()
    protein = (nutrition.get("protein_g") or 0.0) * portion / 100.0
    carbs = (nutrition.get("carbohydrate_g") or 0.0) * portion / 100.0
    fat = (nutrition.get("fat_g") or 0.0) * portion / 100.0

    if group_id == "2":
        roles.add("PRIMARY_PROTEIN")
    elif group_id in {"3", "4"} and protein >= 12:
        roles.add("PRIMARY_PROTEIN")
    elif group_id == "7" and protein >= 5:
        roles.add("COMPLEMENTARY_PROTEIN")
    elif protein >= 5:
        roles.add("COMPLEMENTARY_PROTEIN")

    if group_id == "6" and carbs >= 20:
        roles.add("PRIMARY_CARBOHYDRATE")
    elif group_id == "7" and any(word in n for word in ("lenteja", "garbanzo", "alubia", "judia", "guisante", "soja")) and carbs >= 20:
        roles.add("PRIMARY_CARBOHYDRATE")
    elif carbs >= 10:
        roles.add("COMPLEMENTARY_CARBOHYDRATE")

    if group_id == "5" and fat >= 5:
        roles.add("CONCENTRATED_FAT")
    elif fat >= 5:
        roles.add("COMPLEMENTARY_FAT")
    if group_id == "8":
        roles.add("VEGETABLE")
    if group_id == "9" and "aceituna" not in n and not any(word in n for word in ("zumo", "nectar", "refresco")):
        roles.add("FRUIT")

    core = all(nutrition.get(field) is not None for field in ("calories", "protein_g", "carbohydrate_g", "fat_g"))
    ambiguous = group_id in {"12", "13"} or not culinary
    excluded = group_id == "11" and any(word in n for word in
                                        ("alcohol", "cerveza", "vino", "licor", "whisky", "ron ", "ginebra"))
    empty_beverage = group_id == "11" and sum(nutrition.get(field) or 0.0 for field in
                                               ("protein_g", "carbohydrate_g", "fat_g")) == 0.0
    status = ("EXCLUDED_SCOPE" if excluded or empty_beverage else
              "MENU_ELIGIBLE" if core and not ambiguous else
              "NUTRITION_MISSING" if not core else "REVIEW")
    confidence = 0.95 if not ambiguous else 0.65
    return Classification(
        tuple(sorted(roles)), tuple(sorted(culinary)), family, portion, confidence, status,
        (portion_rule, culinary_rule, "nutrition-v1"),
    )


def _portion(name: str, group: str) -> tuple[float, str]:
    if group == "1":
        if "en polvo" in name: return 25.0, "portion:dairy-powder-25"
        if "queso" in name: return 30.0, "portion:cheese-30"
        if name.startswith(("leche ", "batido ", "bebida ")) or "yogur liquido" in name: return 200.0, "portion:dairy-drink-200"
        return 125.0, "portion:dairy-125"
    if group == "2": return 60.0, "portion:egg-60"
    if group == "3" and any(x in name for x in ("bacon", "beicon", "chorizo", "salami", "salchichon", "mortadela", "jamon", "pate", "embutido")):
        return 50.0, "portion:processed-meat-50"
    if group == "4" and "conserva" in name: return 100.0, "portion:canned-fish-100"
    if group in {"3", "4"}: return 150.0, "portion:center-150"
    if group == "5": return 10.0, "portion:fat-10"
    if group == "6":
        if "pan" in name: return 60.0, "portion:bread-60"
        if any(x in name for x in ("cocido", "hervido", "cocinada", "cocinados")): return 200.0, "portion:cooked-grain-200"
        return 80.0, "portion:dry-grain-80"
    if group == "7":
        if any(x in name for x in ("almendra", "nuez", "avellana", "cacahuete", "pistacho", "semilla")): return 30.0, "portion:nut-30"
        if any(x in name for x in ("cocida", "cocido", "hervida", "hervido", "conserva")): return 180.0, "portion:cooked-pulse-180"
        return 80.0, "portion:dry-pulse-80"
    if group == "8": return 200.0, "portion:vegetable-200"
    if group == "9" and "aceituna" in name: return 30.0, "portion:olive-30"
    if group == "9" and any(word in name for word in ("zumo", "nectar", "refresco")): return 250.0, "portion:fruit-drink-250"
    if group == "9": return 150.0, "portion:fruit-150"
    if group == "10": return 25.0, "portion:sweet-25"
    if group == "11": return 250.0, "portion:beverage-250"
    return 100.0, "portion:fallback-100"


def _culinary(name: str, group: str) -> tuple[set[str], str]:
    roles: set[str] = set()
    if group == "1":
        if "en polvo" in name:
            roles.add("POWDER_MIX_IN")
        elif "queso" in name:
            roles |= {"TOPPING", "SANDWICH_FILLING", "STANDALONE"}
        elif name.startswith(("leche ", "bebida ", "batido ")) or "yogur liquido" in name:
            roles |= {"CEREAL_BASE", "POWDER_BASE", "BEVERAGE", "STANDALONE"}
        elif any(x in name for x in ("arroz con leche", "natillas", "flan", "crema catalana", "helado")):
            roles |= {"STANDALONE", "DESSERT"}
        else:
            roles |= {"CEREAL_BASE", "POWDER_BASE", "STANDALONE", "DESSERT"}
    elif group == "2": roles |= {"PLATE_CENTER", "SANDWICH_FILLING", "STANDALONE"}
    elif group in {"3", "4"}:
        roles.add("SANDWICH_FILLING")
        if not (group == "3" and any(x in name for x in ("bacon", "beicon", "salami", "salchichon", "mortadela", "jamon", "pate"))):
            roles.add("PLATE_CENTER")
    elif group == "5": roles |= {"COOKING_MEDIUM", "SAUCE_DRESSING"}
    elif group == "6":
        if "pan" in name or "tortilla de trigo" in name: roles |= {"SANDWICH_BASE", "PLATE_BASE", "STANDALONE"}
        elif any(x in name for x in ("cereal de desayuno", "copos", "muesli")): roles.add("CEREAL_MIX_IN")
        elif any(x in name for x in ("harina", "almidon", "fecula")): roles |= {"BINDER", "COATING"}
        else: roles.add("PLATE_BASE")
    elif group == "7":
        if any(x in name for x in ("crema", "pasta de", "mantequilla")): roles |= {"SPREAD", "TOPPING"}
        elif any(x in name for x in ("almendra", "nuez", "avellana", "cacahuete", "pistacho", "semilla")): roles |= {"TOPPING", "STANDALONE"}
        else: roles |= {"PLATE_CENTER", "PLATE_BASE", "SIDE"}
    elif group == "8": roles |= {"SIDE", "STANDALONE"}
    elif group == "9" and "aceituna" in name: roles |= {"TOPPING", "STANDALONE"}
    elif group == "9" and any(word in name for word in ("zumo", "nectar", "refresco")): roles |= {"BEVERAGE", "STANDALONE"}
    elif group == "9": roles |= {"STANDALONE", "DESSERT"}
    elif group == "10":
        if any(x in name for x in ("cacao en polvo", "chocolate en polvo")): roles.add("POWDER_MIX_IN")
        elif any(x in name for x in ("mermelada", "crema")): roles.add("SPREAD")
        elif "azucar" in name: roles |= {"TOPPING", "SEASONING"}
        else: roles |= {"TOPPING", "DESSERT", "STANDALONE"}
    elif group == "11": roles |= {"BEVERAGE", "STANDALONE"}
    elif group == "12" and any(x in name for x in ("sal", "pimienta", "especia", "oregano", "perejil")): roles.add("SEASONING")
    return roles, f"culinary:group-{group}-v1"


def _family(name: str) -> str | None:
    compounds = (
        "pastel", "tarta", "mermelada", "mayonesa", "salsa", "vinagreta", "pizza",
        "croqueta", "empanada", "hamburguesa", "salchicha", "potaje", "guiso", "sopa",
        "crema de", "chocolate con", "cereales desayuno", "barrita", "nectar", "refresco",
    )
    if any(marker in name for marker in compounds):
        return None
    matches = [family for family, terms in FAMILIES.items() if any(term in name for term in terms)]
    return matches[0] if len(matches) == 1 else None
