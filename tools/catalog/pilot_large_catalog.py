from __future__ import annotations

from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import tempfile
import time

from classifier import ProductFeatures, classify, classify_type, CLASSIFIER_VERSION
from label_neural_extractor import extract_with_paddleocr
from label_text_extractor import extract_with_tesseract
from mercadona_label_evidence import collect_label_images, nutrition_image_candidates
from mercadona_label_pipeline import download_label_image
from mercadona_nutrition_importer import import_from_label_file, IMPORTER_VERSION
from mercadona_weekly_catalog_adapter import (
    ADAPTER_VERSION as WEEKLY_ADAPTER_VERSION,
    deterministic_candidate_ids,
    fetch_product,
    fetch_product_ids,
    stratified_sample,
)
from nutrition_resolver import ProductIdentity, resolve
from openfoodfacts_adapter import fetch_product as off_fetch, to_candidate as off_candidate, ADAPTER_VERSION as OFF_ADAPTER_VERSION

PILOT_VERSION = "1.0.0"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _tesseract(psm: int):
    return lambda path: extract_with_tesseract(path, language="spa", psm=psm)


def _core_nutrition(candidate) -> dict[str, float] | None:
    if candidate is None:
        return None
    n = candidate.nutrition or {}
    keys = ("calories", "protein_g", "carbohydrate_g", "fat_g")
    if any(n.get(k) is None for k in keys):
        return None
    try:
        return {k: float(n[k]) for k in keys} | ({"fiber_g": float(n["fiber_g"])} if n.get("fiber_g") is not None else {})
    except (TypeError, ValueError):
        return None


def _source_page(product_id: str, payload: dict) -> str:
    value = payload.get("share_url")
    if isinstance(value, str) and value.startswith("http"):
        return value
    slug = payload.get("slug")
    if isinstance(slug, str) and slug:
        return f"https://tienda.mercadona.es/product/{product_id}/{slug}"
    return f"https://tienda.mercadona.es/product/{product_id}"


def _build_features(product, nutrition: dict[str, float] | None) -> ProductFeatures:
    n = nutrition or {}
    return ProductFeatures(
        name=product.name,
        legal_name=product.legal_name,
        ingredients=product.ingredients,
        family=product.family,
        subcategory=product.subcategory,
        calories=n.get("calories"),
        protein_g=n.get("protein_g"),
        carbohydrate_g=n.get("carbohydrate_g"),
        fat_g=n.get("fat_g"),
        fiber_g=n.get("fiber_g"),
    )


