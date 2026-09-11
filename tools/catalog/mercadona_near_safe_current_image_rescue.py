from __future__ import annotations

import argparse
import json
from pathlib import Path

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
DEFAULT_LIMIT = 8


def _iter_jsonl(path: str | Path):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def build_current_image_rescue_candidates(
    diagnostic_path: str | Path,
    product_path: str | Path,
    *,
    corroborated_fields: int = 2,
    limit: int = DEFAULT_LIMIT,
) -> tuple[list[dict], dict]:
    """Select clean REVIEW rows whose canonical image was replaced by one current p9 image.

    The replacement image is always treated as a new raw-live observation. Historical
    values from the old canonical image are never fused with OCR from the new image.
    """
    targets: dict[str, dict] = {}
    for row in _iter_jsonl(diagnostic_path):
        pid = str(row.get("product_id") or "")
        values = row.get("diagnostic_candidate_values") or {}
        if (
            row.get("canonical_status") == "REVIEW"
            and int(row.get("corroborated_fields") or 0) == corroborated_fields
            and int(row.get("independent_engine_families") or 0) >= 2
            and row.get("basis") in {"100_g", "100_ml"}
            and all(values.get(field) is not None for field in CORE)
            and not (row.get("safety_blockers") or [])
            and pid
            and row.get("image_url")
        ):
            targets[pid] = row

    candidates: list[dict] = []
    canonical_image_still_current: list[str] = []
    no_current_p9: list[str] = []
    ambiguous_current_p9: list[str] = []
    seen_products: set[str] = set()

    for row in _iter_jsonl(product_path):
        pid = str(row.get("product_id") or "")
        diagnostic = targets.get(pid)
        if diagnostic is None:
            continue
        seen_products.add(pid)

        canonical_image_url = str(diagnostic.get("image_url") or "")
        photos = [
            p for p in (row.get("photos") or [])
            if isinstance(p, dict) and p.get("zoom")
        ]
        if any(str(p.get("zoom") or "") == canonical_image_url for p in photos):
            canonical_image_still_current.append(pid)
            continue

        p9 = [
            (index, p)
            for index, p in enumerate(photos)
            if str(p.get("perspective") or "") == "9"
            and str(p.get("zoom") or "") != canonical_image_url
        ]
        if not p9:
            no_current_p9.append(pid)
            continue
        if len(p9) != 1:
            ambiguous_current_p9.append(pid)
            continue

        image_index, photo = p9[0]
        current_image_url = str(photo.get("zoom") or "")
        routed_photo = dict(photo)
        routed_photo["perspective"] = 9

        candidate = dict(row)
        candidate["photos"] = [routed_photo]
        candidate["_current_image_rescue_meta"] = {
            "canonical_prior_image_url": canonical_image_url,
            "current_image_url": current_image_url,
            "current_photo_index": image_index,
            "current_photo_perspective": photo.get("perspective"),
            "live_detail_source_url": row.get("source_url"),
            "live_detail_observed_at": row.get("observed_at"),
            "canonical_latest_raw_run_id": diagnostic.get("latest_raw_run_id"),
            "canonical_corroborated_fields": diagnostic.get("corroborated_fields"),
            "canonical_engine_families": diagnostic.get("independent_engine_families"),
            "canonical_confidence": diagnostic.get("confidence"),
            "canonical_basis": diagnostic.get("basis"),
            "observation_policy": "CURRENT_IMAGE_IS_A_NEW_RAW_LIVE_OBSERVATION",
            "cross_image_fusion": False,
            "current_observation_must_satisfy_declared_contract_independently": True,
            "acceptance_policy_changed": False,
        }
        candidates.append(candidate)

    missing_live_product = sorted(set(targets) - seen_products)
    candidates.sort(
        key=lambda row: (
            0 if row.get("ingredients") else 1,
            -int((row.get("_current_image_rescue_meta") or {}).get("canonical_engine_families") or 0),
            -float((row.get("_current_image_rescue_meta") or {}).get("canonical_confidence") or 0.0),
            str(row.get("product_id") or ""),
        )
    )
    selected = candidates if limit <= 0 else candidates[:limit]

    summary = {
        "canonical_requested_corroborated_fields": corroborated_fields,
        "canonical_targets": len(targets),
        "current_replacement_p9_candidates": len(candidates),
        "selected": len(selected),
        "selected_product_ids": [str(row.get("product_id") or "") for row in selected],
        "selected_with_structured_ingredients": sum(bool(row.get("ingredients")) for row in selected),
        "selected_without_structured_ingredients": sum(not bool(row.get("ingredients")) for row in selected),
        "canonical_image_still_current": sorted(canonical_image_still_current),
        "no_current_p9": sorted(no_current_p9),
        "ambiguous_current_p9": sorted(ambiguous_current_p9),
        "missing_live_product": missing_live_product,
        "selection_policy": (
            "CLEAN_CANONICAL_REVIEW_WITH_REPLACED_IMAGE; EXACT_CANONICAL_IMAGE_ABSENT; "
            "EXACTLY_ONE_DISTINCT_CURRENT_FIRST_PARTY_PERSPECTIVE_9_IMAGE"
        ),
        "observation_policy": "CURRENT_IMAGE_IS_A_NEW_RAW_LIVE_OBSERVATION",
        "cross_image_fusion": False,
        "current_observation_must_satisfy_declared_contract_independently": True,
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


def _write_jsonl(path: str | Path, rows: list[dict]) -> None:
    Path(path).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diagnostic", required=True)
    ap.add_argument("--products", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--corroborated-fields", type=int, default=2)
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = ap.parse_args()

    selected, summary = build_current_image_rescue_candidates(
        args.diagnostic,
        args.products,
        corroborated_fields=args.corroborated_fields,
        limit=args.limit,
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "with-ingredients.jsonl", [r for r in selected if r.get("ingredients")])
    _write_jsonl(out / "without-ingredients.jsonl", [r for r in selected if not r.get("ingredients")])
    (out / "selection-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
