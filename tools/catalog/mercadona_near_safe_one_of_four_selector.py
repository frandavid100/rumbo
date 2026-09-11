from __future__ import annotations

import argparse
import json
from pathlib import Path

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
DEFAULT_LIMIT = 16


def build_one_of_four_candidates(
    diagnostic_path: str | Path,
    product_path: str | Path,
    *,
    limit: int = DEFAULT_LIMIT,
) -> tuple[list[dict], dict]:
    """Select a bounded exact-image p9 cohort from clean canonical 1/4 REVIEW rows.

    The canonical tuple is used only to select a difficult cohort. The subsequent
    OCR run is a new raw-live observation over the exact current first-party image
    and must satisfy the normal DECLARED contract independently. No historical
    value is fused into the new observation.
    """
    targets: dict[str, dict] = {}
    for line in Path(diagnostic_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        pid = str(row.get("product_id") or "")
        values = row.get("diagnostic_candidate_values") or {}
        if (
            row.get("canonical_status") == "REVIEW"
            and int(row.get("corroborated_fields") or 0) == 1
            and int(row.get("independent_engine_families") or 0) >= 2
            and row.get("basis") in {"100_g", "100_ml"}
            and all(values.get(field) is not None for field in CORE)
            and not (row.get("safety_blockers") or [])
            and pid
            and row.get("image_url")
        ):
            targets[pid] = row

    candidates: list[dict] = []
    unmatched_current_p9: list[str] = []
    for line in Path(product_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        pid = str(row.get("product_id") or "")
        diagnostic = targets.get(pid)
        if diagnostic is None:
            continue

        image_url = str(diagnostic["image_url"])
        photos = row.get("photos") if isinstance(row.get("photos"), list) else []
        matches = [
            (index, photo)
            for index, photo in enumerate(photos)
            if (
                isinstance(photo, dict)
                and str(photo.get("zoom") or "") == image_url
                and int(photo.get("perspective") or 0) == 9
            )
        ]
        if len(matches) != 1:
            unmatched_current_p9.append(pid)
            continue

        image_index, photo = matches[0]
        candidate = dict(row)
        candidate["photos"] = [dict(photo)]
        candidate["_near_safe_image_meta"] = {
            "image_url": image_url,
            "image_index": image_index,
            "perspective": 9,
            "canonical_latest_raw_run_id": diagnostic.get("latest_raw_run_id"),
            "canonical_corroborated_fields": 1,
            "canonical_engine_families": diagnostic.get("independent_engine_families"),
            "canonical_confidence": diagnostic.get("confidence"),
        }
        candidates.append(candidate)

    candidates.sort(
        key=lambda row: (
            0 if row.get("ingredients") else 1,
            -int((row.get("_near_safe_image_meta") or {}).get("canonical_engine_families") or 0),
            -float((row.get("_near_safe_image_meta") or {}).get("canonical_confidence") or 0.0),
            str(row.get("product_id") or ""),
        )
    )
    selected = candidates[: max(0, limit)] if limit else candidates
    summary = {
        "pilot_limit": limit,
        "canonical_one_of_four_targets": len(targets),
        "current_exact_first_party_p9_targets": len(candidates),
        "selected": len(selected),
        "selected_with_structured_ingredients": sum(bool(row.get("ingredients")) for row in selected),
        "selected_without_structured_ingredients": sum(not bool(row.get("ingredients")) for row in selected),
        "selected_product_ids": [str(row.get("product_id")) for row in selected],
        "unmatched_current_first_party_p9": sorted(unmatched_current_p9),
        "selection_policy": (
            "CURRENT_CLEAN_CANONICAL_1_OF_4_REVIEW_EXACT_CURRENT_FIRST_PARTY_PERSPECTIVE_9_IMAGE; "
            "NEW_RAW_LIVE_OBSERVATION_WITH_DOCTR_AS_ADDITIONAL_INDEPENDENT_OCR_FAMILY"
        ),
        "observation_policy": "CURRENT_EXACT_P9_IMAGE_IS_REPROCESSED_AS_A_NEW_RAW_LIVE_OBSERVATION",
        "cross_run_value_fusion": False,
        "current_observation_must_satisfy_declared_contract_independently": True,
        "new_independent_ocr_family": "doctr",
        "acceptance_policy_changed": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "structured_api_macros_claimed": False,
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "source": "MERCADONA_FIRST_PARTY/label image",
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    return selected, summary


def write_selection(rows: list[dict], summary: dict, out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with_ingredients = [row for row in rows if row.get("ingredients")]
    without_ingredients = [row for row in rows if not row.get("ingredients")]

    def write_jsonl(path: Path, values: list[dict]) -> None:
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values),
            encoding="utf-8",
        )

    write_jsonl(out / "one-of-four-with-ingredients.jsonl", with_ingredients)
    write_jsonl(out / "one-of-four-without-ingredients.jsonl", without_ingredients)
    (out / "selection-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", required=True)
    parser.add_argument("--products", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()

    selected, summary = build_one_of_four_candidates(
        args.diagnostic, args.products, limit=args.limit
    )
    write_selection(selected, summary, args.out)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())
