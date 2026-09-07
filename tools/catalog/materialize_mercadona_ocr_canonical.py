from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"
SOURCE = "MERCADONA_FIRST_PARTY/label image"
SOURCE_RECORD_KIND = "label image"
NUTRITION_FIELDS = ("calories", "protein_g", "carbohydrate_g", "fat_g")
SCHEMA_VERSION = "1.0.1"


def _product_sort_key(product_id: str) -> tuple[int, int | str]:
    text = str(product_id)
    return (0, int(text)) if text.isdigit() else (1, text)


def _complete_nutrition(value: Any) -> dict[str, float] | None:
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


def _run_metadata(summary: dict[str, Any]) -> dict[int, list[str]]:
    """Map persisted run IDs to workflow names without inferring per-product liveness.

    The chronological union deliberately includes diagnostic replay wrappers for processed-ID
    coverage. Therefore the last union run mentioning a product is not necessarily its latest
    *live* canonical OCR observation. We only attach a live run locator where the canonical
    summary itself exposes one: currently that is every usable DECLARED row via
    ``latest_usable_products[].latest_run_id``. Non-usable rows keep the locator null rather
    than falsely attributing a replay run.
    """
    runs = summary.get("runs")
    if not isinstance(runs, list):
        raise ValueError("summary.runs must be a list")
    result: dict[int, list[str]] = {}
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("summary.runs entries must be objects")
        run_id = run.get("run_id")
        if isinstance(run_id, bool) or not isinstance(run_id, int):
            raise ValueError("run_id must be an integer")
        names = run.get("workflow_names") or []
        if not isinstance(names, list):
            raise ValueError("workflow_names must be a list")
        result[run_id] = sorted(str(value) for value in names)
    return result


