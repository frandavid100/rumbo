#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from classifier import CLASSIFIER_VERSION, ProductFeatures, classify
from classify_catalog import SCHEMA as CLASSIFICATION_SCHEMA, store as store_baseline

POLICY_VERSION = "alcampo-manual-policy-2026-08-19.v1"

# foodFamily is deliberately conservative. It is assigned only to simple-food
# classes and only when the product evidence identifies a stable basic food.
COMPOUND_CUES = re.compile(
    r"\b(pizza|lasañ|lasagn|croquet|empanad|rellen|curry|paella|ensalada|gazpacho|salmorejo|sopa|crema de|plato preparado|preparad[oa]|burrito|taco|sándwich|sandwich|bocadillo|hamburguesa|nugget|rebozad|empanizad|salsa|mayonesa|ketchup|pesto)\b",
    re.I,
)

FAMILY_RULES: list[tuple[str,str,str]] = [
    (r"\bpollo\b", "POLLO", "family.chicken"),
    (r"\bpavo\b", "PAVO", "family.turkey"),
    (r"\b(ternera|vacuno)\b", "VACUNO", "family.beef"),
    (r"\bcerdo\b|\bporcino\b", "CERDO", "family.pork"),
    (r"\bconejo\b", "CONEJO", "family.rabbit"),
    (r"\bsalm[oó]n\b", "SALMON", "family.salmon"),
    (r"\bat[uú]n\b", "ATUN", "family.tuna"),
    (r"\bmerluza\b", "MERLUZA", "family.hake"),
    (r"\bbacalao\b", "BACALAO", "family.cod"),
    (r"\bsardina", "SARDINA", "family.sardine"),
    (r"\bcaballa\b", "CABALLA", "family.mackerel"),
    (r"\bdorada\b", "DORADA", "family.seabream"),
    (r"\blubina\b", "LUBINA", "family.seabass"),
    (r"\bgamba|\blangostino", "GAMBA_LANGOSTINO", "family.prawn"),
    (r"\bhuevo", "HUEVO", "family.egg"),
    (r"\barroz\b", "ARROZ", "family.rice"),
    (r"\bpatata\b", "PATATA", "family.potato"),
    (r"\bboniato\b|\bbatata\b", "BONIATO", "family.sweet_potato"),
    (r"\b(lenteja|lentejas)\b", "LENTEJA", "family.lentil"),
    (r"\b(garbanzo|garbanzos)\b", "GARBANZO", "family.chickpea"),
    (r"\b(alubia|alubias|jud[ií]a blanca|jud[ií]as blancas)\b", "ALUBIA", "family.bean"),
    (r"\bpan\b", "PAN", "family.bread"),
    (r"\b(avena|copos de avena)\b", "AVENA", "family.oat"),
    (r"\bquinoa\b", "QUINOA", "family.quinoa"),
    (r"\bma[ií]z\b", "MAIZ", "family.corn"),
    (r"\byogur", "YOGUR", "family.yogurt"),
    (r"\bleche\b", "LECHE", "family.milk"),
    (r"\bpl[aá]tano", "PLATANO", "family.banana"),
    (r"\bmanzana", "MANZANA", "family.apple"),
    (r"\bnaranja", "NARANJA", "family.orange"),
    (r"\bpera\b|\bperas\b", "PERA", "family.pear"),
    (r"\bkiwi", "KIWI", "family.kiwi"),
    (r"\bfresa", "FRESA", "family.strawberry"),
    (r"\bmel[oó]n\b", "MELON", "family.melon"),
    (r"\bsand[ií]a\b", "SANDIA", "family.watermelon"),
    (r"\bpi[nñ]a\b", "PINA", "family.pineapple"),
    (r"\bmelocot[oó]n", "MELOCOTON", "family.peach"),
    (r"\btomate", "TOMATE", "family.tomato"),
    (r"\bcalabac[ií]n", "CALABACIN", "family.zucchini"),
    (r"\bberenjena", "BERENJENA", "family.eggplant"),
    (r"\bzanahoria", "ZANAHORIA", "family.carrot"),
    (r"\bbr[oó]coli", "BROCOLI", "family.broccoli"),
    (r"\bespinaca", "ESPINACA", "family.spinach"),
    (r"\blechuga", "LECHUGA", "family.lettuce"),
    (r"\bpepino", "PEPINO", "family.cucumber"),
    (r"\bpimiento", "PIMIENTO", "family.pepper"),
    (r"\bcebolla", "CEBOLLA", "family.onion"),
    (r"\bchampi[nñ][oó]n", "CHAMPINON", "family.mushroom"),
    (r"\bnuez|\bnueces\b", "NUEZ", "family.walnut"),
    (r"\balmendra", "ALMENDRA", "family.almond"),
    (r"\bcacahuete", "CACAHUETE", "family.peanut"),
    (r"\bavellana", "AVELLANA", "family.hazelnut"),
]

