from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from summarize_mercadona_ocr_run_union import canonical_exclusion_reason

EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"
CORE_SOURCE = "MERCADONA_FIRST_PARTY"
CORE_RECORD_KIND = "label image"


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def select_targets(summary: dict[str, Any]) -> dict[str, Any]:
    current_review = {
        str(value)
        for value in summary.get("latest_status_product_ids", {}).get("REVIEW", [])
    }
    transition = summary.get("declared_to_review_transition_audit") or {}
    non_contradictory = {
        str(value)
        for value in transition.get("non_contradictory_review_product_ids") or []
    }
    targets = sorted(current_review & non_contradictory, key=lambda value: (len(value), value))
    if not targets:
        raise ValueError("No current non-contradictory REVIEW regressions remain")

    excluded_runs = {
        int(value) for value in summary.get("canonical_excluded_run_ids") or []
    }
    target_set = set(targets)
    latest_raw_run_by_product: dict[str, int] = {}
    for run in summary.get("runs") or []:
        run_id = int(run["run_id"])
        if run_id in excluded_runs:
            continue
        seen = {str(value) for value in run.get("new_product_ids") or []}
        seen.update(str(value) for value in run.get("overlap_product_ids") or [])
        for product_id in target_set & seen:
            latest_raw_run_by_product[product_id] = run_id

    missing = sorted(target_set - set(latest_raw_run_by_product))
    if missing:
        raise ValueError(f"Could not resolve a canonical-eligible raw run for: {missing}")

    return {
        "selection": "CURRENT_REVIEW_AFTER_HISTORICAL_DECLARED_NON_CONTRADICTORY_ONLY",
        "target_count": len(targets),
        "product_ids": targets,
        "latest_raw_run_by_product": latest_raw_run_by_product,
        "canonical_excluded_run_count": len(excluded_runs),
        "safety_blocking_products_excluded": True,
        "derived_or_replay_runs_excluded": True,
        "cross_run_value_fusion": False,
        "acceptance_policy_changed": False,
        "evidence_level": EVIDENCE,
        "source": f"{CORE_SOURCE}/{CORE_RECORD_KIND}",
        "redistribution_allowed": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }


