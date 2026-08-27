from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import tempfile

from label_neural_extractor import extract_with_paddleocr
from label_text_extractor import extract_with_tesseract
from mercadona_first_party_details import _get_json, normalize
from mercadona_label_evidence import collect_label_images, nutrition_image_candidates
from mercadona_label_pipeline import download_label_image
from mercadona_nutrition_importer import import_from_label_file
from mercadona_nutrition_reader import OCR_EVIDENCE_LEVEL

BASE = Path(__file__).resolve().parent
DEFAULT_BATCH = BASE / "fixtures" / "mercadona_ocr_first_party_pilot_32.json"
DEFAULT_OUT = BASE / "mercadona-ocr-first-party-pilot-output"


def tess(psm: int):
    return lambda path: extract_with_tesseract(path, language="spa", psm=psm)


def _format(row: dict) -> str | None:
    for key in ("size_format", "unit_name", "packaging"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    value = row.get("unit_size")
    return str(value) if value not in (None, "") else None


def _accepted(candidate) -> dict:
    return {
        "nutrition": candidate.nutrition,
        "source": candidate.source,
        "source_url": candidate.source_url,
        "source_record_id": candidate.source_record_id,
        "evidence_level": candidate.evidence_level,
        "claim": candidate.claim,
        "observed_at": candidate.observed_at,
    }


def main() -> int:
    batch_path = Path(os.environ.get("MERCADONA_OCR_BATCH_FILE", str(DEFAULT_BATCH)))
    out = Path(os.environ.get("MERCADONA_OCR_OUTPUT_DIR", str(DEFAULT_OUT)))
    max_images = max(1, int(os.environ.get("MERCADONA_OCR_MAX_LABEL_IMAGES", "2")))
    out.mkdir(parents=True, exist_ok=True)

    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    if not isinstance(batch, list) or not batch:
        raise ValueError("Mercadona OCR pilot batch must be a non-empty list")

    strategies = (("psm6", tess(6)), ("psm11", tess(11)))
    stats = Counter()
    rows: list[dict] = []
    nutrition_rows: list[dict] = []

    for index, item in enumerate(batch, 1):
        product_id = str(item["product_id"])
        report = {
            "product_id": product_id,
            "selection_category": item.get("category"),
            "selection_reason": item.get("reason"),
        }
        try:
            payload, api_url = _get_json(product_id, timeout=15.0)
            normalized = normalize(payload, source_url=api_url, observed_at=item.get("observed_at") or "")
            report.update({
                "name": normalized.get("name"),
                "ean": normalized.get("ean"),
                "brand": normalized.get("brand"),
                "api_source_url": api_url,
            })
            evidence = collect_label_images(
                retailer_sku=product_id,
                product_name=normalized.get("name") or product_id,
                images=normalized.get("photos") or [],
                source_page=normalized.get("share_url"),
                observed_at=normalized.get("observed_at") or None,
            )
            candidates = [x for x in nutrition_image_candidates(evidence) if str(x.perspective) == "9"]
            report["perspective_9_images"] = len(candidates)
            if not candidates:
                report["status"] = "NO_LABEL_IMAGE"
                stats["NO_LABEL_IMAGE"] += 1
                rows.append(report)
                print(f"processed={index}/{len(batch)} accepted={stats['OCR_ACCEPTED']}", flush=True)
                continue

            stats["PRODUCTS_WITH_LABEL_IMAGE"] += 1
            attempts_by_image = []
            accepted = None
            for evidence_row in candidates[:max_images]:
                stats["LABEL_IMAGES_PROCESSED"] += 1
                with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-first-party-ocr-") as td:
                    image_path = Path(td) / "label.jpg"
                    download_label_image(evidence_row.image_url, image_path, timeout=20.0)
                    result = import_from_label_file(
                        evidence_row,
                        image_path,
                        gtin=normalized.get("ean"),
                        brand=normalized.get("brand"),
                        tesseract_strategies=strategies,
                        neural_extractor=extract_with_paddleocr,
                        work_dir=Path(td) / "work",
                    )
                    attempts_by_image.append({
                        "image_index": evidence_row.image_index,
                        "image_url": evidence_row.image_url,
                        "status": result.status,
                        "reason": result.reason,
                        "attempts": [attempt.__dict__ for attempt in result.attempts],
                    })
                    if result.candidate is not None:
                        if result.candidate.evidence_level != OCR_EVIDENCE_LEVEL:
                            raise ValueError(
                                f"Invalid OCR provenance {result.candidate.evidence_level!r}; "
                                f"expected {OCR_EVIDENCE_LEVEL!r}"
                            )
                        accepted = result.candidate
                        break

            report["image_attempts"] = attempts_by_image
            if accepted is not None:
                report["status"] = "OCR_ACCEPTED"
                report["accepted"] = _accepted(accepted)
                stats["OCR_ACCEPTED"] += 1
                nutrition_rows.append({
                    "product_id": product_id,
                    "ean": normalized.get("ean"),
                    "name": normalized.get("name"),
                    "brand": normalized.get("brand"),
                    "format": _format(normalized),
                    **_accepted(accepted),
                })
            else:
                statuses = [x["status"] for x in attempts_by_image]
                if "REVIEW" in statuses:
                    report["status"] = "REVIEW"
                    stats["REVIEW"] += 1
                elif "ERROR" in statuses:
                    report["status"] = "ERROR"
                    stats["ERROR"] += 1
                else:
                    report["status"] = "UNRESOLVED"
                    stats["UNRESOLVED"] += 1
        except Exception as exc:
            report["status"] = "ERROR"
            report["error"] = f"{type(exc).__name__}:{exc}"
            stats["ERROR"] += 1

        rows.append(report)
        print(f"processed={index}/{len(batch)} accepted={stats['OCR_ACCEPTED']}", flush=True)

    summary = {
        "source": "MERCADONA_FIRST_PARTY",
        "numeric_nutrition_provenance": OCR_EVIDENCE_LEVEL,
        "batch_file": str(batch_path),
        "batch_size": len(batch),
        "stats": dict(stats),
        "recovery_rate": round(stats["OCR_ACCEPTED"] / len(batch), 4),
        "classified": 0,
        "menu_eligible": 0,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.json").write_text(json.dumps({**summary, "items": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "nutrition.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in nutrition_rows),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
