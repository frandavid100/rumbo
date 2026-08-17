from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import html as html_lib
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import carrefour_radar_catalog_importer as base
from classifier import ProductFeatures
from classifier_quality import CLASSIFIER_VERSION, classify
from nutrition_validation import VALIDATOR_VERSION, validate_nutrition


IMPORTER_VERSION = "radarsuper-carrefour-1.1.0"


def nutrition_section(plain: str) -> str:
    """Return only the visible nutrition table text, never the product prose.

    The previous importer searched the whole page, so package sizes such as
    '500 g' could be captured as protein/salt. RadarSuper renders a dedicated
    'Información nutricional' section followed by a 'Datos nutricionales:'
    attribution; parsing is deliberately confined to that block.
    """
    low = plain.lower()
    starts = [low.find("información nutricional"), low.find("informacion nutricional")]
    starts = [x for x in starts if x >= 0]
    if not starts:
        return ""
    start = min(starts)
    ends = []
    for marker in ("datos nutricionales:", "en esta ficha", "sobre este producto"):
        i = low.find(marker, start + 1)
        if i >= 0:
            ends.append(i)
    end = min(ends) if ends else min(len(plain), start + 1800)
    return plain[start:end]


def row_grams(section: str, label_pattern: str) -> float | None:
    m = re.search(
        rf"(?:^|\s){label_pattern}\s+(?:—|–|-)?\s*([0-9]+(?:[.,][0-9]+)?)\s*g\b",
        section,
        re.I,
    )
    return base.decimal(m.group(1)) if m else None


def parse_nutrition(plain: str) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    section = nutrition_section(plain)
    if not section:
        return (None, None, None, None, None, None)

    km = re.search(
        r"Valor energ[eé]tico\s+(?:(?:[0-9]+(?:[.,][0-9]+)?)\s*kJ\s*/\s*)?(?:—\s*/\s*)?([0-9]+(?:[.,][0-9]+)?)\s*kcal\b",
        section,
        re.I,
    )
    kcal = base.decimal(km.group(1)) if km else None
    fat = row_grams(section, r"Grasas?(?:\s+totales?)?")
    carb = row_grams(section, r"Hidratos?\s+de\s+carbono")
    protein = row_grams(section, r"Prote[ií]nas?")
    fiber = row_grams(section, r"Fibra(?:\s+alimentaria)?")
    salt = row_grams(section, r"Sal")
    return kcal, protein, carb, fat, fiber, salt


def parse_product(url: str, family: str) -> base.ProductRecord:
    observed = datetime.now(timezone.utc).isoformat()
    fallback_sku = url.rstrip("/").split("/")[-1]
    try:
        raw = base.fetch_text(url)
        plain = base.textify(raw)
        name = base.first_match([r"<h1[^>]*>(.*?)</h1>", r"<title[^>]*>(.*?)</title>"], raw)
        name = base.clean_fragment(name) or fallback_sku
        sku = base.first_match([r'"sku"\s*:\s*"([^"]+)"', r"SKU\s*:?\s*([A-Za-z0-9_-]+)"], raw) or fallback_sku
        gtin = base.first_match([r'"gtin13"\s*:\s*"(\d{8,14})"', r'"gtin"\s*:\s*"(\d{8,14})"'], raw)
        brand = base.first_match([r'"brand"\s*:\s*\{[^{}]*"name"\s*:\s*"([^"]+)"', r"Marca\s*</[^>]+>\s*<[^>]+>\s*([^<]+)"], raw)
        carrefour_url = base.first_match([r'"url"\s*:\s*"(https://www\.carrefour\.es/supermercado/[^"]+)"', r'href=["\'](https://www\.carrefour\.es/supermercado/[^"\']+)["\']'], raw)

        ingredients = base.first_match([
            r"Ingredientes\s*</h[1-6]>\s*<p[^>]*>(.*?)</p>",
            r"Ingredientes\s*</[^>]+>\s*<[^>]+>(.*?)</[^>]+>",
            r'"ingredients"\s*:\s*"([^"]+)"',
        ], raw)
        ingredients = base.clean_fragment(ingredients)
        legal_name = base.first_match([
            r"Denominaci[oó]n legal\s*</h[1-6]>\s*<p[^>]*>(.*?)</p>",
            r"Denominaci[oó]n legal\s*</[^>]+>\s*<[^>]+>(.*?)</[^>]+>",
        ], raw)
        legal_name = base.clean_fragment(legal_name)

        crumbs = [label for _, label in base.extract_links(raw, "/carrefour/c/") if label]
        subcategory = crumbs[-1] if crumbs else None
        kcal, protein, carb, fat, fiber, salt = parse_nutrition(plain)

        has_off_note = bool(re.search(r"Datos nutricionales\s*:\s*Open Food Facts|Open Food Facts", nutrition_section(plain), re.I))
        core_complete = all(x is not None for x in (kcal, fat, carb, protein))
        evidence_level = "MATCHED" if core_complete else None
        nutrition_source = "OPEN_FOOD_FACTS_VIA_RADARSUPER" if core_complete and has_off_note else ("RADARSUPER" if core_complete else None)

        price = None
        pm = re.search(r"(?:cuesta|precio)[^\d]{0,30}([\d]+(?:[.,]\d+)?)\s*€", plain, re.I)
        if pm:
            price = base.decimal(pm.group(1))

        return base.ProductRecord(
            url, carrefour_url, sku, gtin, name, base.clean_fragment(brand), legal_name,
            ingredients, family, subcategory, kcal, protein, carb, fat, fiber, salt,
            price, evidence_level, nutrition_source, observed,
            hashlib.sha256(raw.encode()).hexdigest(),
        )
    except Exception as exc:
        return base.ProductRecord(
            url, None, fallback_sku, None, fallback_sku, None, None, None,
            family, None, None, None, None, None, None, None, None, None, None,
            observed, "", f"{type(exc).__name__}:{exc}",
        )


