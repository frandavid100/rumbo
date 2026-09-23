from __future__ import annotations

"""Strict production rescue for one deterministic Mercadona centre crop.

This path is deliberately narrower than the diagnostic preprocessing pilot. It
uses exactly the legacy ``crop_center`` transform, PP-OCRv6 and Tesseract PSM 11.
A product is DECLARED only when both independent OCR families individually pass
the normal Mercadona parser with a complete per-100 profile and those profiles
match exactly. No other preprocessing variant is inspected or ranked.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
from typing import Any

from label_image_preprocess import build_fallback_variants
from label_neural_extractor import extract_with_paddleocr
from label_text_extractor import extract_with_tesseract
from mercadona_label_evidence import LabelImageEvidence
from mercadona_label_pipeline import download_label_image
from mercadona_nutrition_reader import OCR_EVIDENCE_LEVEL, VisionExtraction, read_evidence
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings

CORE_FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")
RESCUE_VERSION = "1.0.0"


def _load_one(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 1:
        raise ValueError(f"expected exactly one target row, got {len(rows)}")
    return rows[0]


def _profile(parsed) -> tuple[str, tuple[float, float, float, float]] | None:
    if getattr(parsed, "status", None) != "DECLARED":
        return None
    basis = str(getattr(parsed, "basis", "") or "")
    nutrition = getattr(parsed, "nutrition", None)
    if basis not in {"100_g", "100_ml"} or not isinstance(nutrition, dict):
        return None
    try:
        values = tuple(float(nutrition[field]) for field in CORE_FIELDS)
    except (KeyError, TypeError, ValueError):
        return None
    return basis, values


def _profiles_exactly_match(left, right) -> bool:
    """Require two complete, independently DECLARED profiles to match exactly."""
    a = _profile(left)
    b = _profile(right)
    return a is not None and b is not None and a == b


def _reading_payload(reading) -> dict[str, Any]:
    return {
        "status": reading.parsed.status,
        "confidence": reading.extraction.confidence,
        "basis": reading.parsed.basis,
        "nutrition": reading.parsed.nutrition,
        "reasons": list(reading.parsed.reasons),
        "engine": reading.extraction.engine,
        "engine_version": reading.extraction.engine_version,
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


def _read(evidence: LabelImageEvidence, extraction):
    return read_evidence(evidence, VisionExtraction(
        text=extraction.text,
        confidence=extraction.confidence,
        engine=extraction.engine,
        engine_version=extraction.engine_version,
    ))


def rescue(row: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    pid = str(row.get("product_id") or "")
    if not pid:
        raise ValueError("target product_id is missing")
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    p9 = [p for p in photos if isinstance(p, dict) and str(p.get("perspective")) == "9" and (p.get("zoom") or p.get("regular"))]
    if len(p9) != 1:
        raise ValueError(f"expected exactly one current perspective=9 image, got {len(p9)}")
    photo = p9[0]
    image_url = str(photo.get("zoom") or photo.get("regular"))
    image_index = photos.index(photo)

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
        "status": "REVIEW",
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
        "rescue_version": RESCUE_VERSION,
        "attempts": [],
    }

    with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-center-crop-") as td:
        base = Path(td)
        source = base / f"{pid}.jpg"
        download_label_image(image_url, source, timeout=15.0)
        variants = build_fallback_variants(source, base / "variants")
        centers = [variant for variant in variants if variant.name == "crop_center"]
        if len(centers) != 1:
            raise RuntimeError(f"expected exactly one deterministic crop_center, got {len(centers)}")
        center = centers[0]

        errors: dict[str, str] = {}
        readings: list[tuple[str, str, Any]] = []
        specs = (
            ("paddleocr-center", "paddleocr", extract_with_paddleocr),
            ("tesseract-psm11-center", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=11)),
        )
        for strategy, family, extractor in specs:
            try:
                extraction = extractor(center.path)
                readings.append((strategy, family, _read(evidence, extraction)))
            except Exception as exc:
                errors[strategy] = f"{type(exc).__name__}:{exc}"

        parsed_readings = tuple(
            ParsedOCRReading(
                strategy=strategy,
                result=reading.parsed,
                extraction_confidence=reading.extraction.confidence,
                engine_family=family,
            )
            for strategy, family, reading in readings
        )
        ensemble = fuse_ocr_readings(parsed_readings)
        exact_independent_match = (
            len(readings) == 2
            and _profiles_exactly_match(readings[0][2].parsed, readings[1][2].parsed)
        )

        item["attempts"].append({
            "target_kind": "deterministic_center_crop",
            "preprocess_variant": "crop_center",
            "variant_selection_policy": "FIXED_SINGLE_VARIANT_NO_RANKING",
            "engines": {
                strategy: _reading_payload(reading)
                for strategy, _family, reading in readings
            },
            "engine_errors": errors,
            "exact_independent_profile_match": exact_independent_match,
            "ensemble": _ensemble_payload(ensemble),
        })

        if (
            exact_independent_match
            and ensemble.declared_usable
            and ensemble.independent_engine_families >= 2
            and ensemble.corroborated_fields >= 4
            and ensemble.nutrition is not None
            and all(ensemble.nutrition.get(field) is not None for field in CORE_FIELDS)
        ):
            item["status"] = "DECLARED"
            item["basis"] = ensemble.basis
            item["nutrition"] = ensemble.nutrition
            item["claim"] = (
                f"{OCR_EVIDENCE_LEVEL}; source=MERCADONA_FIRST_PARTY/label image; "
                f"reader=center-crop-rescue-{RESCUE_VERSION}; target=deterministic_center_crop; "
                "strategies=paddleocr-center+tesseract-psm11-center; "
                f"independent_engines={ensemble.independent_engine_families}; "
                f"corroborated_fields={ensemble.corroborated_fields}; basis={ensemble.basis}"
            )
        elif ensemble.nutrition is not None:
            item["nutrition"] = ensemble.nutrition
            item["basis"] = ensemble.basis

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results-00.jsonl").write_text(
        json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    counts = Counter([item["status"]])
    summary = {
        "selected": 1,
        "processed": 1,
        "status_counts": dict(counts),
        "rescue_version": RESCUE_VERSION,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": OCR_EVIDENCE_LEVEL,
        "redistribution_allowed": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    (out_dir / "summary-00.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return item


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    item = rescue(_load_one(args.product), args.out)
    print(json.dumps({
        "product_id": item["product_id"],
        "status": item["status"],
        "nutrition": item.get("nutrition"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
