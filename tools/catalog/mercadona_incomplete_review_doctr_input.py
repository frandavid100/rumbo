from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from audit_mercadona_current_review_failure_modes import (
    EVIDENCE,
    EXPLICIT_BASES,
    _best_snapshot,
    _blockers,
    _candidate_payload,
    _collect_reason_strings,
    _core_present,
    _load_rows,
    _run_id,
)
from summarize_mercadona_ocr_run_union import VALID, canonical_exclusion_reason

CORE_FIELDS = ("calories", "protein_g", "carbohydrate_g", "fat_g")


def _token(value: Any) -> str:
    return str(value or "").strip()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def select_incomplete_review_rows(
    root: Path,
    run_union_summary: dict[str, Any],
    *,
    limit: int = 24,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected_ids = {
        str(value)
        for value in run_union_summary.get("latest_status_product_ids", {}).get("REVIEW", [])
    }
    expected_count = int(
        run_union_summary.get("latest_status_counts", {}).get("REVIEW", len(expected_ids))
    )
    if expected_count != len(expected_ids):
        raise ValueError(
            f"run-union REVIEW count/id mismatch: count={expected_count}, ids={len(expected_ids)}"
        )

    by_product_run: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    excluded_derived = Counter()
    for path in sorted(root.rglob("*.jsonl")):
        run_id = _run_id(path, root)
        if run_id is None:
            continue
        for row in _load_rows(path):
            product_id = _token(row.get("product_id"))
            status = _token(row.get("status"))
            if (
                not product_id
                or product_id not in expected_ids
                or status not in VALID
                or row.get("evidence_level") != EVIDENCE
            ):
                continue
            reason = canonical_exclusion_reason(row)
            if reason:
                excluded_derived[reason] += 1
                continue
            by_product_run[product_id][run_id].append(row)

    missing_latest_raw = sorted(expected_ids - set(by_product_run))
    if missing_latest_raw:
        raise ValueError(
            f"missing latest raw rows for {len(missing_latest_raw)} expected REVIEW products: "
            f"{missing_latest_raw[:10]}"
        )

    eligible: list[dict[str, Any]] = []
    rejection_counts = Counter()
    rejected_examples: dict[str, list[str]] = {}

    for product_id in sorted(expected_ids):
        by_run = by_product_run[product_id]
        latest_run = max(by_run)
        rows = by_run[latest_run]
        statuses = {_token(row.get("status")) for row in rows}
        if statuses != {"REVIEW"}:
            raise ValueError(
                f"latest raw status disagrees with canonical REVIEW for {product_id}: "
                f"run={latest_run}, statuses={sorted(statuses)}"
            )

        snapshot = _best_snapshot(rows)
        nutrition = snapshot.get("nutrition")
        reasons = sorted(
            {
                reason
                for row in rows
                for reason in _collect_reason_strings(row)
                if reason.strip()
            }
        )
        blockers = _blockers(reasons)
        present = _core_present(nutrition)
        corroborated = int(snapshot.get("corroborated_fields") or 0)
        families = int(snapshot.get("independent_engine_families") or 0)
        basis = snapshot.get("basis")
        missing_fields = [
            field
            for field in CORE_FIELDS
            if not isinstance(nutrition, dict) or nutrition.get(field) is None
        ]

        payload = _candidate_payload(
            product_id,
            latest_run,
            rows,
            snapshot,
            reasons,
            blockers,
        )
        payload["present_core_fields"] = present
        payload["missing_core_fields"] = missing_fields
        payload["frontier_kind"] = "INCOMPLETE_EXACTLY_THREE_CORE_FIELDS_WITH_THREE_CORROBORATED"

        rejection_reasons: list[str] = []
        if present != 3 or len(missing_fields) != 1:
            rejection_reasons.append("NOT_EXACTLY_THREE_CORE_FIELDS")
        if corroborated < 3:
            rejection_reasons.append("LESS_THAN_THREE_CORROBORATED_FIELDS")
        if families < 2:
            rejection_reasons.append("INSUFFICIENT_ENGINE_FAMILIES")
        if basis not in EXPLICIT_BASES:
            rejection_reasons.append("NO_EXPLICIT_PER_100_BASIS")
        if blockers:
            rejection_reasons.append("SAFETY_BLOCKED")
        if not _token(payload.get("ean")):
            rejection_reasons.append("MISSING_EAN")
        if not _token(payload.get("image_url")):
            rejection_reasons.append("MISSING_IMAGE_URL")

        if rejection_reasons:
            rejection_counts.update(rejection_reasons)
            if len(rejected_examples) < 24:
                rejected_examples[product_id] = rejection_reasons
            continue
        eligible.append(payload)

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
        "selection_policy": (
            "LATEST_RAW_LIVE_REVIEW_ONLY; EXACTLY_THREE_CORE_VALUES_PRESENT; AT_LEAST_THREE_"
            "CORROBORATED_FIELDS; EXPLICIT_100G_100ML_BASIS; AT_LEAST_TWO_INDEPENDENT_OCR_"
            "FAMILIES; NO_HARD_OCR_CONFLICT; NO_ENERGY_MACRO_INCOHERENCE; NO_AMBIGUOUS_TABLE; "
            "EAN_AND_FIRST_PARTY_IMAGE_ANCHORS_REQUIRED; ACCEPTANCE_THRESHOLDS_UNCHANGED"
        ),
        "latest_review_products": expected_count,
        "eligible_incomplete_frontier": len(eligible),
        "selected": len(selected),
        "selected_product_ids": [_token(row.get("product_id")) for row in selected],
        "selected_missing_core_fields": {
            _token(row.get("product_id")): row.get("missing_core_fields") for row in selected
        },
        "selected_latest_raw_run_ids": {
            _token(row.get("product_id")): row.get("latest_raw_run_id") for row in selected
        },
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "rejected_examples": rejected_examples,
        "excluded_derived_rows": dict(sorted(excluded_derived.items())),
        "acceptance_policy_changed": False,
        "cross_run_value_fusion_allowed": False,
        "missing_values_inferred": False,
        "new_independent_ocr_family": "doctr",
    }
    return selected, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--run-union-summary", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=24)
    args = parser.parse_args()

    summary = json.loads(Path(args.run_union_summary).read_text(encoding="utf-8"))
    selected, selection_summary = select_incomplete_review_rows(
        Path(args.root), summary, limit=args.limit
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "selected.jsonl", selected)
    _write_jsonl(
        out / "inventory.jsonl",
        [{"product_id": _token(row.get("product_id"))} for row in selected],
    )
    (out / "selection-summary.json").write_text(
        json.dumps(selection_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(selection_summary, ensure_ascii=False, sort_keys=True))
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())
