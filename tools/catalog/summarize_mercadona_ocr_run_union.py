from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

VALID = {"DECLARED", "REVIEW", "NO_VISUAL_REGION", "ERROR"}
EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"
SOURCE = "MERCADONA_FIRST_PARTY"
SOURCE_RECORD_KIND = "label image"
NUTRITION_FIELDS = ("calories", "protein_g", "carbohydrate_g", "fat_g")
REASON_FAMILY_ORDER = (
    "EXPLICIT_FIELD_CONFLICT",
    "ENERGY_MACRO_INCOHERENCE",
    "AMBIGUOUS_TABLE",
    "NO_VISUAL_REGION",
    "INSUFFICIENT_CORROBORATION",
    "INCOMPLETE_EXTRACTION",
    "ERROR",
    "OTHER_REVIEW",
    "NONE",
)
EXPLICIT_CONTRADICTION_FAMILIES = {"EXPLICIT_FIELD_CONFLICT", "ENERGY_MACRO_INCOHERENCE"}
SAFETY_BLOCKING_FAMILIES = EXPLICIT_CONTRADICTION_FAMILIES | {"AMBIGUOUS_TABLE"}


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
        number = float(item)
        if not math.isfinite(number):
            return None
        out[field] = number
    return out


def nutrition_key(value: dict[str, float]) -> tuple[float, ...]:
    return tuple(value[field] for field in NUTRITION_FIELDS)


def is_canonical_status_row(row: dict[str, Any]) -> bool:
    """Replay wrappers count as processed evidence but never replace live state."""
    return not isinstance(row.get("replay"), dict)


def has_strict_raw_provenance(row: dict[str, Any]) -> bool:
    """Require the producer's persisted first-party label-image provenance.

    The exact OCR evidence marker remains the processed-union gate. This stricter
    predicate is only the usability gate: malformed or provenance-incomplete rows
    can still prove that a product was processed, but they can never supply macros.
    """
    image_url = row.get("image_url")
    return (
        row.get("evidence_level") == EVIDENCE
        and row.get("source") == SOURCE
        and row.get("source_record_kind") == SOURCE_RECORD_KIND
        and row.get("redistribution_allowed") is False
        and isinstance(image_url, str)
        and image_url.startswith(("https://", "http://"))
    )


