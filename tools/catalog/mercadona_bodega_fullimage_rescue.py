from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any, Iterable

from label_easyocr_extractor import extract_with_easyocr
from label_neural_extractor import extract_with_paddleocr
from label_text_extractor import extract_with_tesseract
from mercadona_label_evidence import LabelImageEvidence
from mercadona_label_pipeline import download_label_image
from mercadona_neural_ocr_wave import (
    _as_parsed_readings,
    _ensemble_payload,
    _fuse_declared_only_readings,
    _reading,
    _reading_payload,
)
from mercadona_nutrition_reader import OCR_EVIDENCE_LEVEL
from nutrition_ocr_ensemble import fuse_ocr_readings


CORE_NUTRITION_FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")
TARGET_KIND = "bodega_full_back_image_rescue"


def select_current_candidates(revalidation: dict[str, Any], *, require_all: bool = True) -> list[dict[str, str]]:
    """Select only identity/EAN/P9-revalidated current Mercadona observations.

    The source full-cut workflow has already re-read the official product API. This
    helper deliberately refuses a partial rescue when require_all=True so a stale
    or changed product cannot silently disappear from the diagnostic cohort.
    """
    checks = revalidation.get("checks") if isinstance(revalidation.get("checks"), list) else []
    expected = int(revalidation.get("expected", len(checks)))
    out: list[dict[str, str]] = []
    for row in checks:
        if not isinstance(row, dict) or row.get("ok") is not True:
            continue
        pid = str(row.get("product_id") or "").strip()
        ean = str(row.get("live_ean") or "").strip()
        image_url = str(row.get("live_p9_url") or "").strip()
        if pid and ean and image_url:
            out.append({"product_id": pid, "ean": ean, "image_url": image_url})
    if require_all and len(out) != expected:
        raise ValueError(f"Refusing partial Bodega rescue: {len(out)}/{expected} current candidates")
    return out


def choose_ensemble(readings: Iterable[tuple[str, str, Any]]):
    """Fuse all observations, allowing REVIEW noise to be ignored only safely.

    The strict fallback is the same production rule as the main Mercadona wave:
    only parser-DECLARED observations participate, and any conflicting DECLARED
    observation remains a hard REVIEW. This function never upgrades a partial or
    inferred value.
    """
    readings = tuple(readings)
    raw = fuse_ocr_readings(_as_parsed_readings(readings, TARGET_KIND))
    if raw.declared_usable:
        return raw
    strict = _fuse_declared_only_readings(
        (
            (strategy, family, reading.parsed, reading.extraction.confidence)
            for strategy, family, reading in readings
        ),
        TARGET_KIND,
    )
    return strict if strict.declared_usable else raw


def extract_full_image_all_families(evidence: LabelImageEvidence, image_path: Path):
    """Run the existing conservative parser over one deterministic full P9 image.

    Unlike the production wave's conditional EasyOCR routing, this bounded rescue
    always asks all three independent OCR families to observe the *same* current
    first-party P9. Acceptance still requires the unchanged parser/coherence and
    ensemble corroboration gates.
    """
    specs = (
        ("paddleocr", "paddleocr", extract_with_paddleocr),
        ("tesseract-psm4", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=4)),
        ("tesseract-psm6", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=6)),
        ("tesseract-psm11", "tesseract", lambda path: extract_with_tesseract(path, language="spa", psm=11)),
        ("easyocr", "easyocr", extract_with_easyocr),
    )
    readings: list[tuple[str, str, Any]] = []
    errors: dict[str, str] = {}
    for strategy, family, extractor in specs:
        try:
            readings.append((strategy, family, _reading(evidence, extractor(image_path))))
        except Exception as exc:  # diagnostic artifact must record, not hide, engine failures
            errors[strategy] = f"{type(exc).__name__}:{exc}"
    return readings, errors, choose_ensemble(readings)


def _safe_declared(ensemble) -> bool:
    nutrition = ensemble.nutrition or {}
    return bool(
        ensemble.declared_usable
        and ensemble.basis in {"100_g", "100_ml"}
        and ensemble.independent_engine_families >= 2
        and ensemble.corroborated_fields == len(CORE_NUTRITION_FIELDS)
        and all(field in nutrition for field in CORE_NUTRITION_FIELDS)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revalidation", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    source = json.loads(Path(args.revalidation).read_text(encoding="utf-8"))
    candidates = select_current_candidates(source, require_all=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for candidate in candidates:
        pid = candidate["product_id"]
        evidence = LabelImageEvidence(
            retailer="Mercadona",
            retailer_sku=pid,
            product_name=pid,
            image_url=candidate["image_url"],
            image_index=0,
            observed_at="",
            source_page=None,
            redistribution_allowed=False,
            purpose="PACK_LABEL_CANDIDATE",
            perspective=9,
        )
        item: dict[str, Any] = {
            **candidate,
            "perspective": 9,
            "source": "MERCADONA_FIRST_PARTY",
            "source_record_kind": "label image",
            "evidence_level": OCR_EVIDENCE_LEVEL,
            "redistribution_allowed": False,
            "prior_values_reused": False,
            "missing_values_inferred": False,
            "image_bytes_persisted": False,
            "CLASSIFIED": 0,
            "MENU_ELIGIBLE": 0,
            "status": "REVIEW",
        }
        try:
            with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-bodega-fullimage-") as td:
                image_path = Path(td) / f"{pid}.jpg"
                download_label_image(candidate["image_url"], image_path, timeout=15.0)
                readings, engine_errors, ensemble = extract_full_image_all_families(evidence, image_path)
                item["engines"] = {
                    strategy: _reading_payload(reading)
                    for strategy, _family, reading in readings
                }
                item["engine_errors"] = engine_errors
                item["ensemble"] = _ensemble_payload(ensemble)
                if _safe_declared(ensemble):
                    item["status"] = "DECLARED"
                    item["basis"] = ensemble.basis
                    item["nutrition"] = ensemble.nutrition
                    item["claim"] = (
                        f"{OCR_EVIDENCE_LEVEL}; source=MERCADONA_FIRST_PARTY/label image; "
                        f"target={TARGET_KIND}; independent_engines={ensemble.independent_engine_families}; "
                        f"corroborated_fields={ensemble.corroborated_fields}; basis={ensemble.basis}"
                    )
        except Exception as exc:
            item["status"] = "ERROR"
            item["error"] = f"{type(exc).__name__}:{exc}"
        results.append(item)

    (out / "results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results),
        encoding="utf-8",
    )
    summary = {
        "processed": len(results),
        "declared_product_ids": [row["product_id"] for row in results if row["status"] == "DECLARED"],
        "review_product_ids": [row["product_id"] for row in results if row["status"] == "REVIEW"],
        "error_product_ids": [row["product_id"] for row in results if row["status"] == "ERROR"],
        "evidence_level": OCR_EVIDENCE_LEVEL,
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "target": TARGET_KIND,
        "prior_values_reused": False,
        "missing_values_inferred": False,
        "image_bytes_persisted": False,
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if summary["error_product_ids"]:
        raise SystemExit(f"Bodega full-image rescue errors: {summary['error_product_ids']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
