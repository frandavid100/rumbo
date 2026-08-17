from __future__ import annotations

import json
from pathlib import Path
import tempfile

from label_neural_extractor import extract_with_paddleocr
from mercadona_label_evidence import nutrition_image_candidates
from mercadona_label_pipeline import download_label_image
from mercadona_nutrition_reader import VisionExtraction, read_evidence, to_candidate
from mercadona_product_adapter import fetch_product
from nutrition_visual_table_detector import detect_visual_table_regions

PRODUCTS = [
    ("23049", "Batido de chocolate Hacendado"),
    ("3363", "Zumo de naranja recién exprimido Hacendado"),
    ("60127", "Media tortilla de patata con cebolla Listo para Comer"),
    ("14325", "Galletas tostadas Hacendado"),
    ("18018", "Atún claro al natural Hacendado"),
]


def parse_extraction(evidence, extraction, product):
    reading = read_evidence(evidence, VisionExtraction(
        text=extraction.text,
        confidence=extraction.confidence,
        engine=extraction.engine,
        engine_version=extraction.engine_version,
    ))
    candidate = to_candidate(reading, gtin=product.ean, brand=product.brand)
    return reading, candidate


def reading_payload(reading):
    return {
        "status": reading.parsed.status,
        "confidence": reading.extraction.confidence,
        "basis": reading.parsed.basis,
        "nutrition": reading.parsed.nutrition,
        "reasons": list(reading.parsed.reasons),
        "engine": reading.extraction.engine,
        "engine_version": reading.extraction.engine_version,
        "text": reading.extraction.text,
    }


def main() -> int:
    report = {
        "reader": "PP-OCRv6",
        "products_requested": len(PRODUCTS),
        "api_fetched": 0,
        "visual_regions": 0,
        "declared_full_image": 0,
        "declared_visual_region": 0,
        "items": [],
    }
    snapshot_dir = Path("live-neural-snapshots")
    snapshot_dir.mkdir(exist_ok=True)

    for product_id, expected_name in PRODUCTS:
        item = {
            "product_id": product_id,
            "expected_name": expected_name,
            "api_status": "ERROR",
            "ean": None,
            "name": None,
            "status": "UNRESOLVED",
            "attempts": [],
            "visual_regions": [],
        }
        try:
            product = fetch_product(product_id, snapshot_dir=snapshot_dir, timeout=10.0)
            report["api_fetched"] += 1
            item.update(api_status="OK", ean=product.ean, name=product.name)
            back_images = [x for x in nutrition_image_candidates(product.label_images) if x.perspective == 9]
            if not back_images:
                item["reason"] = "NO_BACK_IMAGE"
                report["items"].append(item)
                continue

            evidence = back_images[0]
            with tempfile.TemporaryDirectory(prefix="rumbo-neural-label-") as td:
                image_path = Path(td) / f"{product_id}.jpg"
                download_label_image(evidence.image_url, image_path, timeout=12.0)

                full = extract_with_paddleocr(image_path)
                full_reading, full_candidate = parse_extraction(evidence, full, product)
                item["attempts"].append({"variant": "full_image", **reading_payload(full_reading)})
                if full_candidate is not None:
                    item["status"] = "DECLARED"
                    item["via"] = "full_image"
                    item["nutrition"] = full_candidate.nutrition
                    report["declared_full_image"] += 1
                    report["items"].append(item)
                    continue

                region_dir = Path(td) / "visual-regions"
                regions = detect_visual_table_regions(image_path, region_dir)
                report["visual_regions"] += len(regions)
                for region in regions:
                    meta = {
                        "name": region.name,
                        "box": list(region.box),
                        "score": region.score,
                        "horizontal_lines": region.horizontal_lines,
                        "vertical_lines": region.vertical_lines,
                        "line_density": region.line_density,
                    }
                    item["visual_regions"].append(meta)
                    extracted = extract_with_paddleocr(region.path)
                    reading, candidate = parse_extraction(evidence, extracted, product)
                    item["attempts"].append({"variant": region.name, "region": meta, **reading_payload(reading)})
                    if candidate is not None:
                        item["status"] = "DECLARED"
                        item["via"] = "visual_region"
                        item["nutrition"] = candidate.nutrition
                        report["declared_visual_region"] += 1
                        break
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}:{exc}"
        report["items"].append(item)

    report["declared_total"] = report["declared_full_image"] + report["declared_visual_region"]
    report["declared_rate"] = round(report["declared_total"] / len(PRODUCTS), 3)
    Path("live-neural-ocr-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
