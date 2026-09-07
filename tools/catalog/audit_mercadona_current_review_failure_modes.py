from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any, Iterable

from summarize_mercadona_ocr_run_union import (
    EVIDENCE,
    SOURCE,
    SOURCE_RECORD_KIND,
    VALID,
    canonical_exclusion_reason,
)

CORE_FIELDS = ("calories", "protein_g", "carbohydrate_g", "fat_g")
EXPLICIT_BASES = {"100_g", "100_ml"}


def _run_id(path: Path, root: Path) -> int | None:
    rel = path.relative_to(root)
    if not rel.parts:
        return None
    first = rel.parts[0]
    token = first.split("-", 1)[0]
    return int(token) if token.isdigit() else None


def _load_rows(path: Path) -> Iterable[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _collect_reason_strings(value: Any, *, key: str = "") -> list[str]:
    wanted = {
        "reason",
        "reasons",
        "review_reason",
        "review_reasons",
        "nutrition_issue",
        "rejection_reason",
        "conflict",
        "conflicts",
        "field_conflicts",
    }
    out: list[str] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            normalized = str(child_key).lower()
            if normalized in wanted:
                if isinstance(child, str) and child.strip():
                    out.append(child.strip())
                elif isinstance(child, (list, tuple, set)):
                    for item in child:
                        if isinstance(item, str) and item.strip():
                            out.append(item.strip())
                        elif isinstance(item, dict):
                            out.extend(_collect_reason_strings(item, key=normalized))
                elif isinstance(child, dict):
                    for nested_key, nested in child.items():
                        out.append(str(nested_key))
                        if isinstance(nested, str) and nested.strip():
                            out.append(nested.strip())
            if isinstance(child, (dict, list, tuple)):
                out.extend(_collect_reason_strings(child, key=normalized))
    elif isinstance(value, (list, tuple)):
        for child in value:
            out.extend(_collect_reason_strings(child, key=key))
    return out


def _reason_prefix(reason: str) -> str:
    text = reason.strip().upper()
    for delimiter in (":", "(", "["):
        text = text.split(delimiter, 1)[0]
    return text.strip() or "UNKNOWN"


def _core_present(nutrition: Any) -> int:
    if not isinstance(nutrition, dict):
        return 0
    return sum(nutrition.get(field) is not None for field in CORE_FIELDS)


def _int_value(value: Any) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0


def _float_value(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _ensemble_snapshots(row: dict[str, Any]) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    attempts = row.get("attempts")
    if isinstance(attempts, list):
        for attempt_index, attempt in enumerate(attempts):
            if not isinstance(attempt, dict):
                continue
            ensemble = attempt.get("ensemble")
            if isinstance(ensemble, dict):
                snapshots.append(
                    {
                        "origin": f"attempt[{attempt_index}].ensemble",
                        "nutrition": ensemble.get("nutrition"),
                        "basis": ensemble.get("basis") or attempt.get("basis"),
                        "corroborated_fields": _int_value(ensemble.get("corroborated_fields")),
                        "independent_engine_families": _int_value(ensemble.get("independent_engine_families")),
                        "confidence": _float_value(ensemble.get("confidence")),
                        "reasons": _collect_reason_strings(ensemble),
                    }
                )
    # Some early raw producers persisted a product-level candidate without an attempt ensemble.
    # It remains diagnostic only: no independent-family/corroboration credit is invented.
    if isinstance(row.get("nutrition"), dict):
        snapshots.append(
            {
                "origin": "row",
                "nutrition": row.get("nutrition"),
                "basis": row.get("basis") or row.get("nutrition_basis"),
                "corroborated_fields": 0,
                "independent_engine_families": 0,
                "confidence": 0.0,
                "reasons": _collect_reason_strings(row),
            }
        )
    return snapshots


def _best_snapshot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    snapshots = [snapshot for row in rows for snapshot in _ensemble_snapshots(row)]
    if not snapshots:
        return {
            "origin": None,
            "nutrition": None,
            "basis": None,
            "corroborated_fields": 0,
            "independent_engine_families": 0,
            "confidence": 0.0,
            "reasons": [],
        }
    return max(
        snapshots,
        key=lambda item: (
            _core_present(item.get("nutrition")),
            _int_value(item.get("corroborated_fields")),
            _int_value(item.get("independent_engine_families")),
            _float_value(item.get("confidence")),
            str(item.get("origin") or ""),
        ),
    )


def _has_ocr_signal(row: dict[str, Any]) -> bool:
    if isinstance(row.get("ocr_full_text"), str) and row["ocr_full_text"].strip():
        return True
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
            for engine in engines.values():
                if not isinstance(engine, dict):
                    continue
                for key in ("normalized_ocr_text", "ocr_full_text"):
                    text = engine.get(key)
                    if isinstance(text, str) and text.strip():
                        return True
    return False


def _blockers(reasons: Iterable[str]) -> set[str]:
    text = "\n".join(str(reason).upper() for reason in reasons)
    out: set[str] = set()
    if any(token in text for token in ("OCR_FIELD_CONFLICT", "OCR_SAME_ENGINE_CONFLICT", "OCR_BASIS_CONFLICT")):
        out.add("HARD_OCR_CONFLICT")
    if any(token in text for token in ("ENERGY_MACRO_MISMATCH", "ENERGY_MACRO_INCOHER", "MACRO_ENERGY")):
        out.add("ENERGY_MACRO_INCOHERENCE")
    if any(
        token in text
        for token in (
            "MULTIPLE_NUTRITION_COLUMNS",
            "MULTI_COLUMN",
            "MULTIPLE_COLUMN",
            "MULTICOLUMN",
            "AMBIGUOUS_TABLE",
            "AMBIGUOUS_NUTRITION",
        )
    ):
        out.add("AMBIGUOUS_TABLE")
    return out


def _candidate_payload(
    product_id: str,
    run_id: int,
    rows: list[dict[str, Any]],
    snapshot: dict[str, Any],
    reasons: list[str],
    blockers: set[str],
) -> dict[str, Any]:
    representative = rows[0]
    return {
        "product_id": product_id,
        "ean": representative.get("ean"),
        "name": representative.get("name"),
        "category_id": representative.get("category_id"),
        "category_name": representative.get("category_name"),
        "latest_raw_run_id": run_id,
        "canonical_status": "REVIEW",
        "usable_nutrition": None,
        "promotion_allowed": False,
        "diagnostic_candidate_values": snapshot.get("nutrition"),
        "basis": snapshot.get("basis"),
        "corroborated_fields": _int_value(snapshot.get("corroborated_fields")),
        "independent_engine_families": _int_value(snapshot.get("independent_engine_families")),
        "confidence": _float_value(snapshot.get("confidence")),
        "snapshot_origin": snapshot.get("origin"),
        "safety_blockers": sorted(blockers),
        "reason_prefixes": sorted({_reason_prefix(reason) for reason in reasons if str(reason).strip()}),
        "image_url": representative.get("image_url"),
        "source": SOURCE,
        "source_record_kind": SOURCE_RECORD_KIND,
        "source_display": f"{SOURCE}/{SOURCE_RECORD_KIND}",
        "evidence_level": EVIDENCE,
        "redistribution_allowed": False,
        "image_persisted": False,
        "missing_values_inferred": False,
    }


def build_audit(root: Path, run_union_summary: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    expected_ids = {str(value) for value in run_union_summary.get("latest_status_product_ids", {}).get("REVIEW", [])}
    expected_count = int(run_union_summary.get("latest_status_counts", {}).get("REVIEW", len(expected_ids)))
    if expected_count != len(expected_ids):
        raise ValueError(f"run-union REVIEW count/id mismatch: count={expected_count}, ids={len(expected_ids)}")

    by_product_run: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    excluded = Counter()
    for path in sorted(root.rglob("*.jsonl")):
        run_id = _run_id(path, root)
        if run_id is None:
            continue
        for row in _load_rows(path):
            product_id = str(row.get("product_id") or "")
            status = str(row.get("status") or "")
            if not product_id or status not in VALID or row.get("evidence_level") != EVIDENCE:
                continue
            reason = canonical_exclusion_reason(row)
            if reason:
                excluded[reason] += 1
                continue
            by_product_run[product_id][run_id].append(row)

    missing = sorted(expected_ids - set(by_product_run))
    if missing:
        raise ValueError(f"missing latest raw rows for {len(missing)} expected REVIEW products: {missing[:10]}")

    latest_review: dict[str, tuple[int, list[dict[str, Any]]]] = {}
    for product_id in sorted(expected_ids):
        by_run = by_product_run[product_id]
        latest_run = max(by_run)
        rows = by_run[latest_run]
        statuses = {str(row.get("status") or "") for row in rows}
        if statuses != {"REVIEW"}:
            raise ValueError(
                f"latest raw status disagrees with canonical REVIEW for {product_id}: run={latest_run}, statuses={sorted(statuses)}"
            )
        latest_review[product_id] = (latest_run, rows)

    core_coverage = Counter()
    corroborated_counts = Counter()
    family_counts = Counter()
    basis_counts = Counter()
    reason_prefix_counts = Counter()
    blocker_counts = Counter()
    safe_by_corroboration = Counter()
    safe_by_families = Counter()
    ocr_signal = 0
    no_visual_region = 0

    near_safe: list[dict[str, Any]] = []
    fully_corroborated: list[dict[str, Any]] = []
    complete_blocked: list[dict[str, Any]] = []
    reasonless: list[dict[str, Any]] = []

    for product_id, (run_id, rows) in latest_review.items():
        snapshot = _best_snapshot(rows)
        reasons = sorted({reason for row in rows for reason in _collect_reason_strings(row) if reason.strip()})
        blockers = _blockers(reasons)
        present = _core_present(snapshot.get("nutrition"))
        corroborated = _int_value(snapshot.get("corroborated_fields"))
        families = _int_value(snapshot.get("independent_engine_families"))
        basis = str(snapshot.get("basis") or "NONE")
        has_signal = any(_has_ocr_signal(row) for row in rows)

        core_coverage[present] += 1
        corroborated_counts[corroborated] += 1
        family_counts[families] += 1
        basis_counts[basis] += 1
        if has_signal:
            ocr_signal += 1
        for reason in reasons:
            reason_prefix_counts[_reason_prefix(reason)] += 1
        for blocker in blockers:
            blocker_counts[blocker] += 1
        if any("NO_VISUAL_REGION" in reason.upper() for reason in reasons) and not has_signal:
            no_visual_region += 1

        payload = _candidate_payload(product_id, run_id, rows, snapshot, reasons, blockers)
        if not reasons:
            reasonless.append(payload)

        explicit_basis = snapshot.get("basis") in EXPLICIT_BASES
        safe_complete_shape = present == 4 and explicit_basis and families >= 2 and not blockers
        if safe_complete_shape:
            safe_by_corroboration[corroborated] += 1
            safe_by_families[families] += 1
            near_safe.append(payload)
            if corroborated >= 4:
                fully_corroborated.append(payload)
        elif present == 4 and blockers:
            complete_blocked.append(payload)

    if len(latest_review) != expected_count:
        raise ValueError(f"expected {expected_count} latest REVIEW products, audited {len(latest_review)}")

    near_safe.sort(key=lambda row: row["product_id"])
    fully_corroborated.sort(key=lambda row: row["product_id"])
    complete_blocked.sort(key=lambda row: row["product_id"])
    reasonless.sort(key=lambda row: row["product_id"])

    result = {
        "audit_policy": (
            "Latest raw-live exact-evidence REVIEW failure-mode census. Replay wrappers and prior canonical materializations "
            "are excluded. Diagnostic extraction values are never promoted or made usable. A near-safe diagnostic shape "
            "requires all four core values, explicit 100 g/100 ml basis, at least two independent OCR engine families, "
            "and no hard OCR field/basis conflict, energy-macro incoherence, or ambiguous/multiple-column table signal."
        ),
        "source": f"{SOURCE}/{SOURCE_RECORD_KIND}",
        "evidence_level": EVIDENCE,
        "redistribution_allowed": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "latest_review_products": len(latest_review),
        "latest_raw_review_rows": sum(len(rows) for _, rows in latest_review.values()),
        "excluded_derived_rows": dict(sorted(excluded.items())),
        "core_field_coverage_counts": {str(key): value for key, value in sorted(core_coverage.items())},
        "corroborated_field_counts": {str(key): value for key, value in sorted(corroborated_counts.items())},
        "independent_engine_family_counts": {str(key): value for key, value in sorted(family_counts.items())},
        "basis_counts": dict(sorted(basis_counts.items())),
        "reason_prefix_counts": dict(sorted(reason_prefix_counts.items())),
        "safety_blocker_counts": {
            key: blocker_counts.get(key, 0)
            for key in ("HARD_OCR_CONFLICT", "ENERGY_MACRO_INCOHERENCE", "AMBIGUOUS_TABLE")
        },
        "products_with_ocr_signal": ocr_signal,
        "products_without_ocr_signal": len(latest_review) - ocr_signal,
        "no_visual_region_without_ocr_signal": no_visual_region,
        "near_safe_complete_review": len(near_safe),
        "near_safe_complete_by_corroborated_fields": {str(key): value for key, value in sorted(safe_by_corroboration.items())},
        "near_safe_complete_by_engine_families": {str(key): value for key, value in sorted(safe_by_families.items())},
        "fully_corroborated_but_still_review": len(fully_corroborated),
        "complete_but_safety_blocked": len(complete_blocked),
        "reasonless_review_products": len(reasonless),
        "usable_products_created": 0,
        "REVIEW_promoted": 0,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    files = {
        "near-safe-complete-review": near_safe,
        "fully-corroborated-still-review": fully_corroborated,
        "complete-but-safety-blocked": complete_blocked,
        "reasonless-review": reasonless,
    }
    return result, files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--run-union-summary", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    summary = json.loads(Path(args.run_union_summary).read_text(encoding="utf-8"))
    result, files = build_audit(Path(args.root), summary)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for stem, rows in files.items():
        (out / f"{stem}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
