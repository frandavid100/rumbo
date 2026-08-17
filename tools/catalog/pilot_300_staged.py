from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from classifier import classify, classify_type, CLASSIFIER_VERSION
from label_neural_extractor import extract_with_paddleocr
from label_text_extractor import extract_with_tesseract
from mercadona_label_evidence import collect_label_images, nutrition_image_candidates
from mercadona_label_pipeline import download_label_image
from mercadona_nutrition_importer import import_from_label_file
from mercadona_weekly_catalog_adapter import deterministic_candidate_ids, fetch_product_ids, stratified_sample
from nutrition_resolver import ProductIdentity, resolve
from openfoodfacts_adapter import fetch_product as off_fetch, to_candidate as off_candidate
from pilot_large_catalog import _build_features, _core_nutrition_values, _fetch_candidate_products, _is_food_category, _source_page

PILOT_VERSION = "staged-1.0.0"


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def tesseract(psm: int):
    return lambda path: extract_with_tesseract(path, language="spa", psm=psm)


def deterministic_unresolved_sample(items, size: int, seed: str):
    by_category = defaultdict(list)
    for row in items:
        by_category[row["category"]].append(row)
    for category, rows in by_category.items():
        rows.sort(key=lambda r: hashlib.sha256(f"{seed}:{r['product_id']}".encode()).hexdigest())
    categories = sorted(by_category)
    selected = []
    index = 0
    while len(selected) < size:
        progressed = False
        for category in categories:
            rows = by_category[category]
            if index < len(rows):
                selected.append(rows[index])
                progressed = True
                if len(selected) == size:
                    break
        if not progressed:
            break
        index += 1
    return selected


