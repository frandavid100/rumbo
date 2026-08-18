from __future__ import annotations

import argparse, json, re, sqlite3, unicodedata
from collections import Counter
from pathlib import Path

VERSION = "carrefour-manual-1.0"
ORIGIN = "MANUAL_GPT_5_6_SOL"

TYPE_POLICIES = {
    "MILK_BASE": (250,150,350), "CREAMY_BASE": (150,100,300), "BREAKFAST_CEREAL": (50,25,80),
    "PROTEIN_POWDER": (30,20,50), "COCOA_POWDER": (10,5,25), "SWEET_POWDER": (15,5,30),
    "BREWED_DRINK_BASE": (7,2,20), "DRY_RICE": (80,40,120), "DRY_PASTA": (80,40,120),
    "COOKED_GRAIN": (180,80,300), "FRESH_FILLED_PASTA": (125,80,200), "FRESH_STARCH": (250,100,400),
    "BREAD": (70,30,150), "MAIN_MEAT": (150,75,250), "CURED_MEAT": (50,20,100),
    "MAIN_FISH": (170,80,300), "MAIN_EGG": (120,50,240), "VEGETABLE": (200,75,400),
    "PICKLED_VEGETABLE": (80,20,180), "FRUIT": (150,75,300), "DRIED_FRUIT": (30,15,60),
    "CULINARY_OIL": (10,5,15), "FAT_COMPLEMENT": (30,10,80), "SAUCE": (40,10,100),
    "SNACK_DESSERT": (100,30,180), "COOKING_INGREDIENT": (60,15,250), "LEGUME": (180,80,300),
    "CHEESE": (40,15,100), "BEVERAGE": (250,100,500), "SPREAD": (35,10,80),
    "SEASONING": (3,1,10), "PREPARED_DISH": (300,150,500), "UNKNOWN": (100,20,300),
}
CULINARY = {
    "MILK_BASE":["CEREAL_BASE","POWDER_BASE","BEVERAGE","STANDALONE"],
    "CREAMY_BASE":["CEREAL_BASE","POWDER_BASE","STANDALONE","DESSERT"],
    "BREAKFAST_CEREAL":["CEREAL_MIX_IN"], "PROTEIN_POWDER":["POWDER_MIX_IN"],
    "COCOA_POWDER":["POWDER_MIX_IN","TOPPING"], "SWEET_POWDER":["POWDER_MIX_IN"],
    "BREWED_DRINK_BASE":["BEVERAGE"], "DRY_RICE":["PLATE_BASE","SIDE"],
    "DRY_PASTA":["PLATE_BASE","SIDE"], "COOKED_GRAIN":["PLATE_BASE","SIDE"],
    "FRESH_FILLED_PASTA":["PLATE_CENTER","PLATE_BASE"], "FRESH_STARCH":["PLATE_BASE","SIDE"],
    "BREAD":["SANDWICH_BASE","PLATE_BASE","STANDALONE"], "MAIN_MEAT":["PLATE_CENTER","SANDWICH_FILLING"],
    "CURED_MEAT":["SANDWICH_FILLING","STANDALONE","TOPPING"], "MAIN_FISH":["PLATE_CENTER","SANDWICH_FILLING"],
    "MAIN_EGG":["PLATE_CENTER","SANDWICH_FILLING","BINDER"], "VEGETABLE":["SIDE","TOPPING"],
    "PICKLED_VEGETABLE":["SIDE","TOPPING","STANDALONE"], "FRUIT":["STANDALONE","DESSERT"],
    "DRIED_FRUIT":["STANDALONE","DESSERT","TOPPING"], "CULINARY_OIL":["COOKING_MEDIUM","SAUCE_DRESSING"],
    "FAT_COMPLEMENT":["TOPPING","STANDALONE"], "SAUCE":["SAUCE_DRESSING","TOPPING"],
    "LEGUME":["PLATE_CENTER","PLATE_BASE","SIDE"], "CHEESE":["TOPPING","SANDWICH_FILLING","STANDALONE"],
    "COOKING_INGREDIENT":["BINDER","COATING"], "BEVERAGE":["BEVERAGE","STANDALONE"],
    "SPREAD":["SPREAD","TOPPING"], "SEASONING":["SEASONING"],
    "SNACK_DESSERT":["STANDALONE","DESSERT"], "PREPARED_DISH":["PLATE_CENTER","STANDALONE"],
}