SIMPLE_TYPES = {
    "MAIN_MEAT","MAIN_FISH","MAIN_EGG","DRY_RICE","DRY_PASTA","COOKED_GRAIN","FRESH_STARCH",
    "BREAD","LEGUME","MILK_BASE","CREAMY_BASE","FRUIT","VEGETABLE","DRIED_FRUIT","FAT_COMPLEMENT",
}

# These values are manually accepted as physical order-of-magnitude bases from
# the current type policies. Prepared dishes and role-default auxiliaries are
# intentionally omitted: they require product-specific review or a role default.
PHYSICAL_PORTION_TYPES = {
    "MAIN_MEAT","MAIN_FISH","MAIN_EGG","DRY_RICE","DRY_PASTA","FRESH_FILLED_PASTA","COOKED_GRAIN",
    "FRESH_STARCH","BREAD","LEGUME","BREAKFAST_CEREAL","MILK_BASE","CREAMY_BASE","CHEESE","FRUIT",
    "VEGETABLE","DRIED_FRUIT","FAT_COMPLEMENT","BEVERAGE","PROTEIN_POWDER","COCOA_POWDER","SWEET_POWDER",
    "SANDWICH_FILLING","FLEX_PROTEIN","DESSERT","SNACK",
}

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_taxonomy(
  product_id INTEGER PRIMARY KEY, retailer_category TEXT, evidence_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS food_family_assignments(
  product_id INTEGER PRIMARY KEY, food_family TEXT NOT NULL, confidence REAL NOT NULL,
  rule_id TEXT NOT NULL, evidence_json TEXT NOT NULL, policy_version TEXT NOT NULL,
  origin TEXT NOT NULL, reviewed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS portion_basis(
  product_id INTEGER PRIMARY KEY, portion_basis_grams REAL NOT NULL, material_state TEXT NOT NULL,
  confidence REAL NOT NULL, rule_id TEXT NOT NULL, evidence_json TEXT NOT NULL,
  policy_version TEXT NOT NULL, origin TEXT NOT NULL, reviewed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS manual_classification_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, action TEXT NOT NULL,
  rule_id TEXT NOT NULL, evidence_json TEXT NOT NULL, policy_version TEXT NOT NULL,
  reviewed_at TEXT NOT NULL
);
"""


def stable_id(sku: str) -> int:
    return int.from_bytes(hashlib.sha256(f"alcampo-sku:{sku}".encode()).digest()[:7],"big")


def observations(path: Path) -> dict[int,dict]:
    out={}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        row=json.loads(line); out[stable_id(str(row["sku"]))]=row
    return out


def derive_family(name: str, legal: str | None, ingredients: str | None, culinary_type: str | None):
    if culinary_type not in SIMPLE_TYPES: return None
    text=" ".join(x for x in (name,legal or "") if x)
    if COMPOUND_CUES.search(text): return None
    for pattern,family,rule in FAMILY_RULES:
        if re.search(pattern,text,re.I):
            # Ingredient-heavy products with a simple-sounding front name are not
            # accepted solely from name when the ingredient list clearly indicates a recipe.
            if ingredients and len(ingredients)>500: return None
            return family,rule,{"name":name,"legal_name":legal,"culinary_type":culinary_type}
    return None


def run(db_path: Path, obs_path: Path):
    obs=observations(obs_path)
    con=sqlite3.connect(db_path); con.executescript(CLASSIFICATION_SCHEMA); con.executescript(EXTRA_SCHEMA)
    for table in ("culinary_types","nutritional_role_assignments","culinary_role_assignments","culinary_policies","culinary_relations","review_queue","source_taxonomy","food_family_assignments","portion_basis","manual_classification_audit"):
        con.execute(f"DELETE FROM {table}")
    rows=con.execute("""
      SELECT p.id,p.canonical_name,p.legal_name,p.ingredients,n.calories,n.protein_g,n.carbohydrate_g,n.fat_g,n.fiber_g,
             rl.retailer_sku
      FROM products p
      LEFT JOIN nutrition n ON n.product_id=p.id
      LEFT JOIN retailer_listings rl ON rl.product_id=p.id AND rl.retailer='Alcampo'
    """).fetchall()
    now=datetime.now(timezone.utc).isoformat()
    for pid,name,legal,ingredients,kcal,protein,carbs,fat,fiber,sku in rows:
        o=obs.get(pid,{})
        category=o.get("category")
        if category:
            con.execute("INSERT INTO source_taxonomy VALUES(?,?,?)",(pid,category,json.dumps({"retailer":"Alcampo","category":category},ensure_ascii=False)))
        # Re-run classifier with Alcampo's source category as subcategory evidence.
        result=classify(ProductFeatures(name=name,legal_name=legal,ingredients=ingredients,subcategory=category,calories=kcal,protein_g=protein,carbohydrate_g=carbs,fat_g=fat,fiber_g=fiber))
        store_baseline(con,pid,result)
        ctype=result.culinary_type.value if result.culinary_type else None
        nutrition_ok=all(x is not None for x in (kcal,protein,carbs,fat))

        # Manual-policy food family: conservative by design; missing family does not block levels 1-3.
        fam=derive_family(name,legal,ingredients,ctype)
        if fam:
            family,rule,evidence=fam
            con.execute("INSERT INTO food_family_assignments VALUES(?,?,?,?,?,?,?,?)",(pid,family,0.97,rule,json.dumps(evidence,ensure_ascii=False),POLICY_VERSION,"MANUAL_POLICY",now))
            con.execute("INSERT INTO manual_classification_audit(product_id,action,rule_id,evidence_json,policy_version,reviewed_at) VALUES(?,?,?,?,?,?)",(pid,"ASSIGN_FOOD_FAMILY",rule,json.dumps(evidence,ensure_ascii=False),POLICY_VERSION,now))

        # Explicit canonical portion basis from manually accepted physical type rules.
        if ctype in PHYSICAL_PORTION_TYPES and result.preferred_grams and result.preferred_grams>0:
            basis=float(result.preferred_grams)
            state="AS_SOLD_DRY" if ctype in {"DRY_RICE","DRY_PASTA","BREAKFAST_CEREAL","PROTEIN_POWDER","COCOA_POWDER","SWEET_POWDER"} else "AS_SOLD"
            evidence={"culinary_type_internal":ctype,"source":"manual acceptance of physical type policy","preferred_grams_migration":basis,"category":category}
            rule=f"portion.physical.{ctype.lower()}"
            con.execute("INSERT INTO portion_basis VALUES(?,?,?,?,?,?,?,?,?)",(pid,basis,state,0.95,rule,json.dumps(evidence,ensure_ascii=False),POLICY_VERSION,"MANUAL_POLICY",now))
            con.execute("INSERT INTO manual_classification_audit(product_id,action,rule_id,evidence_json,policy_version,reviewed_at) VALUES(?,?,?,?,?,?)",(pid,"ASSIGN_PORTION_BASIS",rule,json.dumps(evidence,ensure_ascii=False),POLICY_VERSION,now))

        # Classification remains blocked by genuine review reasons. Family absence alone does not block levels 1-3.
        classified=bool(result.classified and nutrition_ok)
        reason=None if classified else ("Falta nutrición comparable" if not nutrition_ok else "Clasificación pendiente de revisión")
        con.execute("UPDATE eligibility SET nutritionally_usable=?,classified=?,menu_eligible=?,reason=? WHERE product_id=?",(int(nutrition_ok),int(classified),int(classified),reason,pid))

    con.execute("INSERT OR REPLACE INTO catalog_metadata(key,value) VALUES('classification_policy_version',?)",(POLICY_VERSION,))
    con.execute("INSERT OR REPLACE INTO catalog_metadata(key,value) VALUES('classifier_version',?)",(CLASSIFIER_VERSION,))
    con.commit()
    report={
      "products":len(rows),
      "nutritionally_usable":con.execute("select count(*) from eligibility where nutritionally_usable=1").fetchone()[0],
      "classified":con.execute("select count(*) from eligibility where classified=1").fetchone()[0],
      "menu_eligible":con.execute("select count(*) from eligibility where menu_eligible=1").fetchone()[0],
      "review_open":con.execute("select count(*) from review_queue where status='OPEN'").fetchone()[0],
      "food_family_assigned":con.execute("select count(*) from food_family_assignments").fetchone()[0],
      "portion_basis_assigned":con.execute("select count(*) from portion_basis").fetchone()[0],
      "nutritional_role_assignments":con.execute("select count(*) from nutritional_role_assignments").fetchone()[0],
      "culinary_role_assignments":con.execute("select count(*) from culinary_role_assignments").fetchone()[0],
      "policy_version":POLICY_VERSION,
    }
    print(json.dumps(report,ensure_ascii=False,indent=2)); con.close()

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("database",type=Path); p.add_argument("observations",type=Path); a=p.parse_args(); run(a.database,a.observations)