def _iter_jsonl(root: Path):
    for path in sorted(root.rglob("*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield path, row


def recover_anchors(selection: dict[str, Any], raw_root: str | Path) -> dict[str, Any]:
    run_by_product = {
        str(product_id): int(run_id)
        for product_id, run_id in selection["latest_raw_run_by_product"].items()
    }
    rows_by_product: dict[str, list[dict[str, Any]]] = {
        product_id: [] for product_id in run_by_product
    }
    root = Path(raw_root)
    for path, row in _iter_jsonl(root):
        product_id = str(row.get("product_id") or "")
        expected_run = run_by_product.get(product_id)
        if expected_run is None:
            continue
        first_part = path.relative_to(root).parts[0] if path.relative_to(root).parts else ""
        run_token = first_part.split("-", 1)[0]
        if not run_token.isdigit() or int(run_token) != expected_run:
            continue
        if row.get("status") != "REVIEW":
            continue
        if row.get("evidence_level") != EVIDENCE:
            continue
        if canonical_exclusion_reason(row):
            continue
        rows_by_product[product_id].append(row)

    anchors: dict[str, dict[str, Any]] = {}
    skipped: dict[str, dict[str, Any]] = {}
    for product_id, run_id in sorted(
        run_by_product.items(), key=lambda item: (len(item[0]), item[0])
    ):
        rows = rows_by_product[product_id]
        pairs = sorted(
            {
                (
                    str(row.get("ean") or "").strip(),
                    str(row.get("image_url") or "").strip(),
                )
                for row in rows
                if str(row.get("ean") or "").strip()
                and str(row.get("image_url") or "").strip()
            }
        )
        if len(pairs) != 1:
            skipped[product_id] = {
                "reason": "LATEST_RAW_ANCHOR_PAIR_NOT_UNIQUE",
                "run_id": run_id,
                "eligible_rows": len(rows),
                "pairs": pairs,
            }
            continue
        ean, image_url = pairs[0]
        representative = rows[0]
        anchors[product_id] = {
            "product_id": product_id,
            "ean": ean,
            "image_url": image_url,
            "latest_raw_run_id": run_id,
            "name": representative.get("name"),
        }

    if not anchors:
        raise ValueError(f"No unambiguous latest raw anchors recovered; skipped={skipped}")
    return {"anchors": anchors, "skipped": skipped}


def build_live_input(
    anchor_doc: dict[str, Any], details_path: str | Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    anchors = anchor_doc.get("anchors") or {}
    selected: list[dict[str, Any]] = []
    missing_current_ean: list[str] = []
    reassigned: list[str] = []
    unmatched_p9: list[str] = []

    for line in Path(details_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        product = json.loads(line)
        product_id = str(product.get("product_id") or "").strip()
        anchor = anchors.get(product_id)
        if anchor is None:
            continue
        current_ean = str(product.get("ean") or "").strip()
        if not current_ean:
            missing_current_ean.append(product_id)
            continue
        if current_ean != anchor["ean"]:
            reassigned.append(product_id)
            continue
        photos = product.get("photos") if isinstance(product.get("photos"), list) else []
        matches = [
            (index, photo)
            for index, photo in enumerate(photos)
            if isinstance(photo, dict)
            and str(photo.get("perspective") or "") == "9"
            and str(photo.get("zoom") or "") == anchor["image_url"]
        ]
        if len(matches) != 1:
            unmatched_p9.append(product_id)
            continue
        image_index, photo = matches[0]
        candidate = dict(product)
        candidate["photos"] = [dict(photo)]
        candidate["_bounded_doctr_meta"] = {
            "canonical_ean": anchor["ean"],
            "current_ean": current_ean,
            "image_url": anchor["image_url"],
            "image_index": image_index,
            "perspective": 9,
            "latest_raw_run_id": anchor["latest_raw_run_id"],
            "identity_basis": "EXACT_LATEST_RAW_EAN_EQUALS_CURRENT_FIRST_PARTY_EAN",
            "image_basis": "EXACT_LATEST_RAW_IMAGE_URL_EQUALS_CURRENT_FIRST_PARTY_PERSPECTIVE_9_URL",
        }
        selected.append(candidate)

    selected.sort(
        key=lambda row: (0 if row.get("ingredients") else 1, str(row.get("product_id") or ""))
    )
    if not selected:
        raise ValueError(
            "No exact-EAN exact-current-p9 regression target remains; "
            f"missing_ean={missing_current_ean} reassigned={reassigned} "
            f"unmatched_p9={unmatched_p9}"
        )
    summary = {
        "historical_inventory_products": 4280,
        "anchored_regressions": len(anchors),
        "selected": len(selected),
        "selected_product_ids": [str(row.get("product_id")) for row in selected],
        "selected_with_structured_ingredients": sum(bool(row.get("ingredients")) for row in selected),
        "selected_without_structured_ingredients": sum(not bool(row.get("ingredients")) for row in selected),
        "missing_current_ean": sorted(set(missing_current_ean)),
        "reassigned_current_product_ids": sorted(set(reassigned)),
        "unmatched_current_first_party_p9": sorted(set(unmatched_p9)),
        "selection_policy": "CURRENT_HISTORICAL_DECLARED_TO_REVIEW_NON_CONTRADICTORY; CANONICAL_EXCLUDED_RUNS_IGNORED; EXACT_LATEST_RAW_EAN; EXACT_CURRENT_FIRST_PARTY_EAN; EXACT_SAME_PERSPECTIVE_9_IMAGE_URL",
        "new_independent_ocr_family": "doctr",
        "cross_run_value_fusion": False,
        "current_observation_must_satisfy_declared_contract_independently": True,
        "acceptance_policy_changed": False,
        "evidence_level": EVIDENCE,
        "source": f"{CORE_SOURCE}/{CORE_RECORD_KIND}",
        "redistribution_allowed": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    return selected, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    select = sub.add_parser("select")
    select.add_argument("--summary", required=True)
    select.add_argument("--out", required=True)

    anchors = sub.add_parser("anchors")
    anchors.add_argument("--selection", required=True)
    anchors.add_argument("--raw-root", required=True)
    anchors.add_argument("--out", required=True)

    live = sub.add_parser("live")
    live.add_argument("--anchors", required=True)
    live.add_argument("--details", required=True)
    live.add_argument("--out", required=True)

    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.command == "select":
        payload = select_targets(_load_json(args.summary))
        _write_json(out / "selection.json", payload)
        (out / "run-ids.txt").write_text(
            "".join(
                f"{run_id}\n"
                for run_id in sorted(set(payload["latest_raw_run_by_product"].values()))
            ),
            encoding="utf-8",
        )
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "anchors":
        payload = recover_anchors(_load_json(args.selection), args.raw_root)
        _write_json(out / "anchors.json", payload)
        (out / "inventory.jsonl").write_text(
            "".join(
                json.dumps({"product_id": product_id}, sort_keys=True) + "\n"
                for product_id in payload["anchors"]
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "anchored": len(payload["anchors"]),
                    "skipped": len(payload["skipped"]),
                    "anchored_product_ids": list(payload["anchors"]),
                },
                sort_keys=True,
            )
        )
        return 0

    selected, summary = build_live_input(_load_json(args.anchors), args.details)
    with_ingredients = [row for row in selected if row.get("ingredients")]
    without_ingredients = [row for row in selected if not row.get("ingredients")]
    for name, rows in (
        ("with-ingredients.jsonl", with_ingredients),
        ("without-ingredients.jsonl", without_ingredients),
    ):
        (out / name).write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    _write_json(out / "selection-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
