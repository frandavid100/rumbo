from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
import time
from typing import Any

from label_neural_extractor import extract_with_paddleocr
from label_text_extractor import extract_with_tesseract
from mercadona_label_evidence import LabelImageEvidence
from mercadona_label_pipeline import download_label_image
from mercadona_nutrition_reader import OCR_EVIDENCE_LEVEL, VisionExtraction, read_evidence
from nutrition_ocr_ensemble import ENSEMBLE_VERSION, ParsedOCRReading, fuse_ocr_readings
from nutrition_visual_table_detector import detect_visual_table_regions

MAX_REGIONS_PER_PRODUCT = 2
OCR_ENGINES = ("paddleocr", "tesseract")


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _back_photo(row: dict[str, Any]) -> tuple[int, dict[str, Any]] | None:
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    for index, photo in enumerate(photos):
        if isinstance(photo, dict) and str(photo.get("perspective")) == "9" and photo.get("zoom"):
            return index, photo
    return None


def _eligible(row: dict[str, Any]) -> bool:
    # Structured ingredients are a strong first-party signal that this is a
    # packaged food/drink for which a nutrition panel is plausibly present.
    return bool(row.get("ingredients") and _back_photo(row))


def _reading(evidence: LabelImageEvidence, extracted):
    return read_evidence(evidence, VisionExtraction(
        text=extracted.text,
        confidence=extracted.confidence,
        engine=extracted.engine,
        engine_version=extracted.engine_version,
    ))


def _reading_payload(reading) -> dict[str, Any]:
    return {
        "status": reading.parsed.status,
        "confidence": reading.extraction.confidence,
        "basis": reading.parsed.basis,
        "nutrition": reading.parsed.nutrition,
        "reasons": list(reading.parsed.reasons),
        "engine": reading.extraction.engine,
        "engine_version": reading.extraction.engine_version,
        # Keep normalized OCR evidence for audit; never persist image bytes.
        "normalized_ocr_text": reading.parsed.normalized_text,
    }


def _ensemble_payload(ensemble) -> dict[str, Any]:
    return {
        "status": ensemble.status,
        "basis": ensemble.basis,
        "nutrition": ensemble.nutrition,
        "confidence": ensemble.confidence,
        "corroborated_fields": ensemble.corroborated_fields,
        "independent_engine_families": ensemble.independent_engine_families,
        "reasons": list(ensemble.reasons),
        "fields": [
            {
                "name": field.name,
                "value": field.value,
                "strategies": list(field.strategies),
                "engine_families": list(field.engine_families),
                "corroborated": field.corroborated,
            }
            for field in ensemble.fields
        ],
    }


