from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import tempfile

from label_text_extractor import extract_with_tesseract
from mercadona_label_evidence import collect_label_images, nutrition_image_candidates
from mercadona_label_pipeline import download_label_image, process_label_file_ensemble
from mercadona_weekly_catalog_adapter import fetch_product
from nutrition_visual_table_detector import detect_visual_table_regions

BATCH = Path(__file__).resolve().parent / "fixtures" / "tesseract_screen_batch.json"
OUT = Path(__file__).resolve().parent / "tesseract-screen-output"


def tess(psm: int):
    return lambda path: extract_with_tesseract(path, language="spa", psm=psm)


def missing_count(reason: str | None) -> int:
    if not reason or "MISSING_CORE:" not in reason:
        return 0
    tail = reason.split("MISSING_CORE:", 1)[1]
    return sum(field in tail for field in ("calories", "fat_g", "carbohydrate_g", "protein_g"))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    batch = json.loads(BATCH.read_text(encoding="utf-8"))
    strategies = (("psm6", tess(6)), ("psm11", tess(11)))
    stats = Counter()
    rows = []

    for index, item in enumerate(batch, 1):
        product_id = item["product_id"]
        row = {"product_id": product_id}
        best_missing = 99
        best_status = "UNREADABLE"
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
                row["screen_bucket"] = "NO_IMAGE"
                stats["NO_IMAGE"] += 1
                rows.append(row)
                continue

            with tempfile.TemporaryDirectory(prefix="rumbo-tess-screen-") as td:
                image = Path(td) / "label.jpg"
                download_label_image(back.image_url, image, timeout=10.0)
                attempts = []

                original = process_label_file_ensemble(
                    back, image, gtin=p.ean, brand=p.brand, strategies=strategies,
                )
                attempts.append({"scope":"original","status":original.status,"reason":original.reason})
                if original.candidate is not None:
                    row["screen_bucket"] = "TESSERACT_DECLARED"
                    row["nutrition"] = original.candidate.nutrition
                    stats["TESSERACT_DECLARED"] += 1
                    row["attempts"] = attempts
                    rows.append(row)
                    print(f"screen={index}/{len(batch)} direct={stats['TESSERACT_DECLARED']}", flush=True)
                    continue
                if original.status == "REVIEW":
                    best_status = "REVIEW"
                    best_missing = min(best_missing, missing_count(original.reason))

                regions = detect_visual_table_regions(image, Path(td) / "regions")
                for region in regions[:3]:
                    result = process_label_file_ensemble(
                        back, region.path, gtin=p.ean, brand=p.brand, strategies=strategies,
                    )
                    attempts.append({"scope":region.name,"status":result.status,"reason":result.reason})
                    if result.candidate is not None:
                        row["screen_bucket"] = "TESSERACT_DECLARED"
                        row["nutrition"] = result.candidate.nutrition
                        stats["TESSERACT_DECLARED"] += 1
                        break
                    if result.status == "REVIEW":
                        best_status = "REVIEW"
                        best_missing = min(best_missing, missing_count(result.reason))

                if "screen_bucket" not in row:
                    if best_status == "REVIEW" and best_missing <= 1:
                        row["screen_bucket"] = "NEURAL_HIGH_PRIORITY"
                        stats["NEURAL_HIGH_PRIORITY"] += 1
                    elif best_status == "REVIEW" and best_missing == 2:
                        row["screen_bucket"] = "NEURAL_MEDIUM_PRIORITY"
                        stats["NEURAL_MEDIUM_PRIORITY"] += 1
                    elif best_status == "REVIEW":
                        row["screen_bucket"] = "NEURAL_LOW_PRIORITY"
                        stats["NEURAL_LOW_PRIORITY"] += 1
                    else:
                        row["screen_bucket"] = "UNREADABLE_LOW_PRIORITY"
                        stats["UNREADABLE_LOW_PRIORITY"] += 1
                row["best_missing_core_count"] = None if best_missing == 99 else best_missing
                row["attempts"] = attempts
        except Exception as exc:
            row["screen_bucket"] = "ERROR"
            row["error"] = f"{type(exc).__name__}:{exc}"
            stats["ERROR"] += 1
        rows.append(row)
        print(f"screen={index}/{len(batch)} high={stats['NEURAL_HIGH_PRIORITY']} direct={stats['TESSERACT_DECLARED']}", flush=True)

    priority = sorted(
        rows,
        key=lambda r: ({"TESSERACT_DECLARED":0,"NEURAL_HIGH_PRIORITY":1,"NEURAL_MEDIUM_PRIORITY":2,"NEURAL_LOW_PRIORITY":3,"UNREADABLE_LOW_PRIORITY":4,"NO_IMAGE":5,"ERROR":6}.get(r.get("screen_bucket"), 9), r.get("product_id",""))
    )
    summary = {
        "batch_size": len(batch),
        "stats": dict(stats),
        "neural_high_priority_rate": round(stats["NEURAL_HIGH_PRIORITY"] / len(batch), 4) if batch else 0,
        "tesseract_declared_rate": round(stats["TESSERACT_DECLARED"] / len(batch), 4) if batch else 0,
        "priority_queue": [{"product_id":r.get("product_id"),"name":r.get("name"),"screen_bucket":r.get("screen_bucket"),"best_missing_core_count":r.get("best_missing_core_count")} for r in priority],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "report.json").write_text(json.dumps({**summary, "items": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
