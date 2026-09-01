from __future__ import annotations

import argparse
from collections import Counter
import json
import os
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
from mercadona_ocr_image_candidates import (
    deterministic_shard_window,
    structured_ingredients_p9_alternative_candidate,
)
from nutrition_ocr_ensemble import ENSEMBLE_VERSION
from nutrition_visual_table_detector import detect_visual_table_regions


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _still_review_baseline(path: Path) -> dict[str, dict[str, Any]]:
    rows = _load(path)
    if len(rows) != 2630:
        raise ValueError(f"expected 2630 persisted p9 rows, got {len(rows)}")
    selected = {
        str(row.get("product_id") or ""): row
        for row in rows
        if row.get("status") == "REVIEW" and (row.get("replay") or {}).get("status") == "REVIEW"
    }
    if not selected:
        raise ValueError("persisted p9 replay contains no rows that remain REVIEW in both passes")
    return selected


def selection_exit_code(*, processed: int, eligible: int, skip_first: int) -> int:
    """Treat a deterministically exhausted perspective stratum as a clean no-op.

    An empty result is still an error while unprocessed eligible rows should remain,
    so accidental selection regressions cannot silently pass CI.
    """
    if processed:
        return 0
    return 0 if skip_first >= eligible else 2


def _append_checkpoint(path: Path, row: dict[str, Any]) -> None:
    """Durably append one completed OCR row so job cancellation does not lose prior work."""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _write_progress(
    path: Path,
    *,
    required_perspective: str,
    eligible: int,
    selected: int,
    processed: int,
    status_counts: Counter[str],
    skip_first: int,
    shard_index: int,
    shard_count: int,
) -> None:
    """Persist a small atomic progress manifest alongside the append-only checkpoint."""
    payload = {
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "evidence_level": OCR_EVIDENCE_LEVEL,
        "required_perspective": required_perspective,
        "eligible_products": eligible,
        "selected": selected,
        "processed": processed,
        "status_counts": dict(sorted(status_counts.items())),
        "skip_first": skip_first,
        "shard_index": shard_index,
        "shard_count": shard_count,
        "complete": processed == selected,
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", required=True)
    ap.add_argument("--p9-replay-results", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--required-perspective", required=True)
    ap.add_argument("--shard-index", type=int, default=0)
    ap.add_argument("--shard-count", type=int, default=1)
    ap.add_argument("--skip-first", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0, help="0 means all remaining rows in this shard")
    ap.add_argument("--delay", type=float, default=0.15)
    args = ap.parse_args()

    required_perspective = str(args.required_perspective)
    if required_perspective == "9":
        raise SystemExit("perspective 9 is the baseline image and cannot be an alternative")

    all_rows = _load(Path(args.products))
    still_review = _still_review_baseline(Path(args.p9_replay_results))
    eligible_hits: list[tuple[dict[str, Any], tuple[int, dict[str, Any]], dict[str, Any]]] = []
    for row in all_rows:
        pid = str(row.get("product_id") or "")
        baseline = still_review.get(pid)
        if baseline is None:
            continue
        hit = structured_ingredients_p9_alternative_candidate(
            row, required_perspective=required_perspective
        )
        if hit is not None:
            eligible_hits.append((row, hit, baseline))

    eligible_hits.sort(key=lambda triplet: _stable_sample_key(triplet[0]))
    selected = deterministic_shard_window(
        eligible_hits,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
        skip_first=args.skip_first,
        limit=args.limit,
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    suffix = f"p{required_perspective}-s{args.shard_index:02d}"
    results_path = out / f"results-{suffix}.jsonl"
    progress_path = out / f"progress-{suffix}.json"
    # Always materialize checkpoint files before expensive OCR. GitHub Actions can then
    # upload partial evidence even when the runner reaches its wall-clock timeout.
    results_path.write_text("", encoding="utf-8")
    results: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    _write_progress(
        progress_path,
        required_perspective=required_perspective,
        eligible=len(eligible_hits),
        selected=len(selected),
        processed=0,
        status_counts=status_counts,
        skip_first=args.skip_first,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
    )

    for product_index, (row, (image_index, photo), baseline) in enumerate(selected):
        if product_index and args.delay:
            time.sleep(args.delay)
        pid = str(row.get("product_id") or "")
        image_url = str(photo.get("zoom") or "")
        perspective = photo.get("perspective")
        replay = baseline.get("replay") or {}
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
            "required_perspective": required_perspective,
            "selection_policy": "STRUCTURED_INGREDIENTS_WITH_P9; HISTORICAL_P9_AND_SAFE_REPLAY_BOTH_REVIEW; TRUE_NON_P9_ALTERNATIVE",
            "p9_baseline_status": baseline.get("status"),
            "p9_replay_status": replay.get("status"),
            "p9_replay_basis": replay.get("basis"),
            "p9_replay_nutrition": replay.get("nutrition"),
            "source": "MERCADONA_FIRST_PARTY",
            "source_record_kind": "label image",
            "evidence_level": OCR_EVIDENCE_LEVEL,
            "redistribution_allowed": False,
            "status": "UNRESOLVED",
            "attempts": [],
        }
        try:
            with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-neural-p9-alt-") as td:
                base = Path(td)
                image_path = base / f"{pid}-p{perspective}.jpg"
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
                        "name": "full_alternative_image",
                        "box": None,
                        "score": None,
                        "horizontal_lines": None,
                        "vertical_lines": None,
                        "line_density": None,
                    }
                    item["attempts"].append({
                        "target_kind": target_kind,
                        "region": region_payload,
                        "engines": {
                            strategy: _reading_payload(reading)
                            for strategy, _family, reading in readings
                        },
                        "engine_errors": engine_errors,
                        "ensemble": _ensemble_payload(ensemble),
                    })
                    if ensemble.declared_usable:
                        item["status"] = "DECLARED"
                        item["basis"] = ensemble.basis
                        item["nutrition"] = ensemble.nutrition
                        attempted_strategies = "+".join(
                            strategy for strategy, _family, _reading in readings
                        )
                        item["claim"] = (
                            f"{OCR_EVIDENCE_LEVEL}; source=MERCADONA_FIRST_PARTY/label image; "
                            f"reader=ensemble-{ENSEMBLE_VERSION}; alternative_perspective={perspective}; "
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
        _append_checkpoint(results_path, item)
        _write_progress(
            progress_path,
            required_perspective=required_perspective,
            eligible=len(eligible_hits),
            selected=len(selected),
            processed=len(results),
            status_counts=status_counts,
            skip_first=args.skip_first,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
        )

    exhausted = not results and args.skip_first >= len(eligible_hits)
    summary = {
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "evidence_level": OCR_EVIDENCE_LEVEL,
        "mode": "P9_REVIEW_ALTERNATIVE_VIEW_PADDLEOCR_TESSERACT_WITH_CONDITIONAL_EASYOCR_CORROBORATION",
        "selection_policy": "STRUCTURED_INGREDIENTS_WITH_P9; HISTORICAL_P9_AND_SAFE_REPLAY_BOTH_REVIEW; TRUE_NON_P9_ALTERNATIVE",
        "required_perspective": required_perspective,
        "sample_order": "SHA256_PRODUCT_ID_EAN",
        "inventory_products": len(all_rows),
        "baseline_still_review_products": len(still_review),
        "eligible_products": len(eligible_hits),
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "skip_first": args.skip_first,
        "selected": len(selected),
        "processed": len(results),
        "status_counts": dict(sorted(status_counts.items())),
        "declared_rate": round(status_counts["DECLARED"] / len(results), 4) if results else 0.0,
        "stratum_exhausted": exhausted,
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    (out / f"summary-{suffix}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return selection_exit_code(
        processed=len(results), eligible=len(eligible_hits), skip_first=args.skip_first
    )


if __name__ == "__main__":
    raise SystemExit(main())
