from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import tempfile

from classifier import ProductFeatures, classify
from label_neural_extractor import extract_with_paddleocr
from label_text_extractor import extract_with_tesseract
from mercadona_label_evidence import collect_label_images, nutrition_image_candidates
from mercadona_label_pipeline import download_label_image
from mercadona_nutrition_importer import import_from_label_file
from mercadona_weekly_catalog_adapter import fetch_product

BASE = Path(__file__).resolve().parent
DEFAULT_BATCH = BASE / "fixtures" / "ocr_high_probability_batch.json"
DEFAULT_OUT = BASE / "ocr-priority-output"


def tess(psm: int):
    return lambda path: extract_with_tesseract(path, language="spa", psm=psm)


def core(nutrition):
    if not isinstance(nutrition, dict):
        return None
    keys = ("calories", "protein_g", "carbohydrate_g", "fat_g")
    if any(nutrition.get(k) is None for k in keys):
        return None
    return {k: float(nutrition[k]) for k in keys}


def main() -> int:
    batch_path = Path(os.environ.get("OCR_BATCH_FILE", str(DEFAULT_BATCH)))
    out = Path(os.environ.get("OCR_OUTPUT_DIR", str(DEFAULT_OUT)))
    out.mkdir(parents=True, exist_ok=True)
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    stats = Counter()
    rows = []
    strategies = (("psm6", tess(6)), ("psm11", tess(11)))

    for i, item in enumerate(batch, 1):
        product_id = item["product_id"]
        row = {"product_id": product_id, "selection_reason": item.get("reason")}
        try:
            p = fetch_product(product_id)
            row.update({"name": p.name, "ean": p.ean, "category": p.category_key})
            evidence = collect_label_images(
                retailer_sku=p.product_id, product_name=p.name, images=p.photos,
                source_page=p.payload.get("share_url"), observed_at=p.observed_at,
            )
            candidates = nutrition_image_candidates(evidence)
            back = next((x for x in candidates if str(x.perspective) == "9"), candidates[0] if candidates else None)
            if back is None:
                row["status"] = "NO_IMAGE"
                stats["NO_IMAGE"] += 1
                rows.append(row)
                continue
            with tempfile.TemporaryDirectory(prefix="rumbo-priority-ocr-") as td:
                image = Path(td) / "label.jpg"
                download_label_image(back.image_url, image, timeout=12.0)
                result = import_from_label_file(
                    back, image, gtin=p.ean, brand=p.brand,
                    tesseract_strategies=strategies,
                    neural_extractor=extract_with_paddleocr,
                    work_dir=Path(td) / "work",
                )
                row["status"] = result.status
                row["reason"] = result.reason
                row["attempts"] = [a.__dict__ for a in result.attempts]
                stats[result.status] += 1
                if result.candidate:
                    nutrition = core(result.candidate.nutrition)
                    row["nutrition"] = nutrition
                    row["nutrition_source"] = result.candidate.source
                    if nutrition:
                        features = ProductFeatures(
                            name=p.name, legal_name=p.legal_name, ingredients=p.ingredients,
                            family=p.family, subcategory=p.subcategory,
                            calories=nutrition["calories"], protein_g=nutrition["protein_g"],
                            carbohydrate_g=nutrition["carbohydrate_g"], fat_g=nutrition["fat_g"],
                        )
                        classified = classify(features)
                        row["classified"] = classified.classified
                        row["culinary_type"] = classified.culinary_type.value if classified.culinary_type else None
                        row["review_reasons"] = classified.review_reasons
                        stats["NUTRITION_RECOVERED"] += 1
                        if classified.classified:
                            stats["MENU_ELIGIBLE_FROM_BATCH"] += 1
        except Exception as exc:
            row["status"] = "ERROR"
            row["error"] = f"{type(exc).__name__}:{exc}"
            stats["ERROR"] += 1
        rows.append(row)
        print(f"processed={i}/{len(batch)} recovered={stats['NUTRITION_RECOVERED']}", flush=True)

    summary = {
        "batch_file": str(batch_path),
        "batch_size": len(batch),
        "stats": dict(stats),
        "recovery_rate": round(stats["NUTRITION_RECOVERED"] / len(batch), 4) if batch else 0,
        "menu_eligible_rate": round(stats["MENU_ELIGIBLE_FROM_BATCH"] / len(batch), 4) if batch else 0,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.json").write_text(json.dumps({**summary, "items": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
