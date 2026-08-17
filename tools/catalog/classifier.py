from __future__ import annotations
from dataclasses import dataclass, field
import re, unicodedata
from typing import Iterable

CLASSIFIER_VERSION = "4.1.0"

NUTRITIONAL_ROLES = {
    "PRIMARY_PROTEIN", "COMPLEMENTARY_PROTEIN",
    "PRIMARY_CARBOHYDRATE", "COMPLEMENTARY_CARBOHYDRATE",
    "CONCENTRATED_FAT", "COMPLEMENTARY_FAT", "VEGETABLE", "FRUIT",
}
CULINARY_ROLES = {
    "PLATE_CENTER", "PLATE_BASE", "SIDE", "TOPPING", "SAUCE_DRESSING",
    "CEREAL_BASE", "CEREAL_MIX_IN", "POWDER_BASE", "POWDER_MIX_IN",
    "SANDWICH_BASE", "SANDWICH_FILLING", "SPREAD", "COOKING_MEDIUM",
    "BINDER", "COATING", "SEASONING", "STANDALONE", "BEVERAGE", "DESSERT",
}
TYPE_POLICIES = {
    "MILK_BASE": (250, 150, 350), "CREAMY_BASE": (150, 100, 300),
    "BREAKFAST_CEREAL": (50, 25, 80), "PROTEIN_POWDER": (30, 20, 50),
    "COCOA_POWDER": (10, 5, 25),
    "DRY_RICE": (80, 40, 120), "DRY_PASTA": (80, 40, 120),
    "FRESH_STARCH": (250, 100, 400), "BREAD": (70, 30, 150),
    "MAIN_MEAT": (150, 75, 250), "MAIN_FISH": (170, 80, 300),
    "MAIN_EGG": (120, 50, 240), "VEGETABLE": (200, 75, 400),
    "FRUIT": (150, 75, 300), "CULINARY_OIL": (10, 5, 15),
    "FAT_COMPLEMENT": (30, 10, 80), "SAUCE": (40, 10, 100),
    "SNACK_DESSERT": (100, 30, 250), "COOKING_INGREDIENT": (20, 5, 80),
    "LEGUME": (180, 80, 300), "CHEESE": (40, 15, 100),
    "UNKNOWN": (100, 20, 300),
}
# Calibrados contra el conjunto dorado. Se aplican a la ración de política, no a 100 g.
COMPLEMENTARY_THRESHOLDS_PER_SERVING = {"protein_g": 5.0, "carbohydrate_g": 10.0, "fat_g": 5.0}

@dataclass(frozen=True)
class ProductFeatures:
    name: str
    legal_name: str | None = None
    ingredients: str | None = None
    family: str | None = None
    subcategory: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    carbohydrate_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None

@dataclass(frozen=True)
class Assignment:
    value: str; confidence: float; rule_id: str; evidence: tuple[str, ...]; automatic: bool = True

@dataclass
class ClassificationResult:
    culinary_type: Assignment | None = None
    nutritional_roles: list[Assignment] = field(default_factory=list)
    culinary_roles: list[Assignment] = field(default_factory=list)
    preferred_grams: float | None = None
    minimum_grams: float | None = None
    maximum_grams: float | None = None
    properties: dict[str, bool] = field(default_factory=dict)
    relations: list[dict] = field(default_factory=list)
    review_reasons: list[str] = field(default_factory=list)
    @property
    def classified(self) -> bool:
        confidences = ([self.culinary_type.confidence] if self.culinary_type else []) + [x.confidence for x in self.nutritional_roles + self.culinary_roles]
        return self.culinary_type is not None and bool(self.culinary_roles) and not self.review_reasons and bool(confidences) and min(confidences) >= .80

def norm(v):
    s=unicodedata.normalize("NFD",(v or "").lower()); return "".join(c for c in s if unicodedata.category(c)!="Mn")
def product_text(f): return " ".join(norm(v) for v in [f.name,f.legal_name]).strip()
def _a(value,confidence,rule,*evidence): return Assignment(value,confidence,rule,tuple(evidence))
def serving_amount(f,key,grams):
    v=getattr(f,key); return None if v is None else v*grams/100.0