def _diagnostic_values(row: dict[str, Any]) -> list[str]:
    values: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                add(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                add(str(key))
                if isinstance(item, (str, list, tuple, set, dict)):
                    add(item)

    for key in ("nutrition_issue", "review_reason", "review_reasons", "rejection_reason", "reason", "reasons"):
        add(row.get(key))
    attempts = row.get("attempts")
    if isinstance(attempts, list):
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            for key in ("nutrition_issue", "review_reason", "review_reasons", "rejection_reason", "reason", "reasons"):
                add(attempt.get(key))
            ensemble = attempt.get("ensemble")
            if isinstance(ensemble, dict):
                for key in (
                    "nutrition_issue", "review_reason", "review_reasons", "rejection_reason",
                    "reason", "reasons", "conflict", "conflicts", "field_conflicts",
                ):
                    add(ensemble.get(key))
    return values


def _attempt_has_ocr_signal(row: dict[str, Any]) -> bool:
    attempts = row.get("attempts")
    if not isinstance(attempts, list):
        return False
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        count = attempt.get("ocr_count")
        if isinstance(count, int) and not isinstance(count, bool) and count > 0:
            return True
        text = attempt.get("ocr_full_text")
        if isinstance(text, str) and text.strip():
            return True
        engines = attempt.get("engines")
        if isinstance(engines, dict):
            for value in engines.values():
                if isinstance(value, dict) and isinstance(value.get("normalized_ocr_text"), str) and value["normalized_ocr_text"].strip():
                    return True
    return False


def classify_review_reason_families(row: dict[str, Any]) -> list[str]:
    status = str(row.get("status") or "")
    if status == "DECLARED":
        return ["NONE"]
    if status == "ERROR":
        return ["ERROR"]

    diagnostics = "\n".join(_diagnostic_values(row)).upper()
    families: set[str] = set()
    if "OCR_FIELD_CONFLICT" in diagnostics or "FIELD_CONFLICT" in diagnostics:
        families.add("EXPLICIT_FIELD_CONFLICT")
    if "INCOHER" in diagnostics or "ENERGY_MACRO" in diagnostics or "MACRO_ENERGY" in diagnostics:
        families.add("ENERGY_MACRO_INCOHERENCE")
    if "AMBIGU" in diagnostics or "MULTI_COLUMN" in diagnostics or "MULTIPLE_COLUMN" in diagnostics:
        families.add("AMBIGUOUS_TABLE")

    no_region_signal = status == "NO_VISUAL_REGION" or "NO_VISUAL_REGION" in diagnostics
    if no_region_signal and not _attempt_has_ocr_signal(row):
        families.add("NO_VISUAL_REGION")
    if "CORROBOR" in diagnostics or "INDEPENDENT_SUPPORT" in diagnostics:
        families.add("INSUFFICIENT_CORROBORATION")
    if any(token in diagnostics for token in ("MISSING", "INCOMPLETE", "NO_NUTRITION", "NO_TABLE", "NO_MACRO")):
        families.add("INCOMPLETE_EXTRACTION")
    if not families and status in {"REVIEW", "NO_VISUAL_REGION"}:
        families.add("OTHER_REVIEW")
    return [family for family in REASON_FAMILY_ORDER if family in families]


def summarize_declared_to_review_transitions(
    history: dict[str, list[tuple[int, str, list[str]]]],
) -> dict[str, Any]:
    historical_declared_ids: list[str] = []
    transition_ids: list[str] = []
    reason_ids: dict[str, list[str]] = defaultdict(list)
    explicit_ids: list[str] = []
    safety_blocking_ids: list[str] = []
    non_contradictory_ids: list[str] = []

    for product_id, events in sorted(history.items()):
        if not events:
            continue
        declared_runs = {run_id for run_id, status, _ in events if status == "DECLARED"}
        if not declared_runs:
            continue
        historical_declared_ids.append(product_id)
        latest_run = max(run_id for run_id, _, _ in events)
        latest_events = [(status, families) for run_id, status, families in events if run_id == latest_run]
        latest_statuses = {status for status, _ in latest_events}
        if latest_statuses != {"REVIEW"} or max(declared_runs) >= latest_run:
            continue
        transition_ids.append(product_id)
        families = {
            family for _, event_families in latest_events for family in event_families if family != "NONE"
        } or {"OTHER_REVIEW"}
        for family in sorted(families):
            reason_ids[family].append(product_id)
        if families & EXPLICIT_CONTRADICTION_FAMILIES:
            explicit_ids.append(product_id)
        if families & SAFETY_BLOCKING_FAMILIES:
            safety_blocking_ids.append(product_id)
        else:
            non_contradictory_ids.append(product_id)

    return {
        "historical_declared_products": len(historical_declared_ids),
        "historical_declared_product_ids": historical_declared_ids,
        "latest_review_after_historical_declared": len(transition_ids),
        "latest_review_after_historical_declared_product_ids": transition_ids,
        "reason_family_counts": {family: len(ids) for family, ids in sorted(reason_ids.items())},
        "reason_family_product_ids": {family: sorted(ids) for family, ids in sorted(reason_ids.items())},
        "explicit_contradiction_products": len(explicit_ids),
        "explicit_contradiction_product_ids": sorted(explicit_ids),
        "safety_blocking_products": len(safety_blocking_ids),
        "safety_blocking_product_ids": sorted(safety_blocking_ids),
        "non_contradictory_review_products": len(non_contradictory_ids),
        "non_contradictory_review_product_ids": sorted(non_contradictory_ids),
    }


def reconcile_latest_observations(
    observations: Iterable[tuple[int, str, str, Any] | tuple[int, str, str, Any, bool]],
) -> dict[str, dict[str, Any]]:
    """Return one conservative latest persisted live OCR state per product.

    Four-item observations are accepted for backwards-compatible tests/callers and
    imply strict provenance. Production passes a fifth boolean derived from the raw
    persisted row. A provenance-incomplete DECLARED observation remains DECLARED
    for status accounting but can never become nutrition-usable.
    """
    grouped: dict[str, dict[int, list[tuple[str, Any, bool]]]] = defaultdict(lambda: defaultdict(list))
    for observation in observations:
        if len(observation) == 4:
            run_id, product_id, status, nutrition = observation
            strict_provenance = True
        elif len(observation) == 5:
            run_id, product_id, status, nutrition, strict_provenance = observation
        else:
            raise ValueError("observations must contain 4 or 5 values")
        if status not in VALID:
            continue
        grouped[str(product_id)][int(run_id)].append((status, nutrition, bool(strict_provenance)))

    result: dict[str, dict[str, Any]] = {}
    for product_id, by_run in grouped.items():
        latest_run = max(by_run)
        values = by_run[latest_run]
        statuses = {status for status, _, _ in values}
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

        if any(not strict_provenance for _, _, strict_provenance in values):
            result[product_id] = {
                "latest_run_id": latest_run,
                "status": "DECLARED",
                "latest_run_statuses": ["DECLARED"],
                "usable_complete": False,
                "nutrition": None,
                "nutrition_issue": "INCOMPLETE_STRICT_PROVENANCE_LATEST_RUN",
            }
            continue

        normalized = [complete_nutrition(nutrition) for _, nutrition, _ in values]
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
        if len({nutrition_key(item) for item in complete_values}) != 1:
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
    observations: list[tuple[int, str, str, Any, bool]] = []
    live_history: dict[str, list[tuple[int, str, list[str]]]] = defaultdict(list)
    canonical_excluded_rows: Counter[str] = Counter()
    canonical_excluded_runs: set[int] = set()
    strict_provenance_failures: Counter[str] = Counter()

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
                strict = has_strict_raw_provenance(row)
                observations.append((int(run_id), product_id, status, row.get("nutrition"), strict))
                live_history[product_id].append((int(run_id), status, classify_review_reason_families(row)))
                if not strict:
                    if row.get("source") != SOURCE:
                        strict_provenance_failures["SOURCE"] += 1
                    if row.get("source_record_kind") != SOURCE_RECORD_KIND:
                        strict_provenance_failures["SOURCE_RECORD_KIND"] += 1
                    if row.get("redistribution_allowed") is not False:
                        strict_provenance_failures["REDISTRIBUTION_ALLOWED"] += 1
                    image_url = row.get("image_url")
                    if not isinstance(image_url, str) or not image_url.startswith(("https://", "http://")):
                        strict_provenance_failures["IMAGE_URL"] += 1
            else:
                canonical_excluded_rows["DIAGNOSTIC_REPLAY_WRAPPER"] += 1
                canonical_excluded_runs.add(int(run_id))

    names = load_run_names(Path(args.artifacts_tsv))
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
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
    nutrition_issue_counts = Counter(item["nutrition_issue"] for item in latest.values() if item.get("nutrition_issue"))
    usable = {
        product_id: item for product_id, item in latest.items()
        if item.get("usable_complete") is True and isinstance(item.get("nutrition"), dict)
    }
    latest_status_product_ids: dict[str, list[str]] = defaultdict(list)
    for product_id, item in latest.items():
        latest_status_product_ids[str(item["status"])].append(product_id)
    usable_products = [
        {"product_id": product_id, "latest_run_id": item["latest_run_id"], "nutrition": item["nutrition"]}
        for product_id, item in sorted(usable.items())
    ]
    coverage_without_canonical_state = sorted(seen - set(latest))
    transition_audit = summarize_declared_to_review_transitions(live_history)

    result = {
        "policy": (
            "Chronological exact-evidence processed union with latest-live canonical reconciliation. Diagnostic replay "
            "wrappers remain in processed coverage but never update canonical status. A latest live DECLARED row becomes "
            "nutrition-usable only when every latest-run observation has complete agreeing four-field nutrition and the "
            "raw persisted provenance is exactly Mercadona first-party label-image OCR with redistribution disallowed. "
            "Provenance-incomplete DECLARED rows remain DECLARED for status accounting but have null usable nutrition. "
            "Older DECLARED nutrition is never inherited by a later non-usable state; no missing values are inferred."
        ),
        "evidence_level": EVIDENCE,
        "strict_provenance": {
            "source": SOURCE,
            "source_record_kind": SOURCE_RECORD_KIND,
            "redistribution_allowed": False,
            "image_url_required": True,
        },
        "strict_provenance_failure_counts": dict(sorted(strict_provenance_failures.items())),
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
        "declared_to_review_transition_audit": transition_audit,
        "runs": rows,
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "runs_with_strict_ocr_rows": len(rows),
        "final_distinct_union": len(seen),
        "canonical_status_products": len(latest),
        "canonical_excluded_row_counts": dict(sorted(canonical_excluded_rows.items())),
        "strict_provenance_failure_counts": dict(sorted(strict_provenance_failures.items())),
        "coverage_without_canonical_state": len(coverage_without_canonical_state),
        "latest_status_counts": dict(sorted(latest_status_counts.items())),
        "latest_nutrition_issue_counts": dict(sorted(nutrition_issue_counts.items())),
        "latest_usable_complete": len(usable),
        "historical_declared_products": transition_audit["historical_declared_products"],
        "latest_review_after_historical_declared": transition_audit["latest_review_after_historical_declared"],
        "latest_review_after_historical_declared_reason_family_counts": transition_audit["reason_family_counts"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