def _extract_region(evidence: LabelImageEvidence, region_path: Path):
    readings = []
    engine_errors: dict[str, str] = {}
    for family, extractor in (
        ("paddleocr", extract_with_paddleocr),
        ("tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=6)),
    ):
        try:
            extracted = extractor(region_path)
            reading = _reading(evidence, extracted)
            readings.append((family, reading))
        except Exception as exc:
            engine_errors[family] = f"{type(exc).__name__}:{exc}"

    ensemble = fuse_ocr_readings(
        ParsedOCRReading(
            strategy=f"{family}:visual-region",
            result=reading.parsed,
            extraction_confidence=reading.extraction.confidence,
            engine_family=family,
        )
        for family, reading in readings
    )
    return readings, engine_errors, ensemble


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard-index", type=int, required=True)
    ap.add_argument("--shard-count", type=int, required=True)
    ap.add_argument("--limit", type=int, default=0, help="0 means all rows in this shard")
    ap.add_argument("--delay", type=float, default=0.15)
    args = ap.parse_args()

    all_rows = _load(Path(args.products))
    eligible = [row for row in all_rows if _eligible(row)]
    eligible.sort(key=lambda row: (len(str(row.get("product_id") or "")), str(row.get("product_id") or "")))
    selected = [row for i, row in enumerate(eligible) if i % args.shard_count == args.shard_index]
    if args.limit > 0:
        selected = selected[: args.limit]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()

    for product_index, row in enumerate(selected):
        if product_index and args.delay:
            time.sleep(args.delay)
        pid = str(row.get("product_id") or "")
        photo_hit = _back_photo(row)
        if not pid or photo_hit is None:
            continue
        image_index, photo = photo_hit
        image_url = str(photo["zoom"])
        evidence = LabelImageEvidence(
            retailer="Mercadona",
            retailer_sku=pid,
            product_name=str(row.get("name") or pid),
            image_url=image_url,
            image_index=image_index,
            observed_at=str(row.get("observed_at") or ""),
            source_page=row.get("share_url"),
            redistribution_allowed=False,
            purpose="PACK_LABEL_CANDIDATE",
            perspective=9,
        )
        item: dict[str, Any] = {
            "product_id": pid,
            "ean": row.get("ean"),
            "name": row.get("name"),
            "brand": row.get("brand"),
            "category_id": row.get("category_id"),
            "category_name": row.get("category_name"),
            "image_url": image_url,
            "image_index": image_index,
            "perspective": 9,
            "source": "MERCADONA_FIRST_PARTY",
            "source_record_kind": "label image",
            "evidence_level": OCR_EVIDENCE_LEVEL,
            "redistribution_allowed": False,
            "status": "UNRESOLVED",
            "attempts": [],
        }
        try:
            with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-neural-") as td:
                base = Path(td)
                image_path = base / f"{pid}.jpg"
                download_label_image(image_url, image_path, timeout=15.0)
                regions = detect_visual_table_regions(image_path, base / "regions")
                item["visual_regions_detected"] = len(regions)
                if not regions:
                    item["status"] = "NO_VISUAL_REGION"
                for region in regions[:MAX_REGIONS_PER_PRODUCT]:
                    readings, engine_errors, ensemble = _extract_region(evidence, region.path)
                    attempt = {
                        "region": {
                            "name": region.name,
                            "box": list(region.box),
                            "score": region.score,
                            "horizontal_lines": region.horizontal_lines,
                            "vertical_lines": region.vertical_lines,
                            "line_density": region.line_density,
                        },
                        "engines": {
                            family: _reading_payload(reading)
                            for family, reading in readings
                        },
                        "engine_errors": engine_errors,
                        "ensemble": _ensemble_payload(ensemble),
                    }
                    item["attempts"].append(attempt)
                    if ensemble.declared_usable:
                        item["status"] = "DECLARED"
                        item["basis"] = ensemble.basis
                        item["nutrition"] = ensemble.nutrition
                        item["claim"] = (
                            f"{OCR_EVIDENCE_LEVEL}; source=MERCADONA_FIRST_PARTY/label image; "
                            f"reader=ensemble-{ENSEMBLE_VERSION}; engines=paddleocr+tesseract; "
                            f"independent_engines={ensemble.independent_engine_families}; "
                            f"corroborated_fields={ensemble.corroborated_fields}; basis={ensemble.basis}"
                        )
                        break
                    if ensemble.nutrition is not None or ensemble.status == "REVIEW":
                        item["status"] = "REVIEW"
        except Exception as exc:
            item["status"] = "ERROR"
            item["error"] = f"{type(exc).__name__}:{exc}"
        status_counts[item["status"]] += 1
        results.append(item)

    result_path = out / f"results-{args.shard_index:02d}.jsonl"
    result_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results), encoding="utf-8")
    summary = {
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "evidence_level": OCR_EVIDENCE_LEVEL,
        "mode": "PADDLEOCR_TESSERACT_INDEPENDENT_ENSEMBLE_VISUAL_REGIONS_BACK_LABEL",
        "ocr_engines": list(OCR_ENGINES),
        "ensemble_version": ENSEMBLE_VERSION,
        "inventory_products": len(all_rows),
        "eligible_products": len(eligible),
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "selected": len(selected),
        "processed": len(results),
        "status_counts": dict(sorted(status_counts.items())),
        "declared_rate": round(status_counts["DECLARED"] / len(results), 4) if results else 0.0,
        "redistribution_allowed": False,
    }
    (out / f"summary-{args.shard_index:02d}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if results else 2


if __name__ == "__main__":
    raise SystemExit(main())