def classify_type(f):
    p=product_text(f)
    rules=[
        (r"\b(proteina en polvo|whey|protein powder|isolat[eo])\b","PROTEIN_POWDER","type.protein_powder"),
        (r"\b(cacao puro|cacao en polvo|cocoa powder)\b","COCOA_POWDER","type.cocoa_powder"),
        (r"\b(leche|bebida de soja|bebida de avena|bebida de almendra)\b","MILK_BASE","type.milk_base"),
        (r"\b(yogur|yoghurt|kefir|queso fresco batido)\b","CREAMY_BASE","type.creamy_base"),
        (r"\b(corn flakes|copos de maiz|muesli|granola|cereal de desayuno)\b","BREAKFAST_CEREAL","type.breakfast_cereal"),
        (r"\barroz\b","DRY_RICE","type.dry_rice"),
        (r"\b(macarron|macarrones|pasta seca|espagueti|spaghetti|helices|penne|tallarin|fideo)\b","DRY_PASTA","type.dry_pasta"),
        (r"\b(patata|boniato|batata|yuca)\b","FRESH_STARCH","type.fresh_starch"),
        (r"\b(pan|pita|tortilla de trigo)\b","BREAD","type.bread"),
        (r"\b(lentejas?|garbanzos?|alubias?|judias? blancas?|judias? pintas?)\b","LEGUME","type.legume"),
        (r"\b(queso|parmesano|mozzarella|cheddar)\b","CHEESE","type.cheese"),
        (r"\b(aceite de oliva|aceite de girasol|aceite vegetal|aove)\b","CULINARY_OIL","type.culinary_oil"),
        (r"\b(salsa|mayonesa|ketchup|tomate frito|mostaza)\b","SAUCE","type.sauce"),
        (r"\b(huevo|huevos)\b","MAIN_EGG","type.main_egg"),
        (r"\b(salmon|lubina|dorada|merluza|bacalao|atun|sardina|caballa|pescado)\b","MAIN_FISH","type.main_fish"),
        (r"\b(pollo|pavo|cerdo|vacuno|ternera|cordero|carne)\b","MAIN_MEAT","type.main_meat"),
        (r"\b(nuez|nueces|almendra|avellana|cacahuete|pistacho|aceituna|guacamole)\b","FAT_COMPLEMENT","type.fat_complement"),
        (r"\b(tomates?|calabacines?|berenjenas?|pimientos?|cebollas?|zanahorias?|brocolis?|coliflores?|pepinos?|lechugas?|espinacas?|alcachofas?)\b","VEGETABLE","type.vegetable"),
        (r"\b(platano|banana|manzana|pera|naranja|mandarina|melocoton|kiwi|mango|melon|sandia|uva|fresa|cereza)\b","FRUIT","type.fruit"),
    ]
    for pattern,typ,rid in rules:
        if re.search(pattern,p): return _a(typ,.98,rid,f"name/legal:{p}")
    return None

def nutritional_roles(f,typ,serving):
    roles=[]
    semantic={"MAIN_MEAT":"PRIMARY_PROTEIN","MAIN_FISH":"PRIMARY_PROTEIN","MAIN_EGG":"PRIMARY_PROTEIN","DRY_RICE":"PRIMARY_CARBOHYDRATE","DRY_PASTA":"PRIMARY_CARBOHYDRATE","FRESH_STARCH":"PRIMARY_CARBOHYDRATE","BREAD":"PRIMARY_CARBOHYDRATE","LEGUME":"PRIMARY_CARBOHYDRATE","CULINARY_OIL":"CONCENTRATED_FAT","VEGETABLE":"VEGETABLE","FRUIT":"FRUIT"}
    if typ in semantic: roles.append(_a(semantic[typ],.98,f"nutrition.semantic.{typ.lower()}",f"culinary_type:{typ}"))
    if typ in {"MILK_BASE","CREAMY_BASE","CHEESE","LEGUME","FAT_COMPLEMENT"}:
        p=serving_amount(f,"protein_g",serving)
        if p is not None and p>=5: roles.append(_a("COMPLEMENTARY_PROTEIN",.90,"nutrition.threshold.complementary_protein",f"protein/serving:{p:.2f}g",f"serving:{serving}g"))
    if typ in {"FRUIT","MILK_BASE","CREAMY_BASE"}:
        c=serving_amount(f,"carbohydrate_g",serving)
        if c is not None and c>=10: roles.append(_a("COMPLEMENTARY_CARBOHYDRATE",.88,"nutrition.threshold.complementary_carbohydrate",f"carbohydrate/serving:{c:.2f}g",f"serving:{serving}g"))
    if typ in {"CHEESE","FAT_COMPLEMENT","SAUCE","CREAMY_BASE"}:
        fat=serving_amount(f,"fat_g",serving)
        if fat is not None and fat>=5: roles.append(_a("COMPLEMENTARY_FAT",.88,"nutrition.threshold.complementary_fat",f"fat/serving:{fat:.2f}g",f"serving:{serving}g"))
    if typ=="BREAKFAST_CEREAL": roles.append(_a("PRIMARY_CARBOHYDRATE",.95,"nutrition.semantic.breakfast_cereal","type:BREAKFAST_CEREAL"))
    if typ=="PROTEIN_POWDER":
        p=serving_amount(f,"protein_g",serving)
        if p is not None and p>=15: roles.append(_a("COMPLEMENTARY_PROTEIN",.96,"nutrition.semantic.protein_powder",f"protein/serving:{p:.2f}g"))
    return list({x.value:x for x in roles}.values())

