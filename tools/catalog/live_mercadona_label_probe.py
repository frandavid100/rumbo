from __future__ import annotations

import json
from pathlib import Path

from label_text_extractor import extract_with_tesseract
from mercadona_label_pipeline import process_label_image
from mercadona_product_adapter import fetch_product

PRODUCTS = [
    ("14325", "Galletas tostadas Hacendado"),
    ("23773", "Chocolate negro 72% de cacao Hacendado"),
    ("23049", "Batido de chocolate Hacendado"),
    ("21713", "Refresco cola Hacendado"),
    ("3363", "Zumo de naranja recién exprimido Hacendado"),
    ("80862", "Hummus de garbanzos Hacendado con pimiento del piquillo asado"),
    ("13985", "Masa fresca pizza Hacendado"),
    ("22549", "Pizza Calzone con jamón cocido y queso Hacendado"),
    ("60127", "Media tortilla de patata con cebolla Listo para Comer"),
    ("18018", "Atún claro al natural Hacendado"),
    ("88407", "Lentejas Listo para Comer"),
    ("26108", "Fabada Hacendado"),
    ("23138", "Albóndigas en salsa Hacendado"),
]


def extractor_for(psm: int):
    return lambda path: extract_with_tesseract(path, language="spa", psm=psm)


def main() -> int:
    report = {
        "products_requested": len(PRODUCTS),
        "api_fetched": 0,
        "with_photos": 0,
        "declared": 0,
        "review_only": 0,
        "unreadable": 0,
        "items": [],
    }
    snapshot_dir = Path("live-mercadona-snapshots")
    snapshot_dir.mkdir(exist_ok=True)

    for product_id, expected_name in PRODUCTS:
        item = {
            "product_id": product_id,
            "expected_name": expected_name,
            "api_status": "ERROR",
            "ean": None,
            "name": None,
            "photo_count": 0,
            "status": "UNREADABLE",
            "declared": None,
            "attempts": [],
        }
        try:
            product = fetch_product(product_id, snapshot_dir=snapshot_dir)
            report["api_fetched"] += 1
            item["api_status"] = "OK"
            item["ean"] = product.ean
            item["name"] = product.name
            item["photo_count"] = len(product.label_images)
            if product.label_images:
                report["with_photos"] += 1

            best_review = None
            for evidence in product.label_images:
                for psm in (6, 11):
                    result = process_label_image(
                        evidence,
                        gtin=product.ean,
                        brand=product.brand,
                        extractor=extractor_for(psm),
                    )
                    attempt = {
                        "image_index": evidence.image_index,
                        "psm": psm,
                        "status": result.status,
                        "reason": result.reason,
                        "confidence": (result.reading.extraction.confidence if result.reading else None),
                    }
                    item["attempts"].append(attempt)
                    if result.status == "DECLARED" and result.candidate is not None:
                        item["status"] = "DECLARED"
                        item["declared"] = {
                            "image_index": evidence.image_index,
                            "psm": psm,
                            "basis": result.reading.parsed.basis,
                            "confidence": result.reading.extraction.confidence,
                            "nutrition": result.candidate.nutrition,
                            "source_record_id": result.candidate.source_record_id,
                        }
                        break
                    if result.status == "REVIEW" and result.reading is not None:
                        confidence = result.reading.extraction.confidence
                        if best_review is None or confidence > best_review[0]:
                            best_review = (confidence, attempt, result.reading.parsed.nutrition)
                if item["status"] == "DECLARED":
                    break

            if item["status"] == "DECLARED":
                report["declared"] += 1
            elif best_review is not None:
                item["status"] = "REVIEW"
                item["best_review"] = {
                    "confidence": best_review[0],
                    "attempt": best_review[1],
                    "nutrition": best_review[2],
                }
                report["review_only"] += 1
            else:
                report["unreadable"] += 1
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}:{exc}"
            report["unreadable"] += 1
        report["items"].append(item)

    report["declared_rate"] = round(report["declared"] / len(PRODUCTS), 3)
    Path("live-mercadona-label-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # Network/source failures are measured, not treated as a unit-test failure.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
