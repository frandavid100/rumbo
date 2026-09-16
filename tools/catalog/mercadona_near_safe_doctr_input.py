from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
VALID_BASIS = {"100_g", "100_ml"}


def _token(value: Any) -> str:
    return str(value or "").strip()


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    Path(path).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def select_near_safe_rows(rows: list[dict[str, Any]], *, limit: int = 8) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    rejected: dict[str, list[str]] = {}

    for row in rows:
        pid = _token(row.get("product_id"))
        reasons: list[str] = []
        values = row.get("diagnostic_candidate_values")
        corroborated = int(row.get("corroborated_fields") or 0)
        families = int(row.get("independent_engine_families") or 0)

        if row.get("canonical_status") != "REVIEW":
            reasons.append("NOT_REVIEW")
        if not isinstance(values, dict) or any(values.get(field) is None for field in CORE):
            reasons.append("INCOMPLETE_CORE_VALUES")
        if corroborated not in {1, 2, 3}:
            reasons.append("NOT_ONE_TO_THREE_OF_FOUR")
        if families < 2:
            reasons.append("INSUFFICIENT_ENGINE_FAMILIES")
        if row.get("basis") not in VALID_BASIS:
            reasons.append("NO_EXPLICIT_PER_100_BASIS")
        if row.get("safety_blockers"):
            reasons.append("SAFETY_BLOCKED")
        if not _token(row.get("ean")):
            reasons.append("MISSING_EAN")
        if not _token(row.get("image_url")):
            reasons.append("MISSING_IMAGE_URL")
        if not pid:
            reasons.append("MISSING_PRODUCT_ID")

        if reasons:
            if pid:
                rejected[pid] = reasons
            continue
        eligible.append(dict(row))

    eligible.sort(
        key=lambda row: (
            -int(row.get("corroborated_fields") or 0),
            -int(row.get("independent_engine_families") or 0),
            -float(row.get("confidence") or 0.0),
            _token(row.get("product_id")),
        )
    )
    selected = eligible[: max(0, limit)]
    summary = {
        "selection_policy": "CURRENT_COMPLETE_CLEAN_REVIEW_WITH_EXPLICIT_PER_100_BASIS_AND_EXACT_EAN_IMAGE_ANCHORS; PRIORITIZE_3_OF_4_THEN_2_OF_4_THEN_1_OF_4; ACCEPTANCE_THRESHOLDS_UNCHANGED",
        "input_rows": len(rows),
        "eligible": len(eligible),
        "selected": len(selected),
        "selected_product_ids": [_token(row.get("product_id")) for row in selected],
        "selected_corroboration": {
            _token(row.get("product_id")): int(row.get("corroborated_fields") or 0)
            for row in selected
        },
        "rejected": rejected,
        "acceptance_policy_changed": False,
        "new_independent_ocr_family": "doctr",
    }
    return selected, summary


def build_live_inputs(
    selected: list[dict[str, Any]],
    details: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_pid = {_token(row.get("product_id")): row for row in details if _token(row.get("product_id"))}
    accepted: list[dict[str, Any]] = []
    missing_current: list[str] = []
    missing_current_ean: list[str] = []
    reassigned_product_ids: list[str] = []
    unmatched_current_photo: list[str] = []

    for anchor in selected:
        pid = _token(anchor.get("product_id"))
        current = by_pid.get(pid)
        if current is None:
            missing_current.append(pid)
            continue

        anchor_ean = _token(anchor.get("ean"))
        current_ean = _token(current.get("ean"))
        if not current_ean:
            missing_current_ean.append(pid)
            continue
        if current_ean != anchor_ean:
            reassigned_product_ids.append(pid)
            continue

        image_url = _token(anchor.get("image_url"))
        photos = current.get("photos") if isinstance(current.get("photos"), list) else []
        match = next(
            (
                (index, photo)
                for index, photo in enumerate(photos)
                if isinstance(photo, dict) and _token(photo.get("zoom")) == image_url
            ),
            None,
        )
        if match is None:
            unmatched_current_photo.append(pid)
            continue

        image_index, photo = match
        routed_photo = dict(photo)
        actual_perspective = routed_photo.get("perspective")
        # The OCR worker routes exactly the already-audited image URL. Setting the
        # routing perspective to 9 is metadata for the worker, not a replacement
        # of the image; the original perspective is retained below for audit.
        routed_photo["perspective"] = 9
        candidate = dict(current)
        candidate["photos"] = [routed_photo]
        candidate["_near_safe_anchor"] = {
            "canonical_ean": anchor_ean,
            "current_ean": current_ean,
            "image_url": image_url,
            "current_image_index": image_index,
            "current_image_perspective": actual_perspective,
            "identity_basis": "EXACT_CURRENT_EAN_MATCH",
            "image_basis": "EXACT_CURRENT_FIRST_PARTY_IMAGE_URL_MATCH",
            "canonical_status": anchor.get("canonical_status"),
            "canonical_values": anchor.get("diagnostic_candidate_values"),
            "canonical_corroborated_fields": anchor.get("corroborated_fields"),
            "canonical_engine_families": anchor.get("independent_engine_families"),
            "canonical_latest_raw_run_id": anchor.get("latest_raw_run_id"),
        }
        accepted.append(candidate)

    accepted.sort(key=lambda row: _token(row.get("product_id")))
    summary = {
        "selected": len(selected),
        "accepted_exact_current_identity_and_image": len(accepted),
        "accepted_product_ids": [_token(row.get("product_id")) for row in accepted],
        "missing_current": sorted(set(missing_current)),
        "missing_current_ean": sorted(set(missing_current_ean)),
        "reassigned_product_ids": sorted(set(reassigned_product_ids)),
        "unmatched_current_first_party_photo": sorted(set(unmatched_current_photo)),
        "identity_policy": "PRODUCT_ID_IS_LOOKUP_ONLY; EXACT_NONEMPTY_ANCHOR_EAN_EQUALS_CURRENT_FIRST_PARTY_EAN_REQUIRED",
        "image_policy": "EXACT_ANCHOR_IMAGE_URL_MUST_STILL_EXIST_IN_CURRENT_FIRST_PARTY_PRODUCT_PHOTOS",
        "acceptance_policy_changed": False,
    }
    return accepted, summary


def command_select(args: argparse.Namespace) -> int:
    rows = _load_jsonl(args.diagnostic)
    selected, summary = select_near_safe_rows(rows, limit=args.limit)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "selected.jsonl", selected)
    _write_jsonl(
        out / "inventory.jsonl",
        [{"product_id": _token(row.get("product_id"))} for row in selected],
    )
    (out / "selection-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if selected else 2


def command_live(args: argparse.Namespace) -> int:
    selected = _load_jsonl(args.selected)
    details = _load_jsonl(args.details)
    accepted, summary = build_live_inputs(selected, details)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with_ingredients = [row for row in accepted if row.get("ingredients")]
    without_ingredients = [row for row in accepted if not row.get("ingredients")]
    _write_jsonl(out / "with-ingredients.jsonl", with_ingredients)
    _write_jsonl(out / "without-ingredients.jsonl", without_ingredients)
    (out / "live-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if accepted else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    select = sub.add_parser("select")
    select.add_argument("--diagnostic", required=True)
    select.add_argument("--out", required=True)
    select.add_argument("--limit", type=int, default=8)
    select.set_defaults(func=command_select)

    live = sub.add_parser("live")
    live.add_argument("--selected", required=True)
    live.add_argument("--details", required=True)
    live.add_argument("--out", required=True)
    live.set_defaults(func=command_live)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