def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def decide(name, legal, family):
    n, l, f = norm(name), norm(legal), norm(family)
    t = (n + " " + l).strip()
    composite = r"\b(pizza|lasana|canelon|croqueta|albondiga|moussaka|paella|arroz a banda|arroz negro|arroz tres delicias|arroz con |risotto|fideua|wok|bolonesa|guisantes con jamon|pollo al ajillo|ternera a la jardinera|bo bun|plato preparado|listo para comer|fabada|cocido|callos|ensaladilla|quiche|burrito|nugget|varitas? de|palitos? de pescado|rebozad[oa]|empanad[oa]|rellen[oa]|preparacion vegana|tarrito|desde \d+ meses|a partir de \d+ meses)\b"
    if re.search(composite,t) or f == "pizzas y platos preparados": return "PREPARED_DISH", True, "manual.prepared"
    if re.match(r"^(leche fermentada|bifidus|petit\b)",t) or re.search(r"\b(yogur|yoghurt|kefir|skyr|queso fresco batido|cuajada|petit suisse)\b",t): return "CREAMY_BASE",False,"manual.creamy"
    if re.match(r"^(galletas?|chocolate|bombones?|caramelos?|golosinas?|chuches?|regaliz|barritas?|bizcochos?|magdalenas?|croissants?|napolitanas?|palmeras?|donuts?|helados?|sorbetes?|flanes?|natillas?|panna cotta|tarta|pastel|mousse|postre|patatas? fritas|chips|gusanitos|snack|aperitivo|palomitas|cortezas|torreznos|nachos)\b",t) or re.search(r"\b(haribo|fini\b|smint\b|pikotas|goma\b|pica pica|geles dulces)\b",t): return "SNACK_DESSERT",False,"manual.snack"
    if re.match(r"^(agua\b|refresco\b|coca[- ]?cola\b|pepsi\b|tonica\b|limonada\b|zumo\b|nectar\b|mosto\b|batido\b|bebida energetica\b|bebida isotonica\b|bebida de (?!soja|avena|almendra|arroz))",t): return "BEVERAGE",False,"manual.beverage"
    if re.match(r"^(cafe\b|te\b|rooibos\b|infusion\b)",t): return "BREWED_DRINK_BASE",False,"manual.brew"
    if re.match(r"^(leche\b|bebida de (soja|avena|almendra|arroz)\b|preparado lacteo\b|bebida lactea\b)",t): return "MILK_BASE",False,"manual.milk"
    if re.search(r"\bqueso\b",t) or re.match(r"^(parmesano|mozzarella|cheddar|emmental|gouda|manchego|brie|camembert|ricotta|requeson)\b",t): return "CHEESE",False,"manual.cheese"
    if re.search(r"\b(mermelada|confitura|para untar|untable)\b",t) or re.match(r"^(hummus|pate\b|crema de cacahuete|crema de almendra|crema de avellana)",t): return "SPREAD",False,"manual.spread"
    if re.match(r"^aceitunas?\b",t): return "FAT_COMPLEMENT",False,"manual.olives"
    fish=r"atun|anchoa|boqueron|caballa|bonito|sardina|salmon|lubina|dorada|merluza|bacalao|sepia|calamar|chipiron|gamba|langostino|mejillon|melva|pulpo|surimi|rape|trucha|lenguado|rodaballo|panga|berberecho|zamburina|hueva"
    if re.search(rf"\b({fish})s?\b",t): return "MAIN_FISH",False,"manual.fish"
    if re.match(r"^(salsa\b|mayonesa\b|ketchup\b|mostaza\b|vinagre\b|alioli\b|allioli\b|pesto\b|sirope\b|tomate frito\b)",t): return "SAUCE",False,"manual.sauce"
    if re.match(r"^(aceite de (oliva|girasol|lino|coco|aguacate|sesamo|maiz|soja)|aove)\b",t): return "CULINARY_OIL",False,"manual.oil"
    if re.match(r"^(sal\b|pimienta\b|comino\b|oregano\b|perejil\b|curcuma\b|pimenton\b|canela\b|curry\b|azafran\b|ajo y perejil\b|ajo en polvo\b|cebolla en polvo\b|sazonador\b|molinillo sazonador\b)",t): return "SEASONING",False,"manual.seasoning"
    if re.match(r"^(cereales?\b|muesli\b|granola\b|copos de avena\b|copos de maiz\b|corn flakes\b)",t): return "BREAKFAST_CEREAL",False,"manual.cereal"
    if re.match(r"^(pan\b|panecillos?\b|baguette\b|chapata\b|pita\b|tortilla de trigo\b|tostadas?\b|reganas?\b|picos?\b|colines?\b|palitos de pan\b|picatostes\b)",t): return "BREAD",False,"manual.bread"
    if re.match(r"^(huevos?\b|huevo liquido\b|claras? de huevo\b)",t): return "MAIN_EGG",False,"manual.egg"
    if re.search(r"\b(jamon serrano|jamon iberico|chorizo|salchichon|fuet|lomo embuchado|cecina|sobrasada|longaniza|mortadela|salami)\b",t): return "CURED_MEAT",False,"manual.cured"
    if re.match(r"^(ravioli|tortellini|pasta fresca rellena)",t): return "FRESH_FILLED_PASTA",True,"manual.fresh_pasta"
    if re.match(r"^(fideos? yakisoba|yakisoba)",t) or re.search(r"\b(pasta rice .*slim|fideos .*con pollo)\b",t): return "PREPARED_DISH",True,"manual.prepared_pasta"
    if re.match(r"^(macarron|macarrones|espagueti|espaguetis|spaghetti|pasta\b|penne|helices|tallarin|tallarines|fideo|fideos|fusilli|farfalle|rigatoni|linguine|paccheri|caserecce|mafalde)",t): return "DRY_PASTA",False,"manual.pasta"
    if re.match(r"^arroz\b",t): return ("COOKED_GRAIN" if re.search(r"\b(microondas|cocido|listo)\b",t) else "DRY_RICE"),False,"manual.rice"
    if re.match(r"^(pollo|pavo|cerdo|vacuno|ternera|cordero|conejo|carne|solomillo|entrecot|chuleta|filete|pechuga|muslo|costilla|hamburguesa|salchichas?|fiambre|chopped)\b",t) or f == "carne": return "MAIN_MEAT",False,"manual.meat"
    if re.match(r"^(garbanzos?|lentejas?|alubias?|judias? (blancas?|pintas?)|habas?|habitas?|frijoles?)\b",t):
        if re.search(r"\b(con su sofrito|con verduras|a la riojana|con chorizo|con jamon|guisad[oa])\b",t): return "PREPARED_DISH",True,"manual.prepared_legume"
        return "LEGUME",False,"manual.legume"
    if re.match(r"^(patata\b|patatas?\b|yuca\b|boniato\b|batata\b|gnocchi\b|gnocchetti\b|noquis?\b|pure de patata\b)",t): return "FRESH_STARCH",False,"manual.starch"
    if re.match(r"^(nueces?|almendras?|avellanas?|cacahuetes?|pistachos?|anacardos?|pipas? de girasol|aguacate\b|guacamole\b)",t): return "FAT_COMPLEMENT",False,"manual.fat"
    if re.match(r"^(pepinillos?|piparras?|cebollitas?|encurtidos?|palmito\b)",t): return "PICKLED_VEGETABLE",False,"manual.pickle"
    veg=r"tomate|calabacin|berenjena|pimiento|cebolla|zanahoria|brocoli|coliflor|esparrago|guisante|pepino|lechuga|espinaca|alcachofa|maiz dulce|champinon|seta|puerro|repollo|verdura|judia verde|acelga|calabaza|pisto"
    if re.match(rf"^({veg})s?\b",t): return "VEGETABLE",False,"manual.veg"
    if re.match(r"^(datiles?|pasas?|orejones?|ciruelas? pasas?|papaya desecada|arandanos? .*deshidrat|fruta desecada)",t): return "DRIED_FRUIT",False,"manual.dried_fruit"
    fruit=r"platano|banana|manzana|pera|naranja|mandarina|melocoton|nectarina|kiwi|mango|melon|sandia|uva|fresa|freson|cereza|pomelo|mora|arandano|frambuesa|pina|papaya"
    if re.match(rf"^({fruit})s?\b",t):
        if re.search(r"\b(banad[oa]|chocolate|goma|confitad[oa])\b",t): return "SNACK_DESSERT",False,"manual.processed_fruit"
        return "FRUIT",False,"manual.fruit"
    if re.match(r"^(proteina en polvo|whey|aislado de proteina)",t): return "PROTEIN_POWDER",False,"manual.protein_powder"
    if re.match(r"^(cacao puro|cacao en polvo)",t): return "COCOA_POWDER",False,"manual.cocoa"
    if re.match(r"^(azucar|edulcorante|stevia)",t): return "SWEET_POWDER",False,"manual.sweet"
    if re.match(r"^(harina|levadura|maicena|pan rallado|masa de pizza|gelatina neutra)",t): return "COOKING_INGREDIENT",False,"manual.cooking"
    if f == "marisco y pescado": return "MAIN_FISH",False,"manual.family_fish"
    return "UNKNOWN",True,"manual.unknown"