def main() -> int:
    sample_size = _env_int("PILOT_SIZE", 300)
    candidate_pool = _env_int("PILOT_CANDIDATE_POOL", max(sample_size * 2, 500))
    neural_budget = _env_int("PILOT_NEURAL_BUDGET", 60)
    per_category_cap = _env_int("PILOT_PER_CATEGORY_CAP", 18)
    neural_per_category_cap = _env_int("PILOT_NEURAL_PER_CATEGORY_CAP", 5)
    seed = os.environ.get("PILOT_SEED", "rumbo-mercadona-pilot-2026-08")
    off_delay = float(os.environ.get("PILOT_OFF_DELAY", "0.12"))

    out_dir = Path(os.environ.get("PILOT_OUTPUT_DIR", "pilot-large-output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = out_dir / "off-snapshots"
    snapshot_dir.mkdir(exist_ok=True)

    product_ids = fetch_product_ids()
    candidate_ids = deterministic_candidate_ids(product_ids, seed=seed, limit=candidate_pool)
    candidate_products = []
    acquisition_errors = []
    for product_id in candidate_ids:
        try:
            candidate_products.append(fetch_product(product_id))
        except Exception as exc:
            acquisition_errors.append({"product_id": product_id, "error": f"{type(exc).__name__}:{exc}"})
    sample = stratified_sample(candidate_products, size=sample_size, per_category_cap=per_category_cap)

    counts = Counter()
    source_counts = Counter()
    type_counts = Counter()
    review_reasons = Counter()
    category_stats: dict[str, Counter] = defaultdict(Counter)
    items = []
    neural_used = 0
    neural_by_category = Counter()

    strategies = (("psm6", _tesseract(6)), ("psm11", _tesseract(11)))

    for index, product in enumerate(sample, 1):
        row = {
            "product_id": product.product_id,
            "ean": product.ean,
            "name": product.name,
            "category": product.category_key,
            "status": "IDENTIFIED",
            "nutrition_source": None,
            "evidence_level": None,
            "review_reasons": [],
        }
        counts["IDENTIFIED"] += 1
        category_stats[product.category_key]["IDENTIFIED"] += 1

        # Type coverage is useful even before nutrition is available.
        type_assignment = classify_type(_build_features(product, None))
        if type_assignment is not None:
            row["culinary_type"] = type_assignment.value
            type_counts[type_assignment.value] += 1
            counts["TYPE_RECOGNIZED"] += 1
            category_stats[product.category_key]["TYPE_RECOGNIZED"] += 1
        else:
            row["culinary_type"] = None

        nutrition = None
        selected_candidate = None

        # 1) Exact-GTIN OFF lookup: reusable and cheap compared with OCR.
        if product.ean:
            try:
                fetched = off_fetch(product.ean, snapshot_dir=snapshot_dir, timeout=10.0)
                candidate = off_candidate(fetched)
                if candidate is not None:
                    resolved = resolve(ProductIdentity(
                        name=product.name, brand=product.brand, gtin=product.ean,
                        ingredients=product.ingredients,
                    ), [candidate])
                    if resolved.status == "RESOLVED" and resolved.selected is not None:
                        possible = _core_nutrition(resolved.selected)
                        if possible is not None:
                            nutrition = possible
                            selected_candidate = resolved.selected
                            row["nutrition_source"] = "Open Food Facts"
                            row["evidence_level"] = resolved.level
                            source_counts["Open Food Facts"] += 1
                time.sleep(off_delay)
            except Exception as exc:
                row.setdefault("source_errors", []).append(f"OFF:{type(exc).__name__}:{exc}")

        # 2) Mercadona pack label. Tesseract runs for every unresolved item with a back image.
        # Neural OCR is budgeted and stratified; unattempted neural fallbacks are reported explicitly.
        if nutrition is None and product.photos:
            evidence = collect_label_images(
                retailer_sku=product.product_id,
                product_name=product.name,
                images=product.photos,
                source_page=_source_page(product.product_id, product.payload),
                observed_at=product.observed_at,
            )
            candidates = nutrition_image_candidates(evidence)
            back = next((x for x in candidates if str(x.perspective) == "9"), candidates[0] if candidates else None)
            if back is not None:
                counts["LABEL_ATTEMPTED"] += 1
                category_stats[product.category_key]["LABEL_ATTEMPTED"] += 1
                allow_neural = neural_used < neural_budget and neural_by_category[product.category_key] < neural_per_category_cap
                with tempfile.TemporaryDirectory(prefix="rumbo-pilot-label-") as td:
                    image_path = Path(td) / "label.jpg"
                    try:
                        download_label_image(back.image_url, image_path, timeout=10.0)
                        result = import_from_label_file(
                            back, image_path,
                            gtin=product.ean, brand=product.brand,
                            tesseract_strategies=strategies,
                            neural_extractor=extract_with_paddleocr if allow_neural else None,
                            work_dir=Path(td) / "work",
                        )
                        if allow_neural and any(a.stage == "NEURAL_VISUAL_REGION" for a in result.attempts):
                            neural_used += 1
                            neural_by_category[product.category_key] += 1
                            counts["NEURAL_ATTEMPTED"] += 1
                            category_stats[product.category_key]["NEURAL_ATTEMPTED"] += 1
                        if result.candidate is not None:
                            possible = _core_nutrition(result.candidate)
                            if possible is not None:
                                nutrition = possible
                                selected_candidate = result.candidate
                                row["nutrition_source"] = result.candidate.source
                                row["evidence_level"] = "DECLARED"
                                source_counts[result.candidate.source] += 1
                        else:
                            row["label_status"] = result.status
                            row["label_reason"] = result.reason
                            row["label_attempts"] = [a.__dict__ for a in result.attempts]
                            if not allow_neural:
                                counts["NEURAL_NOT_ATTEMPTED_BUDGET"] += 1
                                category_stats[product.category_key]["NEURAL_NOT_ATTEMPTED_BUDGET"] += 1
                    except Exception as exc:
                        row.setdefault("source_errors", []).append(f"LABEL:{type(exc).__name__}:{exc}")

        if nutrition is not None:
            counts["NUTRITIONALLY_USABLE"] += 1
            category_stats[product.category_key]["NUTRITIONALLY_USABLE"] += 1
            row["nutrition"] = nutrition
            result = classify(_build_features(product, nutrition))
            row["classified"] = result.classified
            row["review_reasons"] = list(result.review_reasons)
            row["nutritional_roles"] = sorted(a.value for a in result.nutritional_roles)
            row["culinary_roles"] = sorted(a.value for a in result.culinary_roles)
            if result.classified:
                counts["CLASSIFIED"] += 1
                category_stats[product.category_key]["CLASSIFIED"] += 1
                counts["MENU_ELIGIBLE"] += 1
                category_stats[product.category_key]["MENU_ELIGIBLE"] += 1
                row["status"] = "MENU_ELIGIBLE"
            else:
                row["status"] = "REVIEW"
                for reason in result.review_reasons:
                    review_reasons[reason] += 1
                    category_stats[product.category_key][f"REVIEW:{reason}"] += 1
        else:
            row["classified"] = False
            row["status"] = "NUTRITION_MISSING"
            review_reasons["NUTRITION_MISSING"] += 1
            category_stats[product.category_key]["NUTRITION_MISSING"] += 1

        items.append(row)
        if index % 25 == 0:
            print(f"processed={index}/{len(sample)} nutrition={counts['NUTRITIONALLY_USABLE']} classified={counts['CLASSIFIED']} neural={neural_used}", flush=True)

    def rate(key: str) -> float:
        return round(counts[key] / len(sample), 4) if sample else 0.0

    category_report = {}
    for category, stats in sorted(category_stats.items()):
        identified = stats["IDENTIFIED"]
        category_report[category] = {
            **dict(stats),
            "nutrition_rate": round(stats["NUTRITIONALLY_USABLE"] / identified, 4) if identified else 0.0,
            "classified_rate": round(stats["CLASSIFIED"] / identified, 4) if identified else 0.0,
        }

    report = {
        "pilot_version": PILOT_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "weekly_adapter_version": WEEKLY_ADAPTER_VERSION,
        "off_adapter_version": OFF_ADAPTER_VERSION,
        "label_importer_version": IMPORTER_VERSION,
        "source_snapshot": "manurruis/mercadona-catalog weekly Hugging Face export",
        "sampling": {
            "seed": seed,
            "product_index_count": len(product_ids),
            "candidate_pool_requested": candidate_pool,
            "candidate_products_fetched": len(candidate_products),
            "sample_requested": sample_size,
            "sample_actual": len(sample),
            "categories_in_sample": len(category_stats),
            "per_category_cap": per_category_cap,
        },
        "neural_budget": {
            "global_cap": neural_budget,
            "per_category_cap": neural_per_category_cap,
            "actually_attempted": counts["NEURAL_ATTEMPTED"],
            "not_attempted_due_to_budget_or_category_cap": counts["NEURAL_NOT_ATTEMPTED_BUDGET"],
        },
        "counts": dict(counts),
        "rates": {
            "identified": rate("IDENTIFIED"),
            "type_recognized": rate("TYPE_RECOGNIZED"),
            "nutritionally_usable": rate("NUTRITIONALLY_USABLE"),
            "classified": rate("CLASSIFIED"),
            "menu_eligible": rate("MENU_ELIGIBLE"),
        },
        "nutrition_sources": dict(source_counts.most_common()),
        "culinary_types": dict(type_counts.most_common()),
        "review_reasons": dict(review_reasons.most_common()),
        "categories": category_report,
        "acquisition_errors": acquisition_errors,
        "items": items,
    }
    (out_dir / "pilot-large-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: v for k, v in report.items() if k not in {"items", "categories", "acquisition_errors"}}
    summary["largest_missing_categories"] = sorted(
        ({"category": c, "missing": s.get("NUTRITION_MISSING", 0), "identified": s.get("IDENTIFIED", 0)}
         for c, s in category_stats.items()),
        key=lambda x: (-x["missing"], -x["identified"], x["category"]),
    )[:20]
    summary["acquisition_error_count"] = len(acquisition_errors)
    (out_dir / "pilot-large-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if len(sample) >= min(sample_size, 100) else 2


if __name__ == "__main__":
    raise SystemExit(main())
