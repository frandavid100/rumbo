from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

VALID = {"DECLARED", "REVIEW", "NO_VISUAL_REGION", "ERROR"}
EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"
NUTRITION_FIELDS = ("calories", "protein_g", "carbohydrate_g", "fat_g")


def load_run_names(tsv: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    if not tsv.exists():
        return out
    for line in tsv.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out[parts[0]].add(parts[1])
    return out


def complete_nutrition(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    out: dict[str, float] = {}
    for field in NUTRITION_FIELDS:
        item = value.get(field)
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        item = float(item)
        if not math.isfinite(item):
            return None
        out[field] = item
    return out


def nutrition_key(value: dict[str, float]) -> tuple[float, ...]:
    return tuple(value[field] for field in NUTRITION_FIELDS)


def is_canonical_status_row(row: dict[str, Any]) -> bool:
    """Return whether a persisted OCR row may update canonical current status.

    Replay artifacts wrap an older live OCR row and attach a ``replay`` diagnostic
    containing the parser/ensemble result under test. Their top-level ``status``
    and ``nutrition`` deliberately remain the source cut's historical values.
    Treating such wrappers as a newer live observation can therefore roll a later
    targeted OCR result backwards merely because a parser regression workflow ran.

    Replays remain part of the auditable processed-id union, but never update the
    canonical state. In particular, replay REVIEW->DECLARED candidates are not
    promoted here and replay wrappers cannot demote newer live DECLARED evidence.
    """
    return not isinstance(row.get("replay"), dict)


def reconcile_latest_observations(
    observations: Iterable[tuple[int, str, str, Any]],
) -> dict[str, dict[str, Any]]:
    """Return one conservative latest persisted live OCR state per product.

    A later live OCR run supersedes an older live run for status accounting.
    Within the same latest run, however, any status disagreement is treated as
    non-usable. A latest DECLARED product is usable only when every strict
    DECLARED observation in that run carries a complete four-field nutrition
    payload and all complete payloads agree exactly. Older DECLARED nutrition is
    never inherited by a later REVIEW, ERROR or NO_VISUAL_REGION observation.
    """
    grouped: dict[str, dict[int, list[tuple[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for run_id, product_id, status, nutrition in observations:
        if status not in VALID:
            continue
        grouped[str(product_id)][int(run_id)].append((status, nutrition))

    result: dict[str, dict[str, Any]] = {}
    for product_id, by_run in grouped.items():
        latest_run = max(by_run)
        values = by_run[latest_run]
        statuses = {status for status, _ in values}
        if len(statuses) != 1:
            result[product_id] = {
                "latest_run_id": latest_run,
                "status": "MULTIPLE_STATUSES_LATEST_RUN",
                "latest_run_statuses": sorted(statuses),
                "usable_complete": False,
                "nutrition": None,
                "nutrition_issue": "MULTIPLE_STATUSES_LATEST_RUN",
            }
            continue

        status = next(iter(statuses))
        if status != "DECLARED":
            result[product_id] = {
                "latest_run_id": latest_run,
                "status": status,
                "latest_run_statuses": [status],
                "usable_complete": False,
                "nutrition": None,
                "nutrition_issue": None,
            }
            continue

        normalized = [complete_nutrition(nutrition) for _, nutrition in values]
        if any(item is None for item in normalized):
            result[product_id] = {
                "latest_run_id": latest_run,
                "status": "DECLARED",
                "latest_run_statuses": ["DECLARED"],
                "usable_complete": False,
                "nutrition": None,
                "nutrition_issue": "INCOMPLETE_DECLARED_NUTRITION_LATEST_RUN",
            }
            continue

        complete_values = [item for item in normalized if item is not None]
        unique = {nutrition_key(item) for item in complete_values}
        if len(unique) != 1:
            result[product_id] = {
                "latest_run_id": latest_run,
                "status": "DECLARED",
                "latest_run_statuses": ["DECLARED"],
                "usable_complete": False,
                "nutrition": None,
                "nutrition_issue": "CONFLICTING_COMPLETE_NUTRITION_LATEST_RUN",
            }
            continue

        result[product_id] = {
            "latest_run_id": latest_run,
            "status": "DECLARED",
            "latest_run_statuses": ["DECLARED"],
            "usable_complete": True,
            "nutrition": complete_values[0],
            "nutrition_issue": None,
        }
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--artifacts-tsv", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    by_run: dict[str, set[str]] = defaultdict(set)
    by_run_status: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    files_by_run: dict[str, set[str]] = defaultdict(set)
    observations: list[tuple[int, str, str, Any]] = []
    canonical_excluded_rows: Counter[str] = Counter()
    canonical_excluded_runs: set[int] = set()
    for path in sorted(Path(args.root).rglob("*.jsonl")):
        rel = path.relative_to(args.root)
        first = rel.parts[0] if rel.parts else ""
        run_id = first.split("-", 1)[0]
        if not run_id.isdigit():
            continue
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
            if not isinstance(row, dict):
                continue
            product_id = str(row.get("product_id") or "")
            status = str(row.get("status") or "")
            if not product_id or status not in VALID or row.get("evidence_level") != EVIDENCE:
                continue
            by_run[run_id].add(product_id)
            by_run_status[run_id][status].add(product_id)
            files_by_run[run_id].add(str(rel))
            if is_canonical_status_row(row):
                observations.append((int(run_id), product_id, status, row.get("nutrition")))
            else:
                canonical_excluded_rows["DIAGNOSTIC_REPLAY_WRAPPER"] += 1
                canonical_excluded_runs.add(int(run_id))

    names = load_run_names(Path(args.artifacts_tsv))
    seen: set[str] = set()
    rows = []
    for run_id in sorted(by_run, key=int):
        ids = by_run[run_id]
        new_ids = ids - seen
        overlap = ids & seen
        rows.append({
            "run_id": int(run_id),
            "workflow_names": sorted(names.get(run_id, set())),
            "distinct_products_in_run": len(ids),
            "new_distinct_products": len(new_ids),
            "overlap_with_prior_union": len(overlap),
            "union_after_run": len(seen | ids),
            "status_distinct_counts": {status: len(values) for status, values in sorted(by_run_status[run_id].items())},
            "new_product_ids": sorted(new_ids),
            "overlap_product_ids": sorted(overlap),
            "artifact_files": sorted(files_by_run[run_id]),
        })
        seen |= ids

    latest = reconcile_latest_observations(observations)
    latest_status_counts = Counter(item["status"] for item in latest.values())
    nutrition_issue_counts = Counter(
        item["nutrition_issue"] for item in latest.values() if item.get("nutrition_issue")
    )
    usable = {
        product_id: item
        for product_id, item in latest.items()
        if item.get("usable_complete") is True and isinstance(item.get("nutrition"), dict)
    }
    latest_status_product_ids: dict[str, list[str]] = defaultdict(list)
    for product_id, item in latest.items():
        latest_status_product_ids[str(item["status"])].append(product_id)
    usable_products = [
        {
            "product_id": product_id,
            "latest_run_id": item["latest_run_id"],
            "nutrition": item["nutrition"],
        }
        for product_id, item in sorted(usable.items())
    ]
    coverage_without_canonical_state = sorted(seen - set(latest))

    result = {
        "policy": (
            "Chronological strict-provenance distinct union. Diagnostic replay wrappers remain in processed-id "
            "coverage but are excluded from canonical current status because their top-level state is historical; "
            "replay promotions are never applied canonically. Among live OCR observations, the latest persisted run "
            "wins for status accounting; a product is usable only when its latest live run contains only DECLARED "
            "strict OCR observations and every such observation has the same complete calories/protein/carbohydrate/fat "
            "payload. Older DECLARED nutrition is never inherited by a later live non-DECLARED status. No semantic "
            "classification or missing-value inference occurs here."
        ),
        "evidence_level": EVIDENCE,
        "runs_with_strict_ocr_rows": len(rows),
        "final_distinct_union": len(seen),
        "canonical_status_products": len(latest),
        "canonical_excluded_row_counts": dict(sorted(canonical_excluded_rows.items())),
        "canonical_excluded_run_ids": sorted(canonical_excluded_runs),
        "coverage_without_canonical_state": len(coverage_without_canonical_state),
        "coverage_without_canonical_state_product_ids": coverage_without_canonical_state,
        "latest_status_counts": dict(sorted(latest_status_counts.items())),
        "latest_status_product_ids": {
            status: sorted(product_ids) for status, product_ids in sorted(latest_status_product_ids.items())
        },
        "latest_nutrition_issue_counts": dict(sorted(nutrition_issue_counts.items())),
        "latest_usable_complete": len(usable),
        "latest_usable_complete_product_ids": sorted(usable),
        "latest_usable_field_counts": {field: len(usable) for field in NUTRITION_FIELDS},
        "latest_usable_products": usable_products,
        "runs": rows,
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "runs_with_strict_ocr_rows": len(rows),
        "final_distinct_union": len(seen),
        "canonical_status_products": len(latest),
        "canonical_excluded_row_counts": dict(sorted(canonical_excluded_rows.items())),
        "coverage_without_canonical_state": len(coverage_without_canonical_state),
        "latest_status_counts": dict(sorted(latest_status_counts.items())),
        "latest_nutrition_issue_counts": dict(sorted(nutrition_issue_counts.items())),
        "latest_usable_complete": len(usable),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
