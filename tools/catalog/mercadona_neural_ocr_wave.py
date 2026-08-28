from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile
import time
from typing import Any

from label_easyocr_extractor import extract_with_easyocr
from label_neural_extractor import extract_with_paddleocr
from label_text_extractor import extract_with_tesseract
from mercadona_label_evidence import LabelImageEvidence
from mercadona_label_pipeline import download_label_image
from mercadona_nutrition_reader import OCR_EVIDENCE_LEVEL, VisionExtraction, read_evidence
from nutrition_ocr_ensemble import ENSEMBLE_VERSION, ParsedOCRReading, fuse_ocr_readings
from nutrition_visual_table_detector import VisualTableRegion, detect_visual_table_regions

MAX_REGIONS_PER_PRODUCT = 2
OCR_ENGINES = ("paddleocr", "tesseract", "easyocr")
OCR_STRATEGIES = ("paddleocr", "tesseract-psm4", "tesseract-psm6", "tesseract-psm11", "easyocr")


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


def _stable_sample_key(row: dict[str, Any]) -> tuple[str, str]:
    """Spread bounded pilots across the whole eligible inventory deterministically.

    Mercadona product ids are strongly clustered by product family and age. Sorting
    numerically before applying a per-shard limit therefore made the first pilot
    overwhelmingly fresh meat/produce and did not estimate OCR performance over
    the packaged-food universe. A SHA-256 ordering is stable but pseudo-random,
    while still processing every eligible row exactly once when --limit=0.
    """
    product_id = str(row.get("product_id") or "")
    ean = str(row.get("ean") or "")
    seed = f"{product_id}\0{ean}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest(), product_id


def _ocr_targets(
    image_path: Path,
    regions: list[VisualTableRegion],
) -> list[tuple[str, Path, VisualTableRegion | None]]:
    """Choose bounded OCR targets without treating morphology as a hard gate.

    The visual detector deliberately looks for ruled/table-like structure. Real
    Mercadona rear labels also contain borderless nutrition panels, so a detector
    miss cannot prove the absence of nutrition. In that case retry the official
    rear-label image itself. Acceptance remains entirely downstream: the parser,
    energy/macro coherence and two-independent-engine corroboration are unchanged.
    """
    if regions:
        return [("visual_region", region.path, region) for region in regions[:MAX_REGIONS_PER_PRODUCT]]
    return [("full_back_image", image_path, None)]


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


def _fuse_declared_only_readings(readings, target_kind: str):
    """Fuse only independently parser-validated observations.

    A REVIEW reading is useful audit evidence, but it must not veto two matching
    readings that have each already passed the deterministic label parser and
    energy/macro checks. Conversely, every conflicting DECLARED observation stays
    in the fusion and therefore still forces REVIEW.
    """
    return fuse_ocr_readings(
        ParsedOCRReading(
            strategy=f"{strategy}:{target_kind}",
            result=result,
            extraction_confidence=confidence,
            engine_family=family,
        )
        for strategy, family, result, confidence in readings
        if getattr(result, "status", None) == "DECLARED"
    )


def _as_parsed_readings(readings, target_kind: str):
    return tuple(
        ParsedOCRReading(
            strategy=f"{strategy}:{target_kind}",
            result=reading.parsed,
            extraction_confidence=reading.extraction.confidence,
            engine_family=family,
        )
        for strategy, family, reading in readings
    )


