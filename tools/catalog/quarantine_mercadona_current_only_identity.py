from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"
SOURCE = "MERCADONA_FIRST_PARTY/label image"
CURRENT_ONLY_WORKFLOW_NAMES = frozenset({
    "Catalog Mercadona neural OCR p9 no-ingredients current delta",
})


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def current_only_introductions(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    runs = summary.get("runs")
    if not isinstance(runs, list):
        raise ValueError("summary.runs must be a list")
    seen: set[str] = set()
    out: dict[str, dict[str, Any]] = {}
    for run in sorted(runs, key=lambda item: int(item.get("run_id") or 0)):
        if not isinstance(run, dict):
            raise ValueError("summary.runs entries must be objects")
        run_id = run.get("run_id")
        names = run.get("workflow_names") or []
        new_ids = [str(value) for value in (run.get("new_product_ids") or [])]
        if isinstance(run_id, bool) or not isinstance(run_id, int):
            raise ValueError("run_id must be an integer")
        if not isinstance(names, list):
            raise ValueError("workflow_names must be a list")
        workflow_names = {str(value) for value in names}
        for product_id in new_ids:
            if not product_id or product_id in seen:
                continue
            seen.add(product_id)
            if workflow_names & CURRENT_ONLY_WORKFLOW_NAMES:
                out[product_id] = {
                    "first_seen_run_id": run_id,
                    "workflow_names": sorted(workflow_names),
                    "reason": "FIRST_SEEN_ONLY_IN_CURRENT_SNAPSHOT_WORKFLOW_WITHOUT_2026_08_27_EAN_PARITY_PROOF",
                }
    return out


def validate_row(row: dict[str, Any]) -> None:
    if row.get("evidence_level") != EVIDENCE:
        raise ValueError(f"unexpected evidence level for {row.get('product_id')}")
    if row.get("source") != SOURCE:
        raise ValueError(f"unexpected source for {row.get('product_id')}")
    if row.get("redistribution_allowed") is not False:
        raise ValueError(f"redistribution must remain disallowed for {row.get('product_id')}")
    if row.get("missing_values_inferred") is not False:
        raise ValueError(f"missing values must not be inferred for {row.get('product_id')}")
    if row.get("classified") is not False or row.get("menu_eligible") is not False:
        raise ValueError(f"semantic flags must remain false for {row.get('product_id')}")


def build_safe_subset(summary: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    quarantined = current_only_introductions(summary)
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("canonical rows must be objects")
        validate_row(row)
        product_id = str(row.get("product_id") or "")
        if not product_id or product_id in by_id:
            raise ValueError(f"missing or duplicate canonical product id: {product_id!r}")
        by_id[product_id] = row

    safe_rows = [row for pid, row in by_id.items() if pid not in quarantined]
    safe_rows.sort(key=lambda row: (0, int(str(row["product_id"]))) if str(row["product_id"]).isdigit() else (1, str(row["product_id"])))
    quarantined_rows = [by_id[pid] for pid in sorted(quarantined) if pid in by_id]
    quarantined_usable = sorted(str(row["product_id"]) for row in quarantined_rows if row.get("usable_complete") is True)
    input_usable = [row for row in rows if row.get("usable_complete") is True]
    safe_usable = [row for row in safe_rows if row.get("usable_complete") is True]
    manifest = {
        "policy": "QUARANTINE_CURRENT_ONLY_FIRST_SEEN_IDENTITIES_UNTIL_2026_08_27_EAN_PARITY_IS_PROVEN",
        "source": SOURCE,
        "evidence_level": EVIDENCE,
        "redistribution_allowed": False,
        "inventory_products": 4280,
        "input_canonical_products": len(rows),
        "input_canonical_usable_complete": len(input_usable),
        "safe_subset_products": len(safe_rows),
        "safe_subset_pct_inventory": round(len(safe_rows) * 100 / 4280, 4),
        "safe_subset_status_counts": dict(sorted(Counter(str(row.get("status") or "UNKNOWN") for row in safe_rows).items())),
        "safe_subset_usable_complete": len(safe_usable),
        "safe_subset_usable_pct_inventory": round(len(safe_usable) * 100 / 4280, 4),
        "quarantined_current_only_products": len(quarantined_rows),
        "quarantined_current_only_product_ids": sorted(str(row["product_id"]) for row in quarantined_rows),
        "quarantined_usable_product_ids": quarantined_usable,
        "quarantine_details": {pid: meta for pid, meta in sorted(quarantined.items()) if pid in by_id},
        "historical_snapshot_full_parity_verified": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "structured_api_macros_claimed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    return safe_rows, manifest


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_sqlite(path: Path, rows: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    try:
        db.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)")
        db.execute("CREATE TABLE canonical_ocr_safe_subset (product_id TEXT PRIMARY KEY, status TEXT NOT NULL, usable_complete INTEGER NOT NULL, payload_json TEXT NOT NULL)")
        db.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            [(key, json.dumps(value, ensure_ascii=False, sort_keys=True)) for key, value in sorted(manifest.items())],
        )
        db.executemany(
            "INSERT INTO canonical_ocr_safe_subset VALUES (?, ?, ?, ?)",
            [(
                str(row["product_id"]),
                str(row.get("status") or "UNKNOWN"),
                1 if row.get("usable_complete") is True else 0,
                json.dumps(row, ensure_ascii=False, sort_keys=True),
            ) for row in rows],
        )
        db.commit()
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--canonical-jsonl", required=True)
    parser.add_argument("--out-jsonl", required=True)
    parser.add_argument("--out-sqlite", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    rows = load_jsonl(Path(args.canonical_jsonl))
    safe_rows, manifest = build_safe_subset(summary, rows)
    write_jsonl(Path(args.out_jsonl), safe_rows)
    write_sqlite(Path(args.out_sqlite), safe_rows, manifest)
    Path(args.manifest).write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