def build_canonical_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    if summary.get("evidence_level") != EVIDENCE:
        raise ValueError("summary evidence_level is not the strict Mercadona OCR marker")

    expected = summary.get("canonical_status_products")
    if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
        raise ValueError("canonical_status_products must be a non-negative integer")

    status_map: dict[str, str] = {}
    status_groups = summary.get("latest_status_product_ids")
    if not isinstance(status_groups, dict):
        raise ValueError("latest_status_product_ids must be an object")
    for status, values in status_groups.items():
        if not isinstance(values, list):
            raise ValueError("latest_status_product_ids values must be lists")
        for raw_product_id in values:
            product_id = str(raw_product_id)
            previous = status_map.get(product_id)
            if previous is not None and previous != str(status):
                raise ValueError(f"product {product_id} appears in multiple canonical statuses")
            status_map[product_id] = str(status)
    if len(status_map) != expected:
        raise ValueError(f"canonical status partition has {len(status_map)} products; expected {expected}")

    run_metadata = _run_metadata(summary)
    usable_by_id: dict[str, dict[str, Any]] = {}
    usable_products = summary.get("latest_usable_products")
    if not isinstance(usable_products, list):
        raise ValueError("latest_usable_products must be a list")
    for item in usable_products:
        if not isinstance(item, dict):
            raise ValueError("latest_usable_products entries must be objects")
        product_id = str(item.get("product_id") or "")
        if not product_id or product_id in usable_by_id:
            raise ValueError(f"invalid or duplicate usable product id: {product_id!r}")
        nutrition = _complete_nutrition(item.get("nutrition"))
        if nutrition is None:
            raise ValueError(f"usable product {product_id} lacks complete finite nutrition")
        run_id = item.get("latest_run_id")
        if isinstance(run_id, bool) or not isinstance(run_id, int):
            raise ValueError(f"usable product {product_id} has invalid latest_run_id")
        if run_id not in run_metadata:
            raise ValueError(
                f"usable latest live run missing from chronological summary: product={product_id} run={run_id}"
            )
        usable_by_id[product_id] = {
            "latest_run_id": run_id,
            "workflow_names": run_metadata[run_id],
            "nutrition": nutrition,
        }

    non_declared_usable = sorted(
        (product_id for product_id in usable_by_id if status_map.get(product_id) != "DECLARED"),
        key=_product_sort_key,
    )
    if non_declared_usable:
        raise ValueError(f"non-DECLARED products marked usable: {non_declared_usable[:10]}")
    if summary.get("latest_usable_complete") != len(usable_by_id):
        raise ValueError(
            f"usable product count {len(usable_by_id)} does not match "
            f"latest_usable_complete={summary.get('latest_usable_complete')}"
        )

    rows: list[dict[str, Any]] = []
    for product_id in sorted(status_map, key=_product_sort_key):
        status = status_map[product_id]
        usable = usable_by_id.get(product_id)
        nutrition = usable["nutrition"] if usable is not None else None
        latest_live_run_id = usable["latest_run_id"] if usable is not None else None
        workflow_names = usable["workflow_names"] if usable is not None else []

        provenance = None
        if nutrition is not None:
            provenance = {
                field: {
                    "evidence_level": EVIDENCE,
                    "source": SOURCE,
                    "source_record_kind": SOURCE_RECORD_KIND,
                    "redistribution_allowed": False,
                    "latest_live_run_id": latest_live_run_id,
                }
                for field in NUTRITION_FIELDS
            }

        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "product_id": product_id,
                "status": status,
                "usable_complete": usable is not None,
                "nutrition": nutrition,
                "nutrition_provenance": provenance,
                "latest_live_run_id": latest_live_run_id,
                "workflow_names": workflow_names,
                "canonical_status_source": "run-union-summary/latest-live reconciliation",
                "evidence_level": EVIDENCE,
                "source": SOURCE,
                "source_record_kind": SOURCE_RECORD_KIND,
                "redistribution_allowed": False,
                "missing_values_inferred": False,
                "structured_api_macros_claimed": False,
                "classified": False,
                "menu_eligible": False,
            }
        )
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def write_sqlite(path: Path, rows: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            );
            CREATE TABLE canonical_ocr (
                product_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                usable_complete INTEGER NOT NULL CHECK (usable_complete IN (0, 1)),
                latest_live_run_id INTEGER,
                workflow_names_json TEXT NOT NULL,
                calories REAL,
                protein_g REAL,
                carbohydrate_g REAL,
                fat_g REAL,
                nutrition_provenance_json TEXT,
                evidence_level TEXT NOT NULL CHECK (evidence_level = 'OCR_DERIVED_FROM_MERCADONA_IMAGE'),
                source TEXT NOT NULL CHECK (source = 'MERCADONA_FIRST_PARTY/label image'),
                source_record_kind TEXT NOT NULL CHECK (source_record_kind = 'label image'),
                redistribution_allowed INTEGER NOT NULL CHECK (redistribution_allowed = 0),
                missing_values_inferred INTEGER NOT NULL CHECK (missing_values_inferred = 0),
                structured_api_macros_claimed INTEGER NOT NULL CHECK (structured_api_macros_claimed = 0),
                classified INTEGER NOT NULL CHECK (classified = 0),
                menu_eligible INTEGER NOT NULL CHECK (menu_eligible = 0),
                CHECK (
                    (usable_complete = 1 AND status = 'DECLARED' AND latest_live_run_id IS NOT NULL
                     AND calories IS NOT NULL AND protein_g IS NOT NULL
                     AND carbohydrate_g IS NOT NULL AND fat_g IS NOT NULL
                     AND nutrition_provenance_json IS NOT NULL)
                    OR
                    (usable_complete = 0 AND latest_live_run_id IS NULL
                     AND calories IS NULL AND protein_g IS NULL
                     AND carbohydrate_g IS NULL AND fat_g IS NULL
                     AND nutrition_provenance_json IS NULL)
                )
            );
            """
        )
        connection.executemany(
            "INSERT INTO metadata(key, value_json) VALUES (?, ?)",
            [(key, json.dumps(value, ensure_ascii=False, sort_keys=True)) for key, value in sorted(manifest.items())],
        )
        for row in rows:
            nutrition = row["nutrition"] or {}
            connection.execute(
                """
                INSERT INTO canonical_ocr(
                    product_id, status, usable_complete, latest_live_run_id, workflow_names_json,
                    calories, protein_g, carbohydrate_g, fat_g, nutrition_provenance_json,
                    evidence_level, source, source_record_kind, redistribution_allowed,
                    missing_values_inferred, structured_api_macros_claimed, classified, menu_eligible
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0)
                """,
                (
                    row["product_id"], row["status"], int(row["usable_complete"]), row["latest_live_run_id"],
                    json.dumps(row["workflow_names"], ensure_ascii=False, sort_keys=True),
                    nutrition.get("calories"), nutrition.get("protein_g"), nutrition.get("carbohydrate_g"),
                    nutrition.get("fat_g"),
                    json.dumps(row["nutrition_provenance"], ensure_ascii=False, sort_keys=True)
                    if row["nutrition_provenance"] is not None else None,
                    row["evidence_level"], row["source"], row["source_record_kind"],
                ),
            )
        connection.commit()
        stored = connection.execute("SELECT COUNT(*) FROM canonical_ocr").fetchone()[0]
        usable = connection.execute("SELECT COUNT(*) FROM canonical_ocr WHERE usable_complete = 1").fetchone()[0]
        if stored != len(rows) or usable != manifest["usable_complete"]:
            raise RuntimeError("SQLite verification count mismatch")
    finally:
        connection.close()


def build_manifest(rows: list[dict[str, Any]], inventory_total: int) -> dict[str, Any]:
    status_counts = Counter(row["status"] for row in rows)
    usable = [row for row in rows if row["usable_complete"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "source_record_kind": SOURCE_RECORD_KIND,
        "evidence_level": EVIDENCE,
        "redistribution_allowed": False,
        "inventory_products": inventory_total,
        "processed_canonical_products": len(rows),
        "processed_pct_inventory": round(len(rows) / inventory_total * 100.0, 4),
        "status_counts": dict(sorted(status_counts.items())),
        "usable_complete": len(usable),
        "usable_complete_pct_inventory": round(len(usable) / inventory_total * 100.0, 4),
        "usable_field_counts": {field: len(usable) for field in NUTRITION_FIELDS},
        "nonusable_latest_live_run_locator_materialized": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "structured_api_macros_claimed": False,
        "classified": 0,
        "menu_eligible": 0,
        "policy": (
            "Materialized from the conservative latest-live OCR reconciliation. REVIEW and every other non-usable "
            "canonical state retain null nutrition. Only complete latest-live DECLARED rows are staged as usable, "
            "with every macro explicitly marked OCR_DERIVED_FROM_MERCADONA_IMAGE. Diagnostic replay union rows never "
            "replace the live run locator attached to usable macro provenance. Non-usable live run locators are left "
            "null because the current summary intentionally does not expose them per product."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--jsonl", required=True)
    parser.add_argument("--sqlite", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--inventory-total", type=int, default=4280)
    args = parser.parse_args()

    if args.inventory_total <= 0:
        raise SystemExit("--inventory-total must be positive")
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise SystemExit("summary must be a JSON object")

    rows = build_canonical_rows(summary)
    manifest = build_manifest(rows, args.inventory_total)
    write_jsonl(Path(args.jsonl), rows)
    write_sqlite(Path(args.sqlite), rows, manifest)
    Path(args.manifest).write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
