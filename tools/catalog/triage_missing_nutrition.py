from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unicodedata

from classifier import ProductFeatures, classify_type, CLASSIFIER_VERSION
from mercadona_label_evidence import collect_label_images, nutrition_image_candidates
from mercadona_label_pipeline import download_label_image
from mercadona_weekly_catalog_adapter import deterministic_candidate_ids, fetch_product, fetch_product_ids, stratified_sample
from nutrition_resolver import ProductIdentity, resolve
from nutrition_visual_table_detector import detect_visual_table_regions
from openfoodfacts_adapter import fetch_product as off_fetch, to_candidate as off_candidate

TRIAGE_VERSION = "1.0.0"
SEED = "rumbo-mercadona-pilot-2026-08"
FOOD_CATEGORY_MARKERS = (
    "aceite", "especias", "salsas", "agua", "refrescos", "aperitivos",
    "arroz", "legumbres", "pasta", "azucar", "caramelos", "chocolate",
    "cacao", "cafe", "infusiones", "carne", "cereales", "galletas",
    "charcuteria", "quesos", "congelados", "conservas", "caldos", "cremas",
    "fruta", "verdura", "huevos", "leche", "mantequilla", "panaderia",
    "pasteleria", "pescado", "marisco", "pizzas", "platos preparados",
    "postres", "yogures", "zumos", "bebidas vegetales",
)
GENERIC_SAFE_TYPES = {"FRUIT", "VEGETABLE", "MAIN_EGG"}
GENERIC_REVIEW_TYPES = {"MAIN_MEAT", "MAIN_FISH", "FRESH_STARCH", "COOKED_GRAIN", "LEGUME"}


def _fold(value: str | None) -> str:
    text = unicodedata.normalize("NFD", (value or "").lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _is_food_category(value: str) -> bool:
    folded = _fold(value)
    return any(marker in folded for marker in FOOD_CATEGORY_MARKERS)


def _is_non_food_product(product) -> bool:
    text = _fold(" ".join(x for x in (product.name, product.legal_name) if x))
    patterns = (
        "vela de cumpleanos", "velas de cumpleanos", "vela numero", "vela numeros",
        "servilleta", "mantel", "plato desechable", "vaso desechable", "cubierto desechable",
    )
    return any(p in text for p in patterns)


def _fetch_products(ids: list[str], workers: int = 16):
    products = []
    errors = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(fetch_product, product_id): product_id for product_id in ids}
        for future in as_completed(futures):
            product_id = futures[future]
            try:
                products.append(future.result())
            except Exception as exc:
                errors.append({"product_id": product_id, "error": f"{type(exc).__name__}:{exc}"})
    products.sort(key=lambda x: x.product_id)
    errors.sort(key=lambda x: x["product_id"])
    return products, errors


def _source_page(product) -> str:
    value = product.payload.get("share_url")
    if isinstance(value, str) and value.startswith("http"):
        return value
    slug = product.payload.get("slug")
    if isinstance(slug, str) and slug:
        return f"https://tienda.mercadona.es/product/{product.product_id}/{slug}"
    return f"https://tienda.mercadona.es/product/{product.product_id}"


def _type(product) -> str | None:
    assignment = classify_type(ProductFeatures(
        name=product.name, legal_name=product.legal_name, ingredients=product.ingredients,
        family=product.family, subcategory=product.subcategory,
    ))
    return assignment.value if assignment else None


def _generic_bucket(product, culinary_type: str | None) -> str:
    if culinary_type in GENERIC_SAFE_TYPES and not product.brand and not product.ingredients:
        return "GENERIC_HIGH_CONFIDENCE_CANDIDATE"
    if culinary_type in GENERIC_REVIEW_TYPES and not product.brand and not product.ingredients:
        return "GENERIC_REVIEW_CANDIDATE"
    return "NOT_GENERIC_CANDIDATE"


def _stable_key(product_id: str, suffix: str) -> str:
    return hashlib.sha256(f"{SEED}:{suffix}:{product_id}".encode()).hexdigest()


