from __future__ import annotations

"""Prepare a fresh OCR reparse of previously verified exact-current non-P9 images.

This route exists for parser-regression validation after OCR/parser code changes.  It
never reuses historical nutrition values.  A previous canary selection contributes
only product identity (product_id/EAN) and the exact first-party image URL.  Before
any image is routed again, current Mercadona detail must still expose the same EAN,
zero perspective=9 images, and exactly one non-P9 zoom image whose URL is identical
to the prior selection.  Any mismatch fails closed.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from mercadona_current_single_family_canary_prepare import PRESELECTED_FLAG, RETRY_IDENTITY_RULE
from mercadona_first_party_details import _get_json, _now, normalize


def _load_selection(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("selection summary must be an object")
    return payload


def prepare(
    selection_path: Path,
    output_dir: Path,
    *,
    targets: list[str],
    source_run_id: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selection = _load_selection(selection_path)
    selected_rows = selection.get("selected_after_live_verification") or []
    by_id = {
        str(row.get("product_id") or ""): row
        for row in selected_rows
        if isinstance(row, dict) and str(row.get("product_id") or "")
    }

    products: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for raw_target in targets:
        pid = str(raw_target).strip()
        prior = by_id.get(pid)
        if prior is None:
            excluded.append({"product_id": pid, "reason": "NOT_IN_PRIOR_VERIFIED_SELECTION"})
            continue

        expected_ean = str(prior.get("ean") or "").strip()
        expected_url = str(prior.get("image_url") or prior.get("historical_image_url") or "").strip()
        if not expected_ean or not expected_url:
            excluded.append({"product_id": pid, "reason": "PRIOR_SELECTION_MISSING_IDENTITY_ANCHOR"})
            continue

        observed_at = _now()
        try:
            payload, source_url = _get_json(pid, timeout=20.0)
            live = normalize(payload, source_url=source_url, observed_at=observed_at)
        except Exception as exc:
            excluded.append({"product_id": pid, "reason": f"LIVE_DETAIL_ERROR:{type(exc).__name__}:{exc}"})
            continue

        current_ean = str(live.get("ean") or "").strip()
        if current_ean != expected_ean:
            excluded.append({
                "product_id": pid,
                "reason": "EAN_MISMATCH",
                "expected_ean": expected_ean,
                "current_ean": current_ean,
            })
            continue

        photos = live.get("photos") if isinstance(live.get("photos"), list) else []
        current_p9 = [
            (index, photo)
            for index, photo in enumerate(photos)
            if isinstance(photo, dict)
            and str(photo.get("perspective") or "") == "9"
            and str(photo.get("zoom") or "").strip()
        ]
        if current_p9:
            excluded.append({
                "product_id": pid,
                "reason": "CURRENT_P9_PRESENT_USE_P9_ROUTE",
                "matches": len(current_p9),
            })
            continue

        alternatives = [
            (index, photo)
            for index, photo in enumerate(photos)
            if isinstance(photo, dict)
            and str(photo.get("perspective") or "").strip()
            and str(photo.get("perspective") or "") != "9"
            and str(photo.get("zoom") or "").strip()
        ]
        if len(alternatives) != 1:
            excluded.append({
                "product_id": pid,
                "reason": "UNIQUE_CURRENT_NON_P9_IMAGE_REQUIRED",
                "matches": len(alternatives),
            })
            continue

        image_index, photo = alternatives[0]
        selected_url = str(photo.get("zoom") or "").strip()
        if selected_url != expected_url:
            excluded.append({
                "product_id": pid,
                "reason": "CURRENT_IMAGE_URL_CHANGED",
                "expected_url": expected_url,
                "current_url": selected_url,
            })
            continue
        if sum(
            1
            for candidate in photos
            if isinstance(candidate, dict)
            and str(candidate.get("zoom") or "").strip() == selected_url
        ) != 1:
            excluded.append({"product_id": pid, "reason": "CURRENT_IMAGE_URL_NOT_UNIQUE"})
            continue

        routed = dict(photo)
        routed[PRESELECTED_FLAG] = True
        current = dict(live)
        current["photos"] = [routed]
        current["_exact_current_image_meta"] = {
            "image_url": selected_url,
            "historical_image_url": expected_url,
            "historical_image_url_changed": False,
            "current_photo_index": image_index,
            "current_photo_perspective": photo.get("perspective"),
            "image_identity_rule": RETRY_IDENTITY_RULE,
            "canonical_ean": expected_ean,
            "current_ean": current_ean,
            "identity_basis": "EXACT_NONEMPTY_CANONICAL_EAN_EQUALS_CURRENT_FIRST_PARTY_EAN",
            "image_selection_basis": (
                "PARSER_REGRESSION_FRESH_REPARSE; EXACT_PRIOR_VERIFIED_FIRST_PARTY_IMAGE_URL STILL "
                "SOLE CURRENT NON_P9 ZOOM IMAGE; ZERO CURRENT P9; EXACT EAN REVALIDATED; HISTORICAL "
                "NUTRITION VALUES NOT CONSUMED"
            ),
            "live_detail_source_url": source_url,
            "live_detail_observed_at": observed_at,
            "previous_latest_raw_run_id": source_run_id,
            "historical_missing_core_fields": prior.get("missing_core_fields"),
            "historical_engine_families": prior.get("historical_engine_families"),
            "historical_corroborated_fields": prior.get("historical_corroborated_fields"),
        }
        products.append(current)
        accepted.append({
            "product_id": pid,
            "ean": expected_ean,
            "name": live.get("name") or prior.get("name"),
            "image_url": selected_url,
            "perspective": photo.get("perspective"),
            "source_run_id": source_run_id,
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "products.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in products),
        encoding="utf-8",
    )
    summary = {
        "mode": "PARSER_REGRESSION_FRESH_REPARSE",
        "source_run_id": source_run_id,
        "requested_targets": [str(target).strip() for target in targets],
        "accepted_after_live_verification": accepted,
        "excluded_after_live_verification": excluded,
        "historical_nutrition_values_consumed": False,
        "cross_run_value_fusion": False,
        "cross_image_value_fusion": False,
        "missing_values_inferred": False,
        "images_persisted": False,
        "redistribution_allowed": False,
        "fresh_observation_must_satisfy_declared_contract_independently": True,
    }
    (output_dir / "selection-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return products, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selection", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--source-run-id", type=int, required=True)
    ap.add_argument("--targets", nargs="+", required=True)
    args = ap.parse_args()
    products, summary = prepare(
        Path(args.selection),
        Path(args.out),
        targets=args.targets,
        source_run_id=args.source_run_id,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if len(products) == len(args.targets) else 2


if __name__ == "__main__":
    raise SystemExit(main())
