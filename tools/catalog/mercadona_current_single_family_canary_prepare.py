from __future__ import annotations

"""Prepare a bounded current-image OCR canary from strict single-family 3/4 REVIEW rows.

Historical OCR nutrition is used only to select candidates. Output product rows contain
current first-party metadata and exactly one live perspective=9 image; no historical
nutrition value is copied into the OCR input.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from mercadona_first_party_details import _get_json, normalize, _now

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
PRESELECTED_FLAG = "_preselected_current_first_party_label_image"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def prepare(residual_path: Path, output_dir: Path, targets: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_id = {str(row.get("product_id") or ""): row for row in _load_jsonl(residual_path)}
    products: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for pid in targets:
        old = by_id.get(pid)
        if old is None:
            excluded.append({"product_id": pid, "reason": "NO_LONGER_IN_STRICT_3_OF_4_RESIDUAL"})
            continue

        values = old.get("diagnostic_candidate_values") or {}
        missing = [field for field in CORE if values.get(field) is None]
        blockers = old.get("safety_blockers") or []
        valid = (
            old.get("canonical_status") == "REVIEW"
            and old.get("basis") in {"100_g", "100_ml"}
            and not blockers
            and len(missing) == 1
            and missing == (old.get("missing_core_fields") or [])
            and int(old.get("independent_engine_families") or 0) == 1
            and str(old.get("ean") or "").strip()
            and str(old.get("image_url") or "").strip()
        )
        if not valid:
            excluded.append({"product_id": pid, "reason": "NO_LONGER_SINGLE_FAMILY_EXPLICIT_3_OF_4"})
            continue

        canonical_ean = str(old["ean"]).strip()
        observed_image_url = str(old["image_url"]).strip()
        observed_at = _now()
        try:
            payload, source_url = _get_json(pid, timeout=20.0)
            live = normalize(payload, source_url=source_url, observed_at=observed_at)
        except Exception as exc:
            excluded.append({"product_id": pid, "reason": f"LIVE_DETAIL_ERROR:{type(exc).__name__}:{exc}"})
            continue

        current_ean = str(live.get("ean") or "").strip()
        if not current_ean or current_ean != canonical_ean:
            excluded.append({
                "product_id": pid,
                "reason": "EAN_MISMATCH",
                "canonical_ean": canonical_ean,
                "current_ean": current_ean,
            })
            continue

        photos = live.get("photos") if isinstance(live.get("photos"), list) else []
        exact = [
            (index, photo)
            for index, photo in enumerate(photos)
            if isinstance(photo, dict)
            and str(photo.get("zoom") or "").strip() == observed_image_url
            and str(photo.get("perspective") or "") == "9"
        ]
        if len(exact) != 1:
            excluded.append({
                "product_id": pid,
                "reason": "EXACT_P9_IMAGE_NOT_UNIQUE_CURRENT",
                "matches": len(exact),
            })
            continue

        image_index, photo = exact[0]
        routed = dict(photo)
        routed[PRESELECTED_FLAG] = True
        current = dict(live)
        current["photos"] = [routed]
        current["_exact_current_image_meta"] = {
            "image_url": observed_image_url,
            "current_photo_index": image_index,
            "current_photo_perspective": photo.get("perspective"),
            "canonical_ean": canonical_ean,
            "current_ean": current_ean,
            "identity_basis": "EXACT_NONEMPTY_CANONICAL_EAN_EQUALS_CURRENT_FIRST_PARTY_EAN",
            "image_selection_basis": "EXACT_LATEST_OBSERVED_PERSPECTIVE_9_IMAGE_URL_OCCURS_ONCE_IN_CURRENT_MERCADONA_FIRST_PARTY_PHOTOS_AFTER_EAN_REVALIDATION",
            "live_detail_source_url": source_url,
            "live_detail_observed_at": observed_at,
            "previous_latest_raw_run_id": old.get("latest_raw_run_id"),
            "historical_missing_core_fields": old.get("missing_core_fields"),
            "historical_engine_families": old.get("independent_engine_families"),
            "historical_corroborated_fields": old.get("corroborated_fields"),
        }
        products.append(current)
        selected.append({
            "product_id": pid,
            "name": old.get("name"),
            "missing_core_fields": old.get("missing_core_fields"),
            "historical_engine_families": old.get("independent_engine_families"),
            "historical_corroborated_fields": old.get("corroborated_fields"),
            "previous_latest_raw_run_id": old.get("latest_raw_run_id"),
            "ean": canonical_ean,
            "image_url": observed_image_url,
            "perspective": photo.get("perspective"),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "products.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in products),
        encoding="utf-8",
    )
    summary = {
        "target_product_ids": targets,
        "selected_after_live_verification": selected,
        "excluded_after_live_verification": excluded,
        "selection_basis": "strict single-family explicit 3-of-4 bounded canary",
        "historical_partial_values_usable": False,
        "cross_run_value_fusion": False,
        "cross_image_value_fusion": False,
        "fresh_observation_must_recover_all_four": True,
        "fresh_declared_requires_independent_engine_families": 2,
        "fresh_declared_requires_corroborated_fields": 4,
        "acceptance_policy_changed": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "image_guessing": False,
    }
    (output_dir / "selection-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return products, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--residual", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--targets", nargs="+", required=True)
    args = ap.parse_args()
    products, summary = prepare(Path(args.residual), Path(args.out), list(args.targets))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not products:
        raise SystemExit("No canary target passed current EAN/exact-P9 verification; refusing OCR guess")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
