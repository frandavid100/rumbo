from __future__ import annotations

"""Fresh OCR retry for an explicitly preselected current Mercadona image.

The caller must prove upstream that the selected image URL occurs exactly once in
CURRENT first-party product detail after exact EAN revalidation. This module does
not guess a perspective or fall back to another photo. It only changes OCR
routing; the ordinary parser, coherence and independent-engine gates stay intact.
Historical OCR values are never consumed here.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
import time
from typing import Any

from mercadona_label_evidence import LabelImageEvidence
import mercadona_near_safe_variant_rescue as rescue
import mercadona_neural_ocr_wave as base
import mercadona_preselected_three_of_four_variant_rescue as preselected


PRESELECTED_FLAG = "_preselected_current_first_party_label_image"


def _preselected_photo(row: dict[str, Any]) -> tuple[int, dict[str, Any]] | None:
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    hits = [
        (index, photo)
        for index, photo in enumerate(photos)
        if isinstance(photo, dict)
        and photo.get(PRESELECTED_FLAG) is True
        and str(photo.get("zoom") or "").strip()
    ]
    # Fail closed if upstream accidentally marks zero or multiple images.
    return hits[0] if len(hits) == 1 else None


def _eligible(row: dict[str, Any]) -> bool:
    return _preselected_photo(row) is not None


def _configure_variant_rescue() -> None:
    base._ORIGINAL_EXTRACT_REGION = base._extract_region
    rescue.should_run_variant_rescue = preselected.should_run_preselected_three_of_four_variant_rescue
    base._extract_region = rescue._extract_region


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard-index", type=int, required=True)
    ap.add_argument("--shard-count", type=int, required=True)
    ap.add_argument("--limit", type=int, default=0, help="0 means all rows in this shard")
    ap.add_argument("--delay", type=float, default=0.15)
    args = ap.parse_args()

    _configure_variant_rescue()
    all_rows = base._load(Path(args.products))
    eligible = [row for row in all_rows if _eligible(row)]
    eligible.sort(key=base._stable_sample_key)
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
        photo_hit = _preselected_photo(row)
        if not pid or photo_hit is None:
            continue
        image_index, photo = photo_hit
        image_url = str(photo["zoom"])
        perspective = photo.get("perspective")
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
            perspective=perspective,
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
            "perspective": perspective,
            "eligibility_mode": "preselected-current-first-party-image",
            "source": "MERCADONA_FIRST_PARTY",
            "source_record_kind": "label image",
            "evidence_level": base.OCR_EVIDENCE_LEVEL,
            "redistribution_allowed": False,
            "status": "UNRESOLVED",
            "attempts": [],
        }
        try:
            with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-current-image-") as td:
                temp = Path(td)
                image_path = temp / f"{pid}.jpg"
                base.download_label_image(image_url, image_path, timeout=15.0)
                regions = base.detect_visual_table_regions(image_path, temp / "regions")
                item["visual_regions_detected"] = len(regions)
                if not regions:
                    item["status"] = "NO_VISUAL_REGION"
                for target_kind, target_path, region in base._ocr_targets(image_path, regions):
                    readings, engine_errors, ensemble = base._extract_region(evidence, target_path, target_kind)
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
                            strategy: base._reading_payload(reading)
                            for strategy, _family, reading in readings
                        },
                        "engine_errors": engine_errors,
                        "ensemble": base._ensemble_payload(ensemble),
                    }
                    item["attempts"].append(attempt)
                    if ensemble.declared_usable:
                        item["status"] = "DECLARED"
                        item["basis"] = ensemble.basis
                        item["nutrition"] = ensemble.nutrition
                        attempted = "+".join(strategy for strategy, _family, _reading in readings)
                        item["claim"] = (
                            f"{base.OCR_EVIDENCE_LEVEL}; source=MERCADONA_FIRST_PARTY/label image; "
                            f"reader=ensemble-{base.ENSEMBLE_VERSION}; target={target_kind}; "
                            f"strategies={attempted}; independent_engines={ensemble.independent_engine_families}; "
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
    result_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results),
        encoding="utf-8",
    )
    summary = {
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "evidence_level": base.OCR_EVIDENCE_LEVEL,
        "mode": "PRESELECTED_CURRENT_FIRST_PARTY_IMAGE_WITH_VARIANT_RESCUE",
        "inventory_products": len(all_rows),
        "eligible_products": len(eligible),
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "selected": len(selected),
        "processed": len(results),
        "status_counts": dict(sorted(status_counts.items())),
        "declared_rate": round(status_counts["DECLARED"] / len(results), 4) if results else 0.0,
        "redistribution_allowed": False,
        "historical_values_consumed": False,
        "image_guessing": False,
    }
    (out / f"summary-{args.shard_index:02d}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if results else 2


if __name__ == "__main__":
    raise SystemExit(main())
