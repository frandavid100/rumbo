from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

REQUIRED_MACROS = ("calories", "protein_g", "carbohydrate_g", "fat_g")


def read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partial", required=True)
    parser.add_argument("--recovery", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    partial_rows = read_jsonl(args.partial)
    recovery_rows = read_jsonl(args.recovery)
    baseline_rows = read_jsonl(args.baseline)

    rows_by_id: dict[str, dict] = {}
    duplicate_conflicts: list[str] = []
    for row in partial_rows + recovery_rows:
        pid = str(row.get("product_id") or "")
        if not pid:
            duplicate_conflicts.append("EMPTY_PRODUCT_ID")
            continue
        prior = rows_by_id.get(pid)
        if prior is not None and prior != row:
            duplicate_conflicts.append(pid)
        rows_by_id[pid] = row
    rows = list(rows_by_id.values())

    counts = Counter(row.get("status", "UNKNOWN") for row in rows)
    declared = [row for row in rows if row.get("status") == "DECLARED"]
    invalid_declared: list[str] = []
    provenance_errors: list[str] = []

    for row in rows:
        pid = str(row.get("product_id") or "")
        if row.get("evidence_level") != "OCR_DERIVED_FROM_MERCADONA_IMAGE":
            provenance_errors.append(f"{pid}:evidence_level")
        if row.get("source") != "MERCADONA_FIRST_PARTY" or row.get("source_record_kind") != "label image":
            provenance_errors.append(f"{pid}:source")
        if row.get("redistribution_allowed") is not False:
            provenance_errors.append(f"{pid}:redistribution")
        if any(key in row for key in ("classified", "menu_eligible", "CLASSIFIED", "MENU_ELIGIBLE")):
            provenance_errors.append(f"{pid}:classification")

    for row in declared:
        attempts = row.get("attempts") or []
        accepted = next((a for a in attempts if (a.get("ensemble") or {}).get("status") == "DECLARED"), None)
        ensemble = (accepted or {}).get("ensemble") or {}
        nutrition = row.get("nutrition") or {}
        if (
            ensemble.get("independent_engine_families", 0) < 2
            or ensemble.get("corroborated_fields", 0) < 4
            or any(nutrition.get(field) is None for field in REQUIRED_MACROS)
        ):
            invalid_declared.append(str(row.get("product_id") or ""))

    baseline_by_id = {str(row.get("product_id") or ""): row for row in baseline_rows}
    current_by_id = {str(row.get("product_id") or ""): row for row in rows}
    missing_baseline = sorted(set(baseline_by_id) - set(current_by_id))
    status_changes: list[dict] = []
    declared_value_conflicts: list[dict] = []
    for pid, baseline in baseline_by_id.items():
        current = current_by_id.get(pid)
        if current is None:
            continue
        if baseline.get("status") != current.get("status"):
            status_changes.append({"product_id": pid, "prior": baseline.get("status"), "current": current.get("status")})
        if (
            baseline.get("status") == "DECLARED"
            and current.get("status") == "DECLARED"
            and baseline.get("nutrition") != current.get("nutrition")
        ):
            declared_value_conflicts.append(
                {"product_id": pid, "prior": baseline.get("nutrition"), "current": current.get("nutrition")}
            )

    new_rows = [row for row in rows if str(row.get("product_id") or "") not in baseline_by_id]
    new_counts = Counter(row.get("status", "UNKNOWN") for row in new_rows)

    summary = {
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "source_workflow_runs": {
            "main_partial": 33189737223,
            "main_partial_artifact_id": 9709214992,
            "recovery_shard_94": 33233618283,
            "baseline_1024": 33189633845,
        },
        "inventory_products": 4280,
        "eligible_products": 2630,
        "sample_order": "SHA256_PRODUCT_ID_EAN",
        "expected_sample": 2048,
        "processed": len(rows),
        "status_counts": {
            "DECLARED": counts.get("DECLARED", 0),
            "REVIEW": counts.get("REVIEW", 0),
            "NO_VISUAL_REGION": counts.get("NO_VISUAL_REGION", 0),
            "ERROR": counts.get("ERROR", 0),
        },
        "declared_rate": round(len(declared) / len(rows), 4) if rows else 0.0,
        "usable_macro_counts": {field: len(declared) for field in REQUIRED_MACROS},
        "declared_with_two_independent_engines_and_four_corroborated_fields": len(declared) - len(invalid_declared),
        "invalid_declared_product_ids": invalid_declared,
        "duplicate_conflicts": duplicate_conflicts,
        "provenance_errors": provenance_errors,
        "reproducibility_against_1024_wave": {
            "baseline_products": len(baseline_rows),
            "missing_prior_product_ids": missing_baseline,
            "status_changes": status_changes,
            "declared_value_conflicts": declared_value_conflicts,
        },
        "new_1024_status_counts": {
            "DECLARED": new_counts.get("DECLARED", 0),
            "REVIEW": new_counts.get("REVIEW", 0),
            "NO_VISUAL_REGION": new_counts.get("NO_VISUAL_REGION", 0),
            "ERROR": new_counts.get("ERROR", 0),
        },
        "safety_assessment": "VALIDATED_CONSERVATIVE_STABLE",
    }

    if len(partial_rows) != 2032:
        raise SystemExit(f"Unexpected partial row count: {len(partial_rows)}")
    if len(recovery_rows) != 16:
        raise SystemExit(f"Unexpected recovery row count: {len(recovery_rows)}")
    if len(rows) != 2048:
        raise SystemExit(f"Incomplete recovered wave: processed={len(rows)} expected=2048")
    if len(baseline_rows) != 1024:
        raise SystemExit(f"Invalid 1024 baseline: rows={len(baseline_rows)}")
    if duplicate_conflicts:
        raise SystemExit("Conflicting duplicate product ids: " + ",".join(duplicate_conflicts[:20]))
    if missing_baseline:
        raise SystemExit("Recovered 2048 wave is not a strict superset of the 1024 baseline")
    if status_changes:
        raise SystemExit("OCR reproducibility regression on 1024 overlap")
    if declared_value_conflicts:
        raise SystemExit("Conflicting DECLARED nutrition on 1024 overlap")
    if provenance_errors:
        raise SystemExit("Provenance contract violated: " + ",".join(provenance_errors[:20]))
    if invalid_declared:
        raise SystemExit("Unsafe DECLARED rows detected: " + ",".join(invalid_declared[:20]))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda row: str(row.get("product_id") or ""))
    (out / "results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    db = sqlite3.connect(out / "results.sqlite")
    db.execute(
        """CREATE TABLE ocr_results (
        product_id TEXT PRIMARY KEY, ean TEXT, name TEXT, brand TEXT,
        category_id TEXT, category_name TEXT, status TEXT NOT NULL,
        calories REAL, protein_g REAL, carbohydrate_g REAL, fat_g REAL,
        image_url TEXT, evidence_level TEXT NOT NULL, source TEXT NOT NULL,
        source_record_kind TEXT NOT NULL, redistribution_allowed INTEGER NOT NULL,
        json_payload TEXT NOT NULL
        )"""
    )
    for row in rows:
        nutrition = row.get("nutrition") or {}
        db.execute(
            "INSERT INTO ocr_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                str(row.get("product_id") or ""), row.get("ean"), row.get("name"), row.get("brand"),
                row.get("category_id"), row.get("category_name"), row.get("status"), nutrition.get("calories"),
                nutrition.get("protein_g"), nutrition.get("carbohydrate_g"), nutrition.get("fat_g"), row.get("image_url"),
                row.get("evidence_level"), row.get("source"), row.get("source_record_kind"),
                0 if row.get("redistribution_allowed") is False else 1,
                json.dumps(row, ensure_ascii=False, sort_keys=True),
            ),
        )
    db.execute("CREATE INDEX idx_ocr_status ON ocr_results(status)")
    db.commit()
    db.close()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