def culinary_roles(typ):
    mapping={
        "MILK_BASE":["CEREAL_BASE","POWDER_BASE","BEVERAGE","STANDALONE"],"CREAMY_BASE":["CEREAL_BASE","POWDER_BASE","STANDALONE","DESSERT"],
        "BREAKFAST_CEREAL":["CEREAL_MIX_IN"],"PROTEIN_POWDER":["POWDER_MIX_IN"],"COCOA_POWDER":["POWDER_MIX_IN","TOPPING"],
        "DRY_RICE":["PLATE_BASE","SIDE"],"DRY_PASTA":["PLATE_BASE","SIDE"],"FRESH_STARCH":["PLATE_BASE","SIDE"],"BREAD":["SANDWICH_BASE","PLATE_BASE","STANDALONE"],
        "MAIN_MEAT":["PLATE_CENTER","SANDWICH_FILLING"],"MAIN_FISH":["PLATE_CENTER","SANDWICH_FILLING"],"MAIN_EGG":["PLATE_CENTER","SANDWICH_FILLING","BINDER"],
        "VEGETABLE":["SIDE","TOPPING"],"FRUIT":["STANDALONE","DESSERT"],"CULINARY_OIL":["COOKING_MEDIUM","SAUCE_DRESSING"],"FAT_COMPLEMENT":["TOPPING","STANDALONE"],
        "SAUCE":["SAUCE_DRESSING","TOPPING"],"LEGUME":["PLATE_CENTER","PLATE_BASE","SIDE"],"CHEESE":["TOPPING","SANDWICH_FILLING","STANDALONE"],"COOKING_INGREDIENT":["BINDER","COATING","SEASONING"],
    }
    return [_a(r,.95,f"culinary.type_policy.{typ.lower()}",f"culinary_type:{typ}") for r in mapping.get(typ,[])]

def relations_for(roles: Iterable[Assignment]):
    values={r.value for r in roles}; out=[]
    for role,target in {"CEREAL_MIX_IN":"CEREAL_BASE","POWDER_MIX_IN":"POWDER_BASE","SPREAD":"SANDWICH_BASE","SANDWICH_FILLING":"SANDWICH_BASE"}.items():
        if role in values: out.append({"source_role":role,"intensity":"REQUIRE","target_role":target,"hard":True})
    for role in {"TOPPING","SAUCE_DRESSING","COOKING_MEDIUM","BINDER","COATING","SEASONING"}&values:
        out.append({"source_role":role,"intensity":"FORBID","target_role":"ALONE","hard":True})
    return out

def classify(f):
    r=ClassificationResult(); typ=classify_type(f)
    if typ is None: r.review_reasons.append("UNKNOWN_CULINARY_TYPE"); return r
    r.culinary_type=typ; pref,mi,ma=TYPE_POLICIES[typ.value]; r.preferred_grams,r.minimum_grams,r.maximum_grams=pref,mi,ma
    r.nutritional_roles=nutritional_roles(f,typ.value,pref); r.culinary_roles=culinary_roles(typ.value); r.relations=relations_for(r.culinary_roles)
    rv={x.value for x in r.culinary_roles}; r.properties={"standalone_allowed":bool(rv&{"STANDALONE","BEVERAGE","DESSERT","PLATE_CENTER","PLATE_BASE","SIDE"}),"requires_cooking":typ.value in {"DRY_RICE","DRY_PASTA","MAIN_MEAT","MAIN_FISH","MAIN_EGG","LEGUME"},"divisible":True}
    if not r.nutritional_roles and typ.value not in {"SAUCE","COOKING_INGREDIENT","COCOA_POWDER"}: r.review_reasons.append("NO_NUTRITIONAL_ROLE")
    if not r.culinary_roles: r.review_reasons.append("NO_CULINARY_ROLE")
    if any(v is None for v in (f.calories,f.protein_g,f.carbohydrate_g,f.fat_g)): r.review_reasons.append("INCOMPLETE_CORE_NUTRITION")
    if "CEREAL_MIX_IN" in rv and not any(x["target_role"]=="CEREAL_BASE" for x in r.relations): r.review_reasons.append("MISSING_CEREAL_BASE_REQUIREMENT")
    if "POWDER_MIX_IN" in rv and not any(x["target_role"]=="POWDER_BASE" for x in r.relations): r.review_reasons.append("MISSING_POWDER_BASE_REQUIREMENT")
    return r
