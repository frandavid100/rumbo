from __future__ import annotations

"""Prepare a bounded current-image OCR canary from strict single-family 3/4 REVIEW rows.

Historical OCR nutrition is used only to select candidates. Output product rows contain
current first-party metadata and exactly one explicitly selected live image; no historical
nutrition value is copied into the OCR input.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from mercadona_first_party_details import _get_json, normalize, _now

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
PRESELECTED_FLAG = "_preselected_current_first_party_label_image"
P9_IDENTITY_RULE = "EXACT_CURRENT_UNIQUE_P9"
ALT_IDENTITY_RULE = "EXACT_CURRENT_ONLY_NON_P9_ZOOM_WITHOUT_UNIQUE_P9"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _static_candidate(row: dict[str, Any]) -> bool:
    values = row.get("diagnostic_candidate_values") or {}
    missing = [field for field in CORE if values.get(field) is None]
    return bool(
        row.get("canonical_status") == "REVIEW"
        and row.get("basis") in {"100_g", "100_ml"}
        and not (row.get("safety_blockers") or [])
        and len(missing) == 1
        and missing == (row.get("missing_core_fields") or [])
        and int(row.get("independent_engine_families") or 0) == 1
        and str(row.get("ean") or "").strip()
        and str(row.get("image_url") or "").strip()
    )


def prepare(
    residual_path: Path,
    output_dir: Path,
    targets: list[str] | None = None,
    limit_selected: int = 0,
    allow_changed_current_p9: bool = False,
    exclude_targets: list[str] | None = None,
    allow_unique_current_non_p9: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if allow_changed_current_p9 and allow_unique_current_non_p9:
        raise ValueError("changed-current-P9 and unique-current-non-P9 modes are mutually exclusive")

    rows = _load_jsonl(residual_path)
    by_id = {str(row.get("product_id") or ""): row for row in rows}
    explicit_targets = [str(pid) for pid in (targets or []) if str(pid).strip()]
    excluded_target_ids = {str(pid).strip() for pid in (exclude_targets or []) if str(pid).strip()}

    products: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    if explicit_targets:
        candidate_ids = explicit_targets
        selection_mode = "explicit_targets"
    else:
        # Preserve the strict auditor's deterministic residual order. The canary is bounded
        # by successful current-image selections, not by the first N historical rows, so a
        # stale/disappeared image does not prevent trying the next still-current candidate.
        candidate_ids = [str(row.get("product_id") or "") for row in rows if str(row.get("product_id") or "")]
        selection_mode = "dynamic_strict_residual"

    live_attempted = 0
    static_candidates = 0
    stopped_after_limit = False

    for candidate_index, pid in enumerate(candidate_ids):
        if limit_selected > 0 and len(products) >= limit_selected:
            stopped_after_limit = True
            break

        if pid in excluded_target_ids:
            excluded.append({"product_id": pid, "reason": "EXCLUDED_PREVIOUSLY_ATTEMPTED_CURRENT_IMAGE_CANARY"})
            continue

        old = by_id.get(pid)
        if old is None:
            excluded.append({"product_id": pid, "reason": "NO_LONGER_IN_STRICT_3_OF_4_RESIDUAL"})
            continue

        if not _static_candidate(old):
            excluded.append({"product_id": pid, "reason": "NO_LONGER_SINGLE_FAMILY_EXPLICIT_3_OF_4"})
            continue
        static_candidates += 1

        canonical_ean = str(old["ean"]).strip()
        observed_image_url = str(old["image_url"]).strip()
        observed_at = _now()
        live_attempted += 1
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
        if allow_unique_current_non_p9:
            current_p9 = [
                (index, photo)
                for index, photo in enumerate(photos)
                if isinstance(photo, dict)
                and str(photo.get("perspective") or "") == "9"
                and str(photo.get("zoom") or "").strip()
            ]
            if len(current_p9) == 1:
                excluded.append({
                    "product_id": pid,
                    "reason": "UNIQUE_CURRENT_P9_EXISTS_USE_P9_ROUTE",
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
                    "current_p9_matches": len(current_p9),
                })
                continue
            image_index, photo = alternatives[0]
            selected_image_url = str(photo.get("zoom") or "").strip()
            if selected_image_url == observed_image_url:
                excluded.append({
                    "product_id": pid,
                    "reason": "CURRENT_NON_P9_EQUALS_HISTORICAL_OCR_IMAGE",
                })
                continue
            matching_current_urls = sum(
                1
                for candidate in photos
                if isinstance(candidate, dict)
                and str(candidate.get("zoom") or "").strip() == selected_image_url
            )
            if matching_current_urls != 1:
                excluded.append({
                    "product_id": pid,
                    "reason": "SELECTED_CURRENT_IMAGE_URL_NOT_UNIQUE",
                    "matches": matching_current_urls,
                })
                continue
            image_selection_basis = (
                "ONLY_CURRENT_FIRST_PARTY_NON_P9_ZOOM_IMAGE_AFTER_EXACT_EAN_REVALIDATION; "
                "NO_UNIQUE_CURRENT_P9; HISTORICAL_OCR_IMAGE_NOT_REUSED; NO_IMAGE_RANKING"
            )
            image_identity_rule = ALT_IDENTITY_RULE
        elif allow_changed_current_p9:
            current_p9 = [
                (index, photo)
                for index, photo in enumerate(photos)
                if isinstance(photo, dict)
                and str(photo.get("perspective") or "") == "9"
                and str(photo.get("zoom") or "").strip()
            ]
            if len(current_p9) != 1:
                excluded.append({
                    "product_id": pid,
                    "reason": "UNIQUE_CURRENT_P9_IMAGE_REQUIRED",
                    "matches": len(current_p9),
                })
                continue
            image_index, photo = current_p9[0]
            selected_image_url = str(photo.get("zoom") or "").strip()
            if selected_image_url == observed_image_url:
                excluded.append({
                    "product_id": pid,
                    "reason": "CURRENT_P9_UNCHANGED_ALREADY_COVERED_BY_EXACT_URL_WAVE",
                })
                continue
            image_selection_basis = (
                "UNIQUE_CURRENT_FIRST_PARTY_PERSPECTIVE_9_IMAGE_AFTER_EXACT_EAN_REVALIDATION; "
                "HISTORICAL_IMAGE_URL_CHANGED_AND_VALUES_NOT_CONSUMED"
            )
            image_identity_rule = P9_IDENTITY_RULE
        else:
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
            selected_image_url = observed_image_url
            image_selection_basis = (
                "EXACT_LATEST_OBSERVED_PERSPECTIVE_9_IMAGE_URL_OCCURS_ONCE_IN_CURRENT_"
                "MERCADONA_FIRST_PARTY_PHOTOS_AFTER_EAN_REVALIDATION"
            )
            image_identity_rule = P9_IDENTITY_RULE

        routed = dict(photo)
        routed[PRESELECTED_FLAG] = True
        current = dict(live)
        current["photos"] = [routed]
        current["_exact_current_image_meta"] = {
            "image_url": selected_image_url,
            "historical_image_url": observed_image_url,
            "historical_image_url_changed": selected_image_url != observed_image_url,
            "current_photo_index": image_index,
            "current_photo_perspective": photo.get("perspective"),
            "image_identity_rule": image_identity_rule,
            "canonical_ean": canonical_ean,
            "current_ean": current_ean,
            "identity_basis": "EXACT_NONEMPTY_CANONICAL_EAN_EQUALS_CURRENT_FIRST_PARTY_EAN",
            "image_selection_basis": image_selection_basis,
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
            "historical_image_url": observed_image_url,
            "image_url": selected_image_url,
            "historical_image_url_changed": selected_image_url != observed_image_url,
            "perspective": photo.get("perspective"),
            "image_identity_rule": image_identity_rule,
            "residual_candidate_index": candidate_index,
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "products.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in products),
        encoding="utf-8",
    )
    if allow_unique_current_non_p9:
        selection_basis = (
            "strict single-family explicit 3-of-4 bounded canary; exact EAN; no unique current P9; exactly one "
            "current first-party non-P9 zoom image; historical OCR image not reused; no image ranking/guessing"
        )
    elif allow_changed_current_p9:
        selection_basis = (
            "strict single-family explicit 3-of-4 bounded canary; exact EAN; exactly one current "
            "first-party P9; current P9 must differ from historical OCR image; historical values never consumed"
        )
    else:
        selection_basis = (
            "strict single-family explicit 3-of-4 bounded canary; exact latest observed P9 must still occur "
            "exactly once in current first-party photos after exact EAN revalidation"
        )
    summary = {
        "selection_mode": selection_mode,
        "requested_target_product_ids": explicit_targets,
        "excluded_previously_attempted_product_ids": sorted(excluded_target_ids),
        "allow_changed_current_p9": allow_changed_current_p9,
        "allow_unique_current_non_p9": allow_unique_current_non_p9,
        "residual_rows": len(rows),
        "candidate_product_ids": candidate_ids,
        "static_candidates_seen_before_stop": static_candidates,
        "live_candidates_attempted": live_attempted,
        "limit_selected": limit_selected,
        "stopped_after_selection_limit": stopped_after_limit,
        "selected_after_live_verification": selected,
        "excluded_after_live_verification": excluded,
        "selection_basis": selection_basis,
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
    ap.add_argument("--targets", nargs="*")
    ap.add_argument("--exclude-targets", nargs="*")
    ap.add_argument(
        "--allow-changed-current-p9",
        action="store_true",
        help="Allow a unique live perspective=9 image only when its URL changed; never consume historical OCR values.",
    )
    ap.add_argument(
        "--allow-unique-current-non-p9",
        action="store_true",
        help=(
            "Allow exactly one live non-P9 zoom image only when no unique current P9 exists; "
            "never consume historical OCR values or rank among multiple images."
        ),
    )
    ap.add_argument(
        "--limit-selected",
        type=int,
        default=0,
        help="Stop after this many candidates pass live EAN/current-image verification; 0 means no limit.",
    )
    args = ap.parse_args()
    if args.limit_selected < 0:
        raise SystemExit("--limit-selected must be >= 0")
    products, summary = prepare(
        Path(args.residual),
        Path(args.out),
        list(args.targets or []),
        args.limit_selected,
        bool(args.allow_changed_current_p9),
        list(args.exclude_targets or []),
        bool(args.allow_unique_current_non_p9),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not products:
        raise SystemExit("No strict residual candidate passed current EAN/current-image verification; refusing OCR guess")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
