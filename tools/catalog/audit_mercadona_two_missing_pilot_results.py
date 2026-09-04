#!/usr/bin/env python3
"""Audit a Mercadona two-missing-core OCR rescue without double-counting promotions.

This is deliberately conservative. A current-run DECLARED row is only considered safe when
all four core values are independently corroborated, provenance is exact, the explicit basis
matches the routed baseline, and the two pre-existing baseline values remain close. Safe
readings already present in the persisted accounting cut are confirmations, not new promotions.
Only novel safe promotions are written to nutrition_staging and applied to cumulative totals.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
from typing import Any

FIELDS = ("calories", "protein_g", "carbohydrate_g", "fat_g")
ALLOWED = {"DECLARED", "REVIEW", "NO_VISUAL_REGION", "ERROR"}
EXPECTED_EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"
EXPECTED_SOURCE = "MERCADONA_FIRST_PARTY"
EXPECTED_RECORD_KIND = "label image"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def close(field: str, a: Any, b: Any) -> bool:
    a, b = float(a), float(b)
    tolerance = (
        max(5.0, 0.04 * max(abs(a), abs(b), 1.0))
        if field == "calories"
        else max(0.6, 0.10 * max(abs(a), abs(b), 1.0))
    )
    return abs(a - b) <= tolerance


def hard_reason(reasons: list[Any]) -> bool:
    for raw in reasons:
        reason = str(raw)
        if (
            reason.startswith("OCR_FIELD_CONFLICT")
            or reason.startswith("OCR_SAME_ENGINE_CONFLICT")
            or reason == "OCR_BASIS_CONFLICT"
            or reason.startswith("ENERGY_MACRO_MISMATCH")
        ):
            return True
    return False


def validate_accounting_cut(cut: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    cumulative = cut.get("cumulative_after_closed_stratum") or cut.get("cumulative_after_closure")
    if not isinstance(cumulative, dict):
        raise ValueError("accounting cut lacks cumulative state")
    required = {"catalog_total", "processed", "DECLARED_complete", "REVIEW"}
    if not required.issubset(cumulative):
        raise ValueError("accounting cut cumulative state is incomplete")
    if int(cumulative["DECLARED_complete"]) + int(cumulative["REVIEW"]) != int(cumulative["processed"]):
        raise ValueError("accounting cut DECLARED + REVIEW does not equal processed")

    promotions = cut.get("promotions") or []
    promotion_ids = [str(item.get("product_id") or "") for item in promotions]
    if any(not pid for pid in promotion_ids) or len(promotion_ids) != len(set(promotion_ids)):
        raise ValueError("accounting cut promotion IDs are empty or duplicated")

    closed = cut.get("closed_stratum") or {}
    if closed and "safe_promotions" in closed and int(closed["safe_promotions"]) != len(promotion_ids):
        raise ValueError("accounting cut promotion count disagrees with closed stratum")
    return cumulative, set(promotion_ids)


def audit(
    baseline_rows: list[dict[str, Any]],
    selection: dict[str, Any],
    rows: list[dict[str, Any]],
    accounting_cut: dict[str, Any],
    accounting_cut_name: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    all_baseline = {str(row["product_id"]): row for row in baseline_rows}
    expected_ids = {str(pid) for pid in (selection.get("product_ids") or [])}
    baseline = {pid: all_baseline[pid] for pid in expected_ids if pid in all_baseline}
    if len(baseline) != len(expected_ids):
        raise ValueError("pilot selection does not map one-to-one to baseline rows")

    cumulative, already_counted_ids = validate_accounting_cut(accounting_cut)

    ids = [str(row.get("product_id") or "") for row in rows]
    observed = set(ids)
    counts = Counter(str(row.get("status") or "UNKNOWN") for row in rows)
    duplicates = sorted(pid for pid, count in Counter(ids).items() if count > 1)
    missing = sorted(expected_ids - observed)
    unexpected = sorted(observed - expected_ids)
    bad_status = sorted(set(counts) - ALLOWED)
    provenance: list[str] = []
    unsafe: list[str] = []
    conflicts: list[dict[str, Any]] = []
    safe: list[dict[str, Any]] = []

    for row in rows:
        pid = str(row.get("product_id") or "")
        prior = baseline.get(pid)
        if prior is None:
            provenance.append(f"{pid}:not_in_baseline")
            continue
        if (
            row.get("evidence_level") != EXPECTED_EVIDENCE
            or row.get("source") != EXPECTED_SOURCE
            or row.get("source_record_kind") != EXPECTED_RECORD_KIND
            or row.get("redistribution_allowed") is not False
            or str(row.get("perspective")) != "9"
        ):
            provenance.append(f"{pid}:provenance")
        if row.get("status") != "DECLARED":
            continue

        accepted = next(
            (
                attempt
                for attempt in (row.get("attempts") or [])
                if (attempt.get("ensemble") or {}).get("status") == "DECLARED"
            ),
            None,
        )
        ensemble = (accepted or {}).get("ensemble") or {}
        nutrition = row.get("nutrition") or {}
        field_rows = {
            str(field.get("name")): field
            for field in (ensemble.get("fields") or [])
            if field.get("name") in FIELDS
        }
        missing_fields = set(prior.get("missing_core_fields") or [])
        if (
            accepted is None
            or int(ensemble.get("independent_engine_families") or 0) < 2
            or int(ensemble.get("corroborated_fields") or 0) < 4
            or any(nutrition.get(field) is None for field in FIELDS)
            or set(field_rows) != set(FIELDS)
            or any(not bool(field_rows[field].get("corroborated")) for field in FIELDS)
            or any(len(field_rows[field].get("engine_families") or []) < 2 for field in FIELDS)
            or len(missing_fields) != 2
            or hard_reason(ensemble.get("reasons") or [])
        ):
            unsafe.append(pid)
            continue

        bad: list[str] = []
        if row.get("basis") != prior.get("basis"):
            bad.append(f"basis:{prior.get('basis')}!={row.get('basis')}")
        prior_nutrition = prior.get("nutrition") or {}
        for field in FIELDS:
            prior_value = prior_nutrition.get(field)
            if field in missing_fields:
                if prior_value is not None:
                    bad.append(f"{field}:expected_prior_missing")
                continue
            if prior_value is None or not close(field, nutrition[field], prior_value):
                bad.append(f"{field}:{prior_value}!~{nutrition[field]}")
        if bad:
            conflicts.append({"product_id": pid, "conflicts": bad})
            continue

        safe.append(
            {
                "product_id": pid,
                "ean": row.get("ean"),
                "name": row.get("name"),
                "basis": row.get("basis"),
                "nutrition": {field: nutrition[field] for field in FIELDS},
                "recovered_core_fields": sorted(missing_fields),
                "independent_engine_families": ensemble.get("independent_engine_families"),
                "corroborated_fields": ensemble.get("corroborated_fields"),
                "source": "MERCADONA_FIRST_PARTY/label image",
                "evidence_level": EXPECTED_EVIDENCE,
                "redistribution_allowed": False,
                "CLASSIFIED": 0,
                "MENU_ELIGIBLE": 0,
            }
        )

    safe_ids = {item["product_id"] for item in safe}
    already_counted_safe = [item for item in safe if item["product_id"] in already_counted_ids]
    novel_safe = [item for item in safe if item["product_id"] not in already_counted_ids]
    novel_ids = {item["product_id"] for item in novel_safe}
    if safe_ids != {item["product_id"] for item in already_counted_safe} | novel_ids:
        raise ValueError("safe promotion partition is inconsistent")

    current_declared = len(safe)
    novel_declared = len(novel_safe)
    prior_declared = int(cumulative["DECLARED_complete"])
    prior_review = int(cumulative["REVIEW"])
    cumulative_declared = prior_declared + novel_declared
    cumulative_review = prior_review - novel_declared
    processed = int(cumulative["processed"])
    catalog_total = int(cumulative["catalog_total"])
    if cumulative_review < 0 or cumulative_declared + cumulative_review != processed:
        raise ValueError("reconciled cumulative totals are inconsistent")

    ok = (
        len(rows) == len(expected_ids)
        and len(observed) == len(expected_ids)
        and not duplicates
        and not missing
        and not unexpected
        and not provenance
        and not unsafe
        and not conflicts
        and not bad_status
    )
    summary = {
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": EXPECTED_EVIDENCE,
        "redistribution_allowed": False,
        "candidate_universe": int(selection.get("candidate_universe") or len(baseline_rows)),
        "selected": len(expected_ids),
        "processed": len(rows),
        "distinct_products_processed": len(observed),
        "remaining_candidates": max(0, int(selection.get("candidate_universe") or len(baseline_rows)) - len(expected_ids)),
        "status_counts": dict(sorted(counts.items())),
        "safe_promotion_products": current_declared,
        "safe_promotion_product_ids": sorted(safe_ids),
        "novel_safe_promotion_products": novel_declared,
        "novel_safe_promotion_product_ids": sorted(novel_ids),
        "already_counted_safe_promotion_products": len(already_counted_safe),
        "already_counted_safe_promotion_product_ids": sorted(item["product_id"] for item in already_counted_safe),
        "accounting_baseline_cut": accounting_cut_name,
        "accounting_baseline_declared": prior_declared,
        "accounting_baseline_review": prior_review,
        "pilot_rate": {
            "DECLARED_fraction": current_declared / len(rows) if rows else 0.0,
            "REVIEW_or_other_fraction": (len(rows) - current_declared) / len(rows) if rows else 0.0,
        },
        "value_conflicts": conflicts,
        "unsafe_declared": unsafe,
        "duplicate_product_ids": duplicates,
        "missing_product_ids": missing,
        "unexpected_product_ids": unexpected,
        "unexpected_statuses": bad_status,
        "provenance_errors": provenance,
        "images_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
        "cumulative_after_pilot": {
            "catalog_total": catalog_total,
            "processed": processed,
            "DECLARED_complete": cumulative_declared,
            "REVIEW": cumulative_review,
            "complete_usable_coverage_pct": round(100.0 * cumulative_declared / catalog_total, 4),
            "processed_coverage_pct": round(100.0 * processed / catalog_total, 4),
        },
        "safety_assessment": "VALIDATED" if ok else "FAILED",
    }
    return summary, safe, novel_safe


def write_outputs(
    out: Path,
    summary: dict[str, Any],
    safe: list[dict[str, Any]],
    novel_safe: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "safe-promotions.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "novel-safe-promotions.json").write_text(json.dumps(novel_safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "results-audited.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    db_path = out / "staging.sqlite"
    if db_path.exists():
        db_path.unlink()
    db = sqlite3.connect(db_path)
    db.executescript(
        """
        CREATE TABLE ocr_run_result (
            product_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
            source_record_kind TEXT NOT NULL,
            evidence_level TEXT NOT NULL,
            redistribution_allowed INTEGER NOT NULL,
            perspective TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );
        CREATE TABLE nutrition_staging (
            product_id TEXT PRIMARY KEY,
            ean TEXT,
            name TEXT,
            basis TEXT NOT NULL,
            calories REAL NOT NULL,
            protein_g REAL NOT NULL,
            carbohydrate_g REAL NOT NULL,
            fat_g REAL NOT NULL,
            source TEXT NOT NULL,
            evidence_level TEXT NOT NULL,
            redistribution_allowed INTEGER NOT NULL,
            classified INTEGER NOT NULL,
            menu_eligible INTEGER NOT NULL
        );
        """
    )
    for row in rows:
        db.execute(
            "INSERT INTO ocr_run_result VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(row.get("product_id") or ""),
                str(row.get("status") or ""),
                str(row.get("source") or ""),
                str(row.get("source_record_kind") or ""),
                str(row.get("evidence_level") or ""),
                int(bool(row.get("redistribution_allowed"))),
                str(row.get("perspective") or ""),
                json.dumps(row, ensure_ascii=False, sort_keys=True),
            ),
        )
    # Critical invariant: only genuinely new safe promotions enter nutrition staging.
    for item in novel_safe:
        n = item["nutrition"]
        db.execute(
            "INSERT INTO nutrition_staging VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item["product_id"], item.get("ean"), item.get("name"), item["basis"],
                n["calories"], n["protein_g"], n["carbohydrate_g"], n["fat_g"],
                item["source"], item["evidence_level"], 0, 0, 0,
            ),
        )
    db.commit()
    db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--accounting-cut", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    baseline_rows = load_jsonl(args.baseline)
    selection = load_json(args.selection)
    rows = load_jsonl(args.results)
    accounting_cut = load_json(args.accounting_cut)
    summary, safe, novel_safe = audit(
        baseline_rows,
        selection,
        rows,
        accounting_cut,
        args.accounting_cut.name,
    )
    write_outputs(args.out, summary, safe, novel_safe, rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["safety_assessment"] != "VALIDATED":
        raise SystemExit("pilot safety audit failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