def persist(db, r: base.ProductRecord) -> tuple[bool, bool, str, tuple[str, ...]]:
    pid = "carrefour:" + r.retailer_sku
    db.execute("INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?)",
               (pid, r.gtin, r.name, r.brand, r.legal_name, r.ingredients, r.family, r.subcategory,
                r.radar_url, r.carrefour_url, r.page_sha256))
    db.execute("INSERT OR REPLACE INTO retailer_listings VALUES(?,?,?,?,?,?,?)",
               ("CARREFOUR", r.retailer_sku, pid, r.carrefour_url, r.price_eur, r.observed_at,
                "UNKNOWN" if r.fetch_error else "ACTIVE"))

    core_complete = all(x is not None for x in (r.calories, r.protein_g, r.carbohydrate_g, r.fat_g))
    if not core_complete:
        db.execute("INSERT OR REPLACE INTO classifications VALUES(?,?,?,?,?,?,?,?,?)",
                   (pid, CLASSIFIER_VERSION, None, None, None, None, 0, "NUTRITION_MISSING", '["NUTRITION_MISSING"]'))
        return False, False, "NUTRITION_MISSING", ("NUTRITION_MISSING",)

    check = validate_nutrition(r.calories, r.protein_g, r.carbohydrate_g, r.fat_g, r.fiber_g, r.salt_g)
    if not check.valid:
        db.execute("INSERT OR REPLACE INTO classifications VALUES(?,?,?,?,?,?,?,?,?)",
                   (pid, CLASSIFIER_VERSION, None, None, None, None, 0, "NUTRITION_INVALID", json.dumps(check.reasons)))
        return False, False, "NUTRITION_INVALID", check.reasons

    db.execute("INSERT OR REPLACE INTO nutrition VALUES(?,?,?,?,?,?,?,?,?,?)",
               (pid, r.calories, r.protein_g, r.carbohydrate_g, r.fat_g, r.fiber_g, r.salt_g,
                r.nutrition_evidence_level or "MATCHED", r.nutrition_source or "RADARSUPER", r.observed_at))
    f = ProductFeatures(
        name=r.name, legal_name=r.legal_name, ingredients=r.ingredients,
        family=r.family, subcategory=r.subcategory, calories=r.calories,
        protein_g=r.protein_g, carbohydrate_g=r.carbohydrate_g,
        fat_g=r.fat_g, fiber_g=r.fiber_g,
    )
    result = classify(f)
    ctype = result.culinary_type.value if result.culinary_type else None
    status = "MENU_ELIGIBLE" if result.classified else "REVIEW"
    db.execute("INSERT OR REPLACE INTO classifications VALUES(?,?,?,?,?,?,?,?,?)",
               (pid, CLASSIFIER_VERSION, ctype, result.preferred_grams, result.minimum_grams, result.maximum_grams,
                int(result.classified), status, json.dumps(result.review_reasons, ensure_ascii=False)))
    for axis, roles in (("NUTRITIONAL", result.nutritional_roles), ("CULINARY", result.culinary_roles)):
        for a in roles:
            db.execute("INSERT OR REPLACE INTO classification_roles VALUES(?,?,?,?,?,?)",
                       (pid, axis, a.value, a.confidence, a.rule_id, json.dumps(a.evidence, ensure_ascii=False)))
    return True, result.classified, status, tuple(result.review_reasons)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="carrefour-catalog-quality-output")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--max-products", type=int, default=0)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    cats = base.category_urls()
    missing = sorted(base.ALLOWED_TOP_CATEGORIES - set(cats))
    if missing:
        print("warning missing categories:", missing, flush=True)
    refs: list[tuple[str, str]] = []
    enum_counts = {}
    for family, url in sorted(cats.items()):
        products = base.enumerate_category(family, url, args.max_pages or None)
        enum_counts[family] = len(products)
        refs.extend((p, family) for p in products)
    unique = {}
    for u, f in refs:
        unique.setdefault(u, f)
    refs = list(unique.items())
    if args.max_products:
        refs = refs[:args.max_products]

    db = base.init_db(out / "carrefour_food_catalog.sqlite")
    for k, v in {
        "schema_version": "carrefour-dev-mirror-2",
        "importer_version": IMPORTER_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "nutrition_validator_version": VALIDATOR_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "catalog_identity_source": "RadarSuper mirror of Carrefour",
        "nutrition_policy": "MATCHED; scoped nutrition table only; blocking plausibility validation",
    }.items():
        db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)", (k, v))

    counts = {
        "DISCOVERABLE": len(refs), "IDENTIFIED": 0, "NUTRITIONALLY_USABLE": 0,
        "CLASSIFIED": 0, "MENU_ELIGIBLE": 0, "REVIEW": 0,
        "NUTRITION_MISSING": 0, "NUTRITION_INVALID": 0, "FETCH_ERROR": 0,
    }
    source_counts: dict[str, int] = {}
    rejection_reasons: dict[str, int] = {}
    observations = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        future_map = {ex.submit(parse_product, u, f): (u, f) for u, f in refs}
        for i, fut in enumerate(cf.as_completed(future_map), 1):
            r = fut.result()
            observations.append(asdict(r))
            if r.fetch_error:
                counts["FETCH_ERROR"] += 1
            else:
                counts["IDENTIFIED"] += 1
            usable, classified, status, reasons = persist(db, r)
            if usable:
                counts["NUTRITIONALLY_USABLE"] += 1
                source_counts[r.nutrition_source or "UNKNOWN"] = source_counts.get(r.nutrition_source or "UNKNOWN", 0) + 1
            if classified:
                counts["CLASSIFIED"] += 1
                counts["MENU_ELIGIBLE"] += 1
            elif status in counts:
                counts[status] += 1
            for reason in reasons:
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            if i % 100 == 0 or i == len(refs):
                db.commit()
                pct = (i / len(refs) * 100) if refs else 100
                print(
                    f"progress={i}/{len(refs)} ({pct:.1f}%) usable={counts['NUTRITIONALLY_USABLE']} "
                    f"eligible={counts['MENU_ELIGIBLE']} invalid={counts['NUTRITION_INVALID']}",
                    flush=True,
                )
    db.commit()
    db.close()

    observations.sort(key=lambda x: (x["family"], x["retailer_sku"]))
    with (out / "observations.jsonl").open("w", encoding="utf-8") as fh:
        for x in observations:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    summary = {
        "importer_version": IMPORTER_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "nutrition_validator_version": VALIDATOR_VERSION,
        "allowed_food_categories": sorted(base.ALLOWED_TOP_CATEGORIES),
        "discovered_categories": cats,
        "enumerated_per_category": enum_counts,
        "unique_product_urls": len(refs),
        "counts": counts,
        "nutrition_sources": source_counts,
        "rejection_reasons": rejection_reasons,
        "provenance_note": "Identity/listing is obtained from RadarSuper's Carrefour mirror. Nutrition attributed there to Open Food Facts is stored as MATCHED, never DECLARED Carrefour evidence.",
        "distribution_note": "Development artifact only; do not redistribute as a Carrefour-derived database without rights review.",
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if refs else 2


if __name__ == "__main__":
    raise SystemExit(main())