def main() -> int:
    sample_size = int(os.environ.get("TRIAGE_SIZE", "300"))
    candidate_pool = int(os.environ.get("TRIAGE_CANDIDATE_POOL", "900"))
    visual_budget = int(os.environ.get("TRIAGE_VISUAL_BUDGET", "120"))
    workers = int(os.environ.get("TRIAGE_ACQUISITION_WORKERS", "16"))
    out = Path(os.environ.get("TRIAGE_OUTPUT_DIR", "nutrition-triage-output"))
    out.mkdir(parents=True, exist_ok=True)
    off_dir = out / "off-snapshots"
    off_dir.mkdir(exist_ok=True)

    ids = fetch_product_ids()
    candidate_ids = deterministic_candidate_ids(ids, seed=SEED, limit=candidate_pool)
    products, acquisition_errors = _fetch_products(candidate_ids, workers)
    food = [p for p in products if _is_food_category(p.category_key) and not _is_non_food_product(p)]
    sample = stratified_sample(food, size=sample_size, per_category_cap=24)

    rows = []
    counts = Counter()
    categories = defaultdict(Counter)

    # Stage 1: exact GTIN against OFF only. No OCR and no image download yet.
    for index, p in enumerate(sample, 1):
        culinary_type = _type(p)
        row = {
            "product_id": p.product_id,
            "ean": p.ean,
            "name": p.name,
            "category": p.category_key,
            "culinary_type": culinary_type,
            "ingredients_present": bool(p.ingredients),
            "photo_count": len(p.photos),
            "nutrition_status": "MISSING",
            "structured_source": None,
            "generic_bucket": _generic_bucket(p, culinary_type),
        }
        counts["IDENTIFIED"] += 1
        categories[p.category_key]["IDENTIFIED"] += 1
        if p.ean:
            try:
                fetched = off_fetch(p.ean, snapshot_dir=off_dir, timeout=8.0)
                candidate = off_candidate(fetched)
                if candidate:
                    resolution = resolve(ProductIdentity(
                        name=p.name, brand=p.brand, gtin=p.ean, ingredients=p.ingredients
                    ), [candidate])
                    if resolution.status == "RESOLVED" and resolution.nutrition:
                        core = resolution.nutrition
                        if all(core.get(k) is not None for k in ("calories", "protein_g", "carbohydrate_g", "fat_g")):
                            row["nutrition_status"] = "RESOLVED_STRUCTURED"
                            row["structured_source"] = "Open Food Facts"
                            row["evidence_level"] = resolution.level
                            counts["RESOLVED_STRUCTURED"] += 1
                            categories[p.category_key]["RESOLVED_STRUCTURED"] += 1
            except Exception as exc:
                row.setdefault("source_errors", []).append(f"OFF:{type(exc).__name__}:{exc}")
        rows.append(row)
        if index % 50 == 0:
            print(f"structured={index}/{len(sample)} resolved={counts['RESOLVED_STRUCTURED']}", flush=True)

    unresolved = [r for r in rows if r["nutrition_status"] == "MISSING"]
    product_by_id = {p.product_id: p for p in sample}

    # Stage 2: metadata score for every unresolved product.
    for row in unresolved:
        p = product_by_id[row["product_id"]]
        evidence = collect_label_images(
            retailer_sku=p.product_id, product_name=p.name, images=p.photos,
            source_page=_source_page(p), observed_at=p.observed_at,
        )
        candidates = nutrition_image_candidates(evidence)
        has_back = any(str(x.perspective) == "9" for x in candidates)
        score = 0
        reasons = []
        if p.ean:
            score += 2; reasons.append("GTIN")
        if p.ingredients:
            score += 1; reasons.append("INGREDIENTS")
        if has_back:
            score += 4; reasons.append("PERSPECTIVE_9")
        elif candidates:
            score += 1; reasons.append("PACK_IMAGE")
        if len(candidates) >= 2:
            score += 1; reasons.append("MULTIPLE_IMAGES")
        row["ocr_metadata_score"] = score
        row["ocr_metadata_reasons"] = reasons
        row["has_back_image"] = has_back
        row["label_image_count"] = len(candidates)

    # Stage 3: visual table detection for the best metadata candidates only.
    visual_candidates = sorted(
        (r for r in unresolved if r.get("label_image_count", 0) > 0),
        key=lambda r: (-r.get("ocr_metadata_score", 0), _stable_key(r["product_id"], "visual")),
    )[:visual_budget]
    visual_ids = {r["product_id"] for r in visual_candidates}

    for index, row in enumerate(visual_candidates, 1):
        p = product_by_id[row["product_id"]]
        evidence = collect_label_images(
            retailer_sku=p.product_id, product_name=p.name, images=p.photos,
            source_page=_source_page(p), observed_at=p.observed_at,
        )
        candidates = nutrition_image_candidates(evidence)
        back = next((x for x in candidates if str(x.perspective) == "9"), candidates[0] if candidates else None)
        row["visual_checked"] = True
        if back is None:
            row["visual_table_regions"] = 0
            continue
        try:
            with tempfile.TemporaryDirectory(prefix="rumbo-triage-") as td:
                image = Path(td) / "label.jpg"
                download_label_image(back.image_url, image, timeout=10.0)
                regions = detect_visual_table_regions(image, Path(td) / "regions")
                row["visual_table_regions"] = len(regions)
                row["visual_best_score"] = max((float(x.score) for x in regions), default=0.0)
                if regions:
                    counts["VISUAL_TABLE_FOUND"] += 1
                    categories[p.category_key]["VISUAL_TABLE_FOUND"] += 1
        except Exception as exc:
            row["visual_table_regions"] = 0
            row.setdefault("source_errors", []).append(f"VISUAL:{type(exc).__name__}:{exc}")
        if index % 20 == 0:
            print(f"visual={index}/{len(visual_candidates)} tables={counts['VISUAL_TABLE_FOUND']}", flush=True)

    for row in unresolved:
        if row["product_id"] not in visual_ids:
            row["visual_checked"] = False
            row["visual_table_regions"] = None

        score = row.get("ocr_metadata_score", 0)
        regions = row.get("visual_table_regions")
        if regions and regions > 0:
            row["triage_bucket"] = "OCR_HIGH_PROBABILITY"
            row["ocr_priority_score"] = score + 5
        elif row.get("visual_checked") and score >= 6:
            row["triage_bucket"] = "OCR_MEDIUM_PROBABILITY"
            row["ocr_priority_score"] = score
        elif not row.get("visual_checked") and score >= 7:
            row["triage_bucket"] = "OCR_PENDING_VISUAL_CHECK"
            row["ocr_priority_score"] = score
        elif row["generic_bucket"] != "NOT_GENERIC_CANDIDATE":
            row["triage_bucket"] = row["generic_bucket"]
            row["ocr_priority_score"] = score
        else:
            row["triage_bucket"] = "REVIEW_OR_LOW_PROBABILITY"
            row["ocr_priority_score"] = score
        counts[row["triage_bucket"]] += 1
        categories[row["category"]][row["triage_bucket"]] += 1

    queue = sorted(
        unresolved,
        key=lambda r: (-r.get("ocr_priority_score", 0), _stable_key(r["product_id"], "queue")),
    )

    summary = {
        "triage_version": TRIAGE_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "sampling": {
            "index_size": len(ids), "candidate_pool": candidate_pool,
            "candidate_products_fetched": len(products), "food_candidates": len(food),
            "sample": len(sample), "seed": SEED,
        },
        "counts": dict(counts),
        "structured_resolution_rate": round(counts["RESOLVED_STRUCTURED"] / len(sample), 4) if sample else 0,
        "unresolved_after_structured": len(unresolved),
        "visual_budget": visual_budget,
        "visual_checked": len(visual_candidates),
        "visual_table_rate": round(counts["VISUAL_TABLE_FOUND"] / len(visual_candidates), 4) if visual_candidates else 0,
        "generic_candidates": {
            "high_confidence": sum(r["generic_bucket"] == "GENERIC_HIGH_CONFIDENCE_CANDIDATE" for r in unresolved),
            "review": sum(r["generic_bucket"] == "GENERIC_REVIEW_CANDIDATE" for r in unresolved),
            "note": "Candidates only; no generic nutrition values are assigned by this triage.",
        },
        "acquisition_error_count": len(acquisition_errors),
        "top_ocr_queue": [
            {k: r.get(k) for k in ("product_id", "name", "category", "culinary_type", "triage_bucket", "ocr_priority_score", "visual_table_regions")}
            for r in queue[:50]
        ],
    }
    report = {
        **summary,
        "categories": {k: dict(v) for k, v in sorted(categories.items())},
        "acquisition_errors": acquisition_errors,
        "items": rows,
        "ocr_queue": queue,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if len(sample) == sample_size else 2


if __name__ == "__main__":
    raise SystemExit(main())
