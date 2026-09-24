from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any

from label_easyocr_extractor import extract_with_easyocr
from label_image_preprocess import build_fallback_variants
from label_neural_extractor import extract_with_paddleocr
from mercadona_label_evidence import LabelImageEvidence
from mercadona_label_pipeline import download_label_image
from mercadona_nutrition_reader import OCR_EVIDENCE_LEVEL, VisionExtraction, read_evidence
from nutrition_visual_table_detector import detect_visual_table_regions

CORE_FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")
REVERSAL_PREFIX = "SINGLE_REVERSED_MACRO_CANDIDATE:"


def _profile(parsed: Any) -> dict[str, float] | None:
    nutrition = getattr(parsed, "nutrition", None)
    if getattr(parsed, "basis", None) not in {"100_g", "100_ml"} or not isinstance(nutrition, dict):
        return None
    if any(field not in nutrition for field in CORE_FIELDS):
        return None
    out: dict[str, float] = {}
    for field in CORE_FIELDS:
        value = nutrition.get(field)
        if not isinstance(value, (int, float)):
            return None
        out[field] = float(value)
    return out


def _is_single_reversal_candidate(parsed: Any) -> bool:
    reasons = tuple(str(reason) for reason in (getattr(parsed, "reasons", ()) or ()))
    return (
        getattr(parsed, "status", None) == "REVIEW"
        and _profile(parsed) is not None
        and len(reasons) == 1
        and reasons[0].startswith(REVERSAL_PREFIX)
    )


def _corroborates_single_reversal_candidate(paddle: Any, easy: Any) -> bool:
    """Return true only for exact independent corroboration of a guarded tuple.

    This is diagnostic evidence only. It deliberately does not promote REVIEW to
    usable nutrition; production acceptance remains in the ordinary parser and
    multi-engine ensemble.
    """
    if not _is_single_reversal_candidate(paddle):
        return False
    if getattr(easy, "status", None) != "DECLARED":
        return False
    if getattr(paddle, "basis", None) != getattr(easy, "basis", None):
        return False
    left, right = _profile(paddle), _profile(easy)
    if left is None or right is None:
        return False
    return all(abs(left[field] - right[field]) <= 1e-9 for field in CORE_FIELDS)


def _read(evidence: LabelImageEvidence, extracted: Any):
    return read_evidence(
        evidence,
        VisionExtraction(
            text=extracted.text,
            confidence=extracted.confidence,
            engine=extracted.engine,
            engine_version=extracted.engine_version,
        ),
    )


def _payload(reading: Any) -> dict[str, Any]:
    return {
        "status": reading.parsed.status,
        "basis": reading.parsed.basis,
        "nutrition": reading.parsed.nutrition,
        "reasons": list(reading.parsed.reasons),
        "confidence": reading.extraction.confidence,
        "engine": reading.extraction.engine,
        "engine_version": reading.extraction.engine_version,
        "normalized_ocr_text": reading.parsed.normalized_text,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product-id", required=True)
    ap.add_argument("--ean", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--image-url", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    evidence = LabelImageEvidence(
        retailer="Mercadona",
        retailer_sku=args.product_id,
        product_name=args.name,
        image_url=args.image_url,
        image_index=0,
        observed_at="",
        source_page=None,
        redistribution_allowed=False,
        purpose="PACK_LABEL_CANDIDATE",
        perspective=9,
    )

    attempts: list[dict[str, Any]] = []
    corroborated = False
    with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-easy-reversal-") as td:
        base = Path(td)
        image_path = base / f"{args.product_id}.jpg"
        download_label_image(args.image_url, image_path, timeout=20.0)
        regions = detect_visual_table_regions(image_path, base / "regions")
        targets = [("visual_region", region.path, region) for region in regions[:2]]
        if not targets:
            targets = [("full_back_image", image_path, None)]

        # One deterministic preprocessing fallback only. This is a diagnostic
        # probe, not a best-of-many selector: the known center crop is attempted
        # after the ordinary visual target to test whether text scale/edge clutter
        # explains EasyOCR's lost decimal glyphs and basis token.
        variants = build_fallback_variants(image_path, base / "fallback")
        center = next((variant for variant in variants if variant.name == "crop_center"), None)
        if center is not None:
            targets.append(("crop_center", center.path, None))

        for target_kind, target_path, region in targets:
            attempt: dict[str, Any] = {
                "target_kind": target_kind,
                "region": {
                    "name": region.name,
                    "box": list(region.box),
                    "score": region.score,
                } if region is not None else {"name": target_kind, "box": None, "score": None},
                "engines": {},
                "errors": {},
                "exact_independent_corroboration": False,
            }
            readings: dict[str, Any] = {}
            for strategy, extractor in (
                ("paddleocr", extract_with_paddleocr),
                ("easyocr", extract_with_easyocr),
            ):
                try:
                    extracted = extractor(target_path)
                    reading = _read(evidence, extracted)
                    readings[strategy] = reading.parsed
                    attempt["engines"][strategy] = _payload(reading)
                except Exception as exc:  # live diagnostic only
                    attempt["errors"][strategy] = f"{type(exc).__name__}:{exc}"
            if "paddleocr" in readings and "easyocr" in readings:
                attempt["exact_independent_corroboration"] = _corroborates_single_reversal_candidate(
                    readings["paddleocr"], readings["easyocr"]
                )
                corroborated = corroborated or attempt["exact_independent_corroboration"]
            attempts.append(attempt)

    result = {
        "product_id": args.product_id,
        "ean": args.ean,
        "name": args.name,
        "image_url": args.image_url,
        "perspective": 9,
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "evidence_level": OCR_EVIDENCE_LEVEL,
        "redistribution_allowed": False,
        "image_bytes_persisted": False,
        "historical_nutrition_values_reused": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
        "diagnostic_status": "CORROBORATED" if corroborated else "NOT_CORROBORATED",
        "attempts": attempts,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "product_id": args.product_id,
        "diagnostic_status": result["diagnostic_status"],
        "attempts": len(attempts),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