def _extract_region(evidence: LabelImageEvidence, region_path: Path, target_kind: str):
    # PSM 4, 6 and 11 are intentionally all used because nutrition tables
    # linearise differently as a single column, compact block or sparse text.
    # They remain one Tesseract engine family: complementary fields are useful,
    # but the layouts never count as independent corroboration.
    readings = []
    engine_errors: dict[str, str] = {}
    extractor_specs = (
        ("paddleocr", "paddleocr", extract_with_paddleocr),
        ("tesseract-psm4", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=4)),
        ("tesseract-psm6", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=6)),
        ("tesseract-psm11", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=11)),
    )
    for strategy, family, extractor in extractor_specs:
        try:
            extracted = extractor(region_path)
            reading = _reading(evidence, extracted)
            readings.append((strategy, family, reading))
        except Exception as exc:
            engine_errors[strategy] = f"{type(exc).__name__}:{exc}"

    ensemble = fuse_ocr_readings(_as_parsed_readings(readings, target_kind))

    # EasyOCR is deliberately a bounded rescue, not a compulsory third vote.
    # It cannot make an unsafe parse valid by itself, so only pay its CPU/model
    # cost when another independent engine already has a parser-DECLARED reading
    # that lacks safe corroboration from the Paddle/Tesseract baseline.
    if not ensemble.declared_usable and any(reading.parsed.status == "DECLARED" for _s, _f, reading in readings):
        try:
            extracted = extract_with_easyocr(region_path)
            reading = _reading(evidence, extracted)
            readings.append(("easyocr", "easyocr", reading))
        except Exception as exc:
            engine_errors["easyocr"] = f"{type(exc).__name__}:{exc}"
        else:
            raw_with_easyocr = fuse_ocr_readings(_as_parsed_readings(readings, target_kind))
            if raw_with_easyocr.declared_usable:
                ensemble = raw_with_easyocr
            else:
                strict = _fuse_declared_only_readings(
                    (
                        (strategy, family, reading.parsed, reading.extraction.confidence)
                        for strategy, family, reading in readings
                    ),
                    target_kind,
                )
                # REVIEW observations are not positive evidence. If their only
                # effect was to poison two matching, independently DECLARED reads,
                # use the clean fusion. Credible DECLARED conflicts remain REVIEW.
                ensemble = strict if strict.declared_usable else raw_with_easyocr

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
    eligible.sort(key=_stable_sample_key)
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
                    # Keep this diagnostic if even the bounded full-image rescue
                    # remains wholly unresolved; REVIEW/DECLARED may supersede it.
                    item["status"] = "NO_VISUAL_REGION"
                for target_kind, target_path, region in _ocr_targets(image_path, regions):
                    readings, engine_errors, ensemble = _extract_region(evidence, target_path, target_kind)
                    region_payload = {
                        "name": region.name,
                        "box": list(region.box),
                        "score": region.score,
                        "horizontal_lines": region.horizontal_lines,
                        "vertical_lines": region.vertical_lines,
                        "line_density": region.line_density,
                    } if region is not None else {
                        "name": "full_back_image",
                        "box": None,
                        "score": None,
                        "horizontal_lines": None,
                        "vertical_lines": None,
                        "line_density": None,
                    }
                    attempt = {
                        "target_kind": target_kind,
                        "region": region_payload,
                        "engines": {
                            strategy: _reading_payload(reading)
                            for strategy, _family, reading in readings
                        },
                        "engine_errors": engine_errors,
                        "ensemble": _ensemble_payload(ensemble),
                    }
                    item["attempts"].append(attempt)
                    if ensemble.declared_usable:
                        item["status"] = "DECLARED"
                        item["basis"] = ensemble.basis
                        item["nutrition"] = ensemble.nutrition
                        attempted_strategies = "+".join(strategy for strategy, _family, _reading_obj in readings)
                        item["claim"] = (
                            f"{OCR_EVIDENCE_LEVEL}; source=MERCADONA_FIRST_PARTY/label image; "
                            f"reader=ensemble-{ENSEMBLE_VERSION}; target={target_kind}; "
                            f"strategies={attempted_strategies}; "
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
        "mode": "PADDLEOCR_TESSERACT_WITH_CONDITIONAL_EASYOCR_CORROBORATION",
        "fallback_policy": "FULL_BACK_IMAGE_ONLY_WHEN_NO_VISUAL_REGION; EASYOCR_ONLY_WHEN_BASELINE_HAS_DECLARED_UNCORROBORATED_READING",
        "sample_order": "SHA256_PRODUCT_ID_EAN",
        "ocr_engines": list(OCR_ENGINES),
        "ocr_strategies": list(OCR_STRATEGIES),
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