def nutrition_roles(p,c,f,typ):
    if typ == "UNKNOWN": return []
    serving=TYPE_POLICIES[typ][0]; pp=p*serving/100; cc=c*serving/100; ff=f*serving/100
    out=[]
    primary={"MAIN_MEAT":"PRIMARY_PROTEIN","MAIN_FISH":"PRIMARY_PROTEIN","MAIN_EGG":"PRIMARY_PROTEIN","DRY_RICE":"PRIMARY_CARBOHYDRATE","DRY_PASTA":"PRIMARY_CARBOHYDRATE","COOKED_GRAIN":"PRIMARY_CARBOHYDRATE","FRESH_STARCH":"PRIMARY_CARBOHYDRATE","BREAD":"PRIMARY_CARBOHYDRATE","LEGUME":"PRIMARY_CARBOHYDRATE","BREAKFAST_CEREAL":"PRIMARY_CARBOHYDRATE","CULINARY_OIL":"CONCENTRATED_FAT","VEGETABLE":"VEGETABLE","PICKLED_VEGETABLE":"VEGETABLE","FRUIT":"FRUIT","DRIED_FRUIT":"FRUIT"}
    if typ in primary: out.append(primary[typ])
    if typ == "PREPARED_DISH":
        if pp>=20: out.append("PRIMARY_PROTEIN")
        if cc>=25: out.append("PRIMARY_CARBOHYDRATE")
        if ff>=5: out.append("COMPLEMENTARY_FAT")
    if typ in {"MILK_BASE","CREAMY_BASE","CHEESE","LEGUME","FAT_COMPLEMENT","SPREAD","SNACK_DESSERT","CURED_MEAT"} and pp>=5: out.append("COMPLEMENTARY_PROTEIN")
    if typ in {"FRUIT","DRIED_FRUIT","MILK_BASE","CREAMY_BASE","BEVERAGE","SNACK_DESSERT"} and cc>=10: out.append("COMPLEMENTARY_CARBOHYDRATE")
    if typ in {"MILK_BASE","CHEESE","FAT_COMPLEMENT","SAUCE","CREAMY_BASE","SPREAD","SNACK_DESSERT","CURED_MEAT"} and ff>=5: out.append("COMPLEMENTARY_FAT")
    if typ == "PROTEIN_POWDER" and pp>=15: out.append("COMPLEMENTARY_PROTEIN")
    if "PRIMARY_PROTEIN" in out and "COMPLEMENTARY_PROTEIN" in out: out.remove("COMPLEMENTARY_PROTEIN")
    if "PRIMARY_CARBOHYDRATE" in out and "COMPLEMENTARY_CARBOHYDRATE" in out: out.remove("COMPLEMENTARY_CARBOHYDRATE")
    return list(dict.fromkeys(out))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("sqlite"); ap.add_argument("--out",default="carrefour-manual-output"); a=ap.parse_args()
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True); db=sqlite3.connect(a.sqlite); db.row_factory=sqlite3.Row
    rows=db.execute("SELECT p.*,n.calories,n.protein_g,n.carbohydrate_g,n.fat_g FROM products p JOIN nutrition n USING(product_id) ORDER BY p.product_id").fetchall()
    decisions=[]; counts=Counter(); db.execute("DELETE FROM classification_roles WHERE product_id IN (SELECT product_id FROM nutrition)")
    for r in rows:
        typ,review,rule=decide(r["name"],r["legal_name"],r["family"]); pref,mi,ma=TYPE_POLICIES[typ]
        nr=nutrition_roles(r["protein_g"],r["carbohydrate_g"],r["fat_g"],typ); cr=CULINARY.get(typ,[])
        status="REVIEW" if review else "MENU_ELIGIBLE"; reasons=[]
        if review: reasons=["UNKNOWN_CULINARY_TYPE" if typ=="UNKNOWN" else "MANUAL_REVIEW_REQUIRED"]
        if typ=="PREPARED_DISH": reasons.append("PREPARED_DISH_NEEDS_PORTION_REVIEW")
        db.execute("INSERT OR REPLACE INTO classifications VALUES(?,?,?,?,?,?,?,?,?)",(r["product_id"],VERSION,typ,pref,mi,ma,int(not review),status,json.dumps(reasons,ensure_ascii=False)))
        for axis,roles in (("NUTRITIONAL",nr),("CULINARY",cr)):
            for role in roles: db.execute("INSERT OR REPLACE INTO classification_roles VALUES(?,?,?,?,?,?)",(r["product_id"],axis,role,1.0,"manual.catalog_build",json.dumps([ORIGIN,rule],ensure_ascii=False)))
        decisions.append({"product_id":r["product_id"],"name":r["name"],"family":r["family"],"culinary_type":typ,"nutritional_roles":nr,"culinary_roles":cr,"status":status,"review_reasons":reasons,"origin":ORIGIN,"version":VERSION,"decision":rule})
        counts[status]+=1; counts[typ]+=1
    db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)",("manual_classification_version",VERSION)); db.commit(); db.close()
    with (out/"carrefour_manual_classification.jsonl").open("w",encoding="utf-8") as fh:
        for d in decisions: fh.write(json.dumps(d,ensure_ascii=False)+"\n")
    summary={"version":VERSION,"origin":ORIGIN,"nutrition_rows":len(rows),"menu_eligible":counts["MENU_ELIGIBLE"],"review":counts["REVIEW"],"types":{k:v for k,v in sorted(counts.items()) if k not in {"MENU_ELIGIBLE","REVIEW"}}}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