def main() -> int:
    sample_size = env_int("PILOT_SIZE", 300)
    candidate_pool = env_int("PILOT_CANDIDATE_POOL", 900)
    workers = env_int("PILOT_ACQUISITION_WORKERS", 16)
    label_sample_size = env_int("PILOT_LABEL_SAMPLE", 30)
    seed = os.environ.get("PILOT_SEED", "rumbo-mercadona-pilot-2026-08")
    out = Path(os.environ.get("PILOT_OUTPUT_DIR", "pilot-300-staged-output"))
    out.mkdir(parents=True, exist_ok=True)
    off_snapshots = out / "off-snapshots"
    off_snapshots.mkdir(exist_ok=True)

    ids = fetch_product_ids()
    candidate_ids = deterministic_candidate_ids(ids, seed=seed, limit=candidate_pool)
    products, acquisition_errors = _fetch_candidate_products(candidate_ids, workers)
    food = [p for p in products if _is_food_category(p.category_key)]
    sample = stratified_sample(food, size=sample_size, per_category_cap=24)

    product_by_id = {p.product_id: p for p in sample}
    rows = []
    counts = Counter()
    category_counts = defaultdict(Counter)
    type_counts = Counter()
    sources = Counter()

    # Stage A: all 300 identities + type recognition + exact-GTIN OFF.
    for index, p in enumerate(sample, 1):
        row = {"product_id": p.product_id, "ean": p.ean, "name": p.name,
               "category": p.category_key, "nutrition": None, "nutrition_source": None,
               "status": "IDENTIFIED", "review_reasons": []}
        counts["IDENTIFIED"] += 1
        category_counts[p.category_key]["IDENTIFIED"] += 1
        type_assignment = classify_type(_build_features(p, None))
        row["culinary_type"] = type_assignment.value if type_assignment else None
        if type_assignment:
            counts["TYPE_RECOGNIZED"] += 1
            category_counts[p.category_key]["TYPE_RECOGNIZED"] += 1
            type_counts[type_assignment.value] += 1

        if p.ean:
            try:
                fetched = off_fetch(p.ean, snapshot_dir=off_snapshots, timeout=8.0)
                candidate = off_candidate(fetched)
                if candidate:
                    resolution = resolve(ProductIdentity(name=p.name, brand=p.brand, gtin=p.ean,
                                                        ingredients=p.ingredients), [candidate])
                    if resolution.status == "RESOLVED":
                        nutrition = _core_nutrition_values(resolution.nutrition)
                        if nutrition:
                            row["nutrition"] = nutrition
                            row["nutrition_source"] = "Open Food Facts"
                            row["evidence_level"] = resolution.level
                            sources["Open Food Facts"] += 1
            except Exception as exc:
                row.setdefault("source_errors", []).append(f"OFF:{type(exc).__name__}:{exc}")
        rows.append(row)
        if index % 50 == 0:
            print(f"stageA={index}/{len(sample)}", flush=True)

    unresolved = [r for r in rows if r["nutrition"] is None]
    label_sample = deterministic_unresolved_sample(unresolved, min(label_sample_size, len(unresolved)), seed + ":labels")
    label_ids = {r["product_id"] for r in label_sample}

    # Stage B: a registered stratified sample of unresolved products gets full label OCR.
    strategies = (("psm6", tesseract(6)), ("psm11", tesseract(11)))
    label_stats = Counter()
    label_categories = Counter()
    for index, row in enumerate(label_sample, 1):
        p = product_by_id[row["product_id"]]
        label_stats["SELECTED"] += 1
        label_categories[p.category_key] += 1
        evidence = collect_label_images(retailer_sku=p.product_id, product_name=p.name,
                                        images=p.photos, source_page=_source_page(p.product_id, p.payload),
                                        observed_at=p.observed_at)
        candidates = nutrition_image_candidates(evidence)
        back = next((x for x in candidates if str(x.perspective) == "9"), candidates[0] if candidates else None)
        if back is None:
            row["label_status"] = "NO_IMAGE"
            label_stats["NO_IMAGE"] += 1
            continue
        try:
            with tempfile.TemporaryDirectory(prefix="rumbo-stage-label-") as td:
                image = Path(td) / "label.jpg"
                download_label_image(back.image_url, image, timeout=10.0)
                result = import_from_label_file(back, image, gtin=p.ean, brand=p.brand,
                                                tesseract_strategies=strategies,
                                                neural_extractor=extract_with_paddleocr,
                                                work_dir=Path(td) / "work")
                row["label_status"] = result.status
                row["label_attempts"] = [a.__dict__ for a in result.attempts]
                label_stats[result.status] += 1
                if result.candidate:
                    nutrition = _core_nutrition_values(result.candidate.nutrition)
                    if nutrition:
                        row["nutrition"] = nutrition
                        row["nutrition_source"] = result.candidate.source
                        row["evidence_level"] = "DECLARED"
                        sources[result.candidate.source] += 1
                        label_stats["NUTRITION_RECOVERED"] += 1
        except Exception as exc:
            row["label_status"] = "ERROR"
            row.setdefault("source_errors", []).append(f"LABEL:{type(exc).__name__}:{exc}")
            label_stats["ERROR"] += 1
        print(f"stageB={index}/{len(label_sample)} recovered={label_stats['NUTRITION_RECOVERED']}", flush=True)

    # Stage C: classification across every product whose nutrition was actually resolved.
    review_reasons = Counter()
    for row in rows:
        p = product_by_id[row["product_id"]]
        if row["nutrition"] is None:
            row["status"] = "NUTRITION_MISSING"
            row["label_sampled"] = row["product_id"] in label_ids
            continue
        counts["NUTRITIONALLY_USABLE"] += 1
        category_counts[p.category_key]["NUTRITIONALLY_USABLE"] += 1
        result = classify(_build_features(p, row["nutrition"]))
        row["nutritional_roles"] = sorted(x.value for x in result.nutritional_roles)
        row["culinary_roles"] = sorted(x.value for x in result.culinary_roles)
        row["review_reasons"] = list(result.review_reasons)
        row["classified"] = result.classified
        if result.classified:
            counts["CLASSIFIED"] += 1
            counts["MENU_ELIGIBLE"] += 1
            category_counts[p.category_key]["CLASSIFIED"] += 1
            category_counts[p.category_key]["MENU_ELIGIBLE"] += 1
            row["status"] = "MENU_ELIGIBLE"
        else:
            row["status"] = "REVIEW"
            for reason in result.review_reasons:
                review_reasons[reason] += 1

    def rate(key):
        return round(counts[key] / len(sample), 4) if sample else 0

    off_resolved = sum(1 for r in rows if r["nutrition_source"] == "Open Food Facts")
    label_recovered = label_stats["NUTRITION_RECOVERED"]
    summary = {
        "pilot_version": PILOT_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "sampling": {"index_size": len(ids), "candidate_pool": candidate_pool,
                     "candidate_products_fetched": len(products), "food_candidates": len(food),
                     "sample_actual": len(sample), "categories": len({p.category_key for p in sample}),
                     "seed": seed},
        "counts": dict(counts),
        "rates_observed_lower_bound": {"identified": rate("IDENTIFIED"),
                                        "type_recognized": rate("TYPE_RECOGNIZED"),
                                        "nutritionally_usable": rate("NUTRITIONALLY_USABLE"),
                                        "classified": rate("CLASSIFIED"),
                                        "menu_eligible": rate("MENU_ELIGIBLE")},
        "off": {"resolved": off_resolved, "rate": round(off_resolved / len(sample), 4) if sample else 0},
        "label_sample": {"requested": label_sample_size, "actual": len(label_sample),
                         "stats": dict(label_stats), "categories": dict(label_categories),
                         "recovery_rate_within_sample": round(label_recovered / len(label_sample), 4) if label_sample else 0,
                         "note": "Not extrapolated to unsampled unresolved products"},
        "nutrition_sources": dict(sources),
        "review_reasons_on_nutrition_resolved": dict(review_reasons),
        "culinary_types": dict(type_counts),
        "acquisition_error_count": len(acquisition_errors),
    }
    category_summary = {}
    for category, stats in category_counts.items():
        n = stats["IDENTIFIED"]
        category_summary[category] = {**dict(stats),
                                     "type_rate": round(stats["TYPE_RECOGNIZED"] / n, 3) if n else 0,
                                     "nutrition_observed_rate": round(stats["NUTRITIONALLY_USABLE"] / n, 3) if n else 0}
    report = {**summary, "categories": category_summary, "acquisition_errors": acquisition_errors, "items": rows}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if len(sample) >= 250 else 2


if __name__ == "__main__":
    raise SystemExit(main())
