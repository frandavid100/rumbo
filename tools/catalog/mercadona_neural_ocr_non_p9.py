from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
import time
from typing import Any

from mercadona_label_evidence import LabelImageEvidence
from mercadona_label_pipeline import download_label_image
from mercadona_neural_ocr_wave import (
    _ensemble_payload,
    _extract_region,
    _ocr_targets,
    _reading_payload,
    _stable_sample_key,
)
from mercadona_nutrition_reader import OCR_EVIDENCE_LEVEL
from mercadona_ocr_image_candidates import has_p9_zoom, non_p9_zoom_candidates
from nutrition_ocr_ensemble import ENSEMBLE_VERSION
from nutrition_visual_table_detector import detect_visual_table_regions


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _candidate(
    row: dict[str, Any],
    *,
    required_perspective: str | None,
    preferred_perspectives: tuple[str, ...],
) -> tuple[int, dict[str, Any]] | None:
    # This expansion is deliberately restricted to products already carrying the
    # strongest first-party food signal used by the main wave: structured ingredients.
    if not row.get("ingredients") or has_p9_zoom(row):
        return None
    candidates = non_p9_zoom_candidates(row, preferred_perspectives=preferred_perspectives)
    if required_perspective is not None:
        candidates = [hit for hit in candidates if str(hit[1].get("perspective")) == required_perspective]
    return candidates[0] if candidates else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard-index", type=int, required=True)
    ap.add_argument("--shard-count", type=int, required=True)
    ap.add_argument("--limit", type=int, default=0, help="0 means all rows in this shard")
    ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--required-perspective", default=None)
    ap.add_argument("--preferred-perspectives", default="10,4,2,1")
    args = ap.parse_args()

    preferred = tuple(part.strip() for part in args.preferred_perspectives.split(",") if part.strip())
    all_rows = _load(Path(args.products))
    eligible_hits = [
        (row, hit)
        for row in all_rows
        if (hit := _candidate(
            row,
            required_perspective=args.required_perspective,
            preferred_perspectives=preferred,
        )) is not None
    ]
    eligible_hits.sort(key=lambda pair: _stable_sample_key(pair[0]))
    selected = [pair for i, pair in enumerate(eligible_hits) if i % args.shard_count == args.shard_index]
    if args.limit > 0:
        selected = selected[: args.limit]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    selected_perspectives: Counter[str] = Counter()

    for product_index, (row, (image_index, photo)) in enumerate(selected):
        if product_index and args.delay:
            time.sleep(args.delay)
        pid = str(row.get("product_id") or "")
        if not pid:
            continue
        image_url = str(photo.get("zoom") or "")
        perspective = photo.get("perspective")
        selected_perspectives[str(perspective)] += 1
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
            "selection_policy": "STRUCTURED_INGREDIENTS_WITHOUT_P9; TRUE_NON_P9_PERSPECTIVE",
            "required_perspective": args.required_perspective,
            "preferred_perspectives": list(preferred),
            "source": "MERCADONA_FIRST_PARTY",
            "source_record_kind": "label image",
            "evidence_level": OCR_EVIDENCE_LEVEL,
            "redistribution_allowed": False,
            "status": "UNRESOLVED",
            "attempts": [],
        }
        try:
            with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-neural-non-p9-") as td:
                base = Path(td)
                image_path = base / f"{pid}.jpg"
                download_label_image(image_url, image_path, timeout=15.0)
                regions = detect_visual_table_regions(image_path, base / "regions")
                item["visual_regions_detected"] = len(regions)
                if not regions:
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
                        attempted_strategies = "+".join(strategy for strategy, _family, _reading in readings)
                        item["claim"] = (
                            f"{OCR_EVIDENCE_LEVEL}; source=MERCADONA_FIRST_PARTY/label image; "
                            f"reader=ensemble-{ENSEMBLE_VERSION}; true_perspective={perspective}; "
                            f"target={target_kind}; strategies={attempted_strategies}; "
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

    (out / f"results-{args.shard_index:02d}.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results),
        encoding="utf-8",
    )
    summary = {
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "evidence_level": OCR_EVIDENCE_LEVEL,
        "mode": "NON_P9_PADDLEOCR_TESSERACT_WITH_CONDITIONAL_EASYOCR_CORROBORATION",
        "selection_policy": "STRUCTURED_INGREDIENTS_WITHOUT_P9; TRUE_NON_P9_PERSPECTIVE",
        "required_perspective": args.required_perspective,
        "preferred_perspectives": list(preferred),
        "sample_order": "SHA256_PRODUCT_ID_EAN",
        "inventory_products": len(all_rows),
        "eligible_products": len(eligible_hits),
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "selected": len(selected),
        "processed": len(results),
        "selected_perspectives": dict(sorted(selected_perspectives.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "declared_rate": round(status_counts["DECLARED"] / len(results), 4) if results else 0.0,
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    (out / f"summary-{args.shard_index:02d}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if results else 2


if __name__ == "__main__":
    raise SystemExit(main())
