from __future__ import annotations

"""Prepare a bounded reread of fixed-cut Mercadona label images for removed products.

This is a historical-cut route, not a current-catalog route. It is only allowed when
Mercadona's current first-party product-detail endpoint returns HTTP 404. Identity and
image routing are anchored to an earlier persisted raw-live OCR observation that already
carried the exact EAN and exact Mercadona first-party image URL. Historical nutrition
values and OCR text are never copied into the new OCR input.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

from mercadona_current_single_family_canary_prepare import PRESELECTED_FLAG
from mercadona_first_party_details import _get_json

EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"
SOURCE = "MERCADONA_FIRST_PARTY"
SOURCE_RECORD_KIND = "label image"
IMAGE_PREFIX = "https://prod-mercadona.imgix.net/images/"
IDENTITY_RULE = "FIXED_CUT_EXACT_FIRST_PARTY_IMAGE_URL_REREAD_AFTER_LIVE_404"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_rows(source_dirs: list[Path]) -> list[tuple[Path, dict[str, Any]]]:
    rows: list[tuple[Path, dict[str, Any]]] = []
    for root in source_dirs:
        for path in sorted(root.rglob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append((path, row))
    return rows


def _strict_anchor(row: dict[str, Any]) -> bool:
    ean = str(row.get("ean") or "").strip()
    url = str(row.get("image_url") or "").strip()
    perspective = str(row.get("perspective") or "").strip()
    return bool(
        row.get("evidence_level") == EVIDENCE
        and row.get("source") == SOURCE
        and row.get("source_record_kind") == SOURCE_RECORD_KIND
        and row.get("redistribution_allowed") is False
        and ean
        and url.startswith(IMAGE_PREFIX)
        and perspective
    )


def _require_live_404(product_id: str) -> str:
    try:
        _get_json(product_id, timeout=20.0)
    except HTTPError as exc:
        if exc.code == 404:
            return "HTTP_404"
        raise RuntimeError(f"unexpected current detail HTTP status for {product_id}: {exc.code}") from exc
    except Exception as exc:
        raise RuntimeError(f"current detail check failed for {product_id}: {type(exc).__name__}:{exc}") from exc
    raise RuntimeError(f"current detail exists for {product_id}; use a current-image route instead")


def prepare(
    source_dirs: list[Path],
    output_dir: Path,
    *,
    targets: list[str],
    source_runs: dict[str, int],
    source_artifacts: dict[str, int],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows = _load_rows(source_dirs)
    by_id: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    for path, row in raw_rows:
        pid = str(row.get("product_id") or "").strip()
        if pid in targets and _strict_anchor(row):
            by_id[pid].append((path, row))

    products: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for pid in targets:
        candidates = by_id.get(pid, [])
        if not candidates:
            excluded.append({"product_id": pid, "reason": "NO_STRICT_RAW_LIVE_IDENTITY_IMAGE_ANCHOR"})
            continue

        identities = {
            (
                str(row.get("ean") or "").strip(),
                str(row.get("image_url") or "").strip(),
                str(row.get("perspective") or "").strip(),
            )
            for _path, row in candidates
        }
        if len(identities) != 1:
            excluded.append({
                "product_id": pid,
                "reason": "CONFLICTING_HISTORICAL_IDENTITY_OR_IMAGE_ANCHORS",
                "anchors": sorted(identities),
            })
            continue

        live_status = _require_live_404(pid)
        source_path, anchor = candidates[0]
        ean, image_url, perspective = next(iter(identities))
        photo = {
            "zoom": image_url,
            "perspective": int(perspective) if perspective.isdigit() else perspective,
            PRESELECTED_FLAG: True,
        }
        product = {
            "product_id": pid,
            "ean": ean,
            "name": anchor.get("name") or pid,
            "brand": anchor.get("brand"),
            "category_id": anchor.get("category_id"),
            "category_name": anchor.get("category_name"),
            "observed_at": _now(),
            "photos": [photo],
            "_fixed_cut_reread_meta": {
                "identity_rule": IDENTITY_RULE,
                "identity_basis": "EARLIER_PERSISTED_RAW_LIVE_EXACT_EAN_PLUS_EXACT_MERCADONA_FIRST_PARTY_IMAGE_URL",
                "historical_source_run_id": source_runs.get(pid),
                "historical_source_artifact_id": source_artifacts.get(pid),
                "historical_source_file": str(source_path),
                "canonical_ean": ean,
                "image_url": image_url,
                "perspective": photo["perspective"],
                "current_detail_status": live_status,
                "historical_nutrition_values_consumed": False,
                "historical_ocr_text_consumed": False,
                "cross_run_value_fusion": False,
                "cross_image_value_fusion": False,
                "missing_values_inferred": False,
            },
        }
        products.append(product)
        selected.append({
            "product_id": pid,
            "ean": ean,
            "name": product["name"],
            "image_url": image_url,
            "perspective": photo["perspective"],
            "identity_rule": IDENTITY_RULE,
            "current_detail_status": live_status,
            "historical_source_run_id": source_runs.get(pid),
            "historical_source_artifact_id": source_artifacts.get(pid),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "products.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in products),
        encoding="utf-8",
    )
    summary = {
        "mode": "FIXED_CUT_REMOVED_PRODUCT_FIRST_PARTY_IMAGE_REREAD",
        "identity_rule": IDENTITY_RULE,
        "requested_targets": targets,
        "selected": selected,
        "excluded": excluded,
        "selection_policy": (
            "Current product detail must return HTTP 404. Reread only the exact Mercadona first-party image URL and "
            "exact EAN already persisted together in earlier raw-live OCR evidence for the fixed 2026-08-27 cut."
        ),
        "historical_nutrition_values_consumed": False,
        "historical_ocr_text_consumed": False,
        "cross_run_value_fusion": False,
        "cross_image_value_fusion": False,
        "missing_values_inferred": False,
        "images_persisted": False,
        "redistribution_allowed": False,
        "fresh_observation_must_satisfy_declared_contract_independently": True,
    }
    (output_dir / "selection-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return products, summary


def _parse_mapping(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        pid, sep, raw_number = value.partition("=")
        if not sep or not pid.strip() or not raw_number.strip().isdigit():
            raise ValueError(f"invalid mapping {value!r}; expected product_id=integer")
        out[pid.strip()] = int(raw_number.strip())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", action="append", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--targets", nargs="+", required=True)
    ap.add_argument("--source-run", action="append", default=[])
    ap.add_argument("--source-artifact", action="append", default=[])
    args = ap.parse_args()
    targets = [str(pid).strip() for pid in args.targets]
    products, summary = prepare(
        [Path(value) for value in args.source_dir],
        Path(args.out),
        targets=targets,
        source_runs=_parse_mapping(args.source_run),
        source_artifacts=_parse_mapping(args.source_artifact),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if len(products) == len(targets) else 2


if __name__ == "__main__":
    raise SystemExit(main())
