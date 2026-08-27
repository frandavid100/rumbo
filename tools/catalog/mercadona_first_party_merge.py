from __future__ import annotations

import argparse
from collections import Counter
import glob
import json
from pathlib import Path
import sqlite3
from typing import Any

SOURCE = "MERCADONA_FIRST_PARTY"
EVIDENCE_TYPE = "OBSERVED_API"


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _merge(base: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in detail.items():
        if key == "field_evidence":
            continue
        if _present(value) or key in ("published", "is_bulk", "is_variable_weight", "is_new_arrival", "is_prepared_by_mercadona"):
            result[key] = value
    evidence = dict(base.get("field_evidence") or {})
    evidence.update(detail.get("field_evidence") or {})
    result["field_evidence"] = evidence
    return result


def _coverage(rows: list[dict[str, Any]], field: str) -> dict[str, float | int]:
    count = sum(1 for row in rows if _present(row.get(field)))
    return {"present": count, "pct": round(100 * count / len(rows), 2) if rows else 0.0}


def _build_sqlite(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    try:
        db.executescript(
            """
            CREATE TABLE products (
                product_id TEXT PRIMARY KEY,
                ean TEXT,
                name TEXT,
                brand TEXT,
                origin TEXT,
                packaging TEXT,
                published INTEGER,
                price REAL,
                unit_price REAL,
                unit_size REAL,
                unit_name TEXT,
                bulk_price REAL,
                category_id TEXT,
                category_name TEXT,
                legal_name TEXT,
                description TEXT,
                suppliers_json TEXT NOT NULL,
                ingredients TEXT,
                allergens TEXT,
                storage_instructions TEXT,
                usage_instructions TEXT,
                photos_json TEXT NOT NULL,
                photo_count INTEGER NOT NULL,
                source TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                observed_at TEXT,
                detail_observed INTEGER NOT NULL,
                record_json TEXT NOT NULL
            );
            CREATE TABLE field_evidence (
                product_id TEXT NOT NULL,
                field TEXT NOT NULL,
                source TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                observed_at TEXT,
                source_url TEXT,
                PRIMARY KEY (product_id, field)
            );
            CREATE INDEX field_evidence_source_idx ON field_evidence(source, evidence_type);
            """
        )
        for row in rows:
            pid = str(row.get("product_id") or "")
            db.execute(
                """INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    pid, row.get("ean"), row.get("name"), row.get("brand"), row.get("origin"), row.get("packaging"),
                    int(row["published"]) if isinstance(row.get("published"), bool) else None,
                    row.get("price"), row.get("unit_price"), row.get("unit_size"), row.get("unit_name"), row.get("bulk_price"),
                    row.get("category_id"), row.get("category_name"), row.get("legal_name"), row.get("description"),
                    json.dumps(row.get("suppliers") or [], ensure_ascii=False), row.get("ingredients"), row.get("allergens"),
                    row.get("storage_instructions"), row.get("usage_instructions"),
                    json.dumps(row.get("photos") or [], ensure_ascii=False), int(row.get("photo_count") or 0),
                    row.get("source") or SOURCE, row.get("evidence_type") or EVIDENCE_TYPE, row.get("observed_at"),
                    int(bool(row.get("detail_observed"))), json.dumps(row, ensure_ascii=False, sort_keys=True),
                ),
            )
            for field, ev in (row.get("field_evidence") or {}).items():
                if not isinstance(ev, dict):
                    continue
                db.execute(
                    "INSERT OR REPLACE INTO field_evidence VALUES (?,?,?,?,?,?)",
                    (pid, field, ev.get("source") or SOURCE, ev.get("evidence_type") or EVIDENCE_TYPE,
                     ev.get("observed_at"), ev.get("source_url")),
                )
        db.commit()
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--details-glob", required=True)
    ap.add_argument("--errors-glob")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    inventory = _load_jsonl(Path(args.inventory))
    by_id = {str(row.get("product_id")): row for row in inventory if row.get("product_id")}
    detail_files = [Path(p) for p in sorted(glob.glob(args.details_glob, recursive=True))]
    details: list[dict[str, Any]] = []
    for path in detail_files:
        details.extend(_load_jsonl(path))
    for detail in details:
        pid = str(detail.get("product_id") or "")
        if not pid:
            continue
        by_id[pid] = _merge(by_id.get(pid, {"product_id": pid}), detail)

    rows = list(by_id.values())
    rows.sort(key=lambda row: (len(str(row.get("product_id") or "")), str(row.get("product_id") or "")))
    errors: list[dict[str, Any]] = []
    if args.errors_glob:
        for path in [Path(p) for p in sorted(glob.glob(args.errors_glob, recursive=True))]:
            errors.extend(_load_jsonl(path))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "products.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    (out / "errors.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in errors), encoding="utf-8")
    _build_sqlite(out / "mercadona-first-party.sqlite", rows)

    fields = [
        "ean", "name", "brand", "origin", "packaging", "price", "unit_price", "unit_size", "unit_name", "bulk_price",
        "category_id", "category_name", "photos", "legal_name", "description", "suppliers", "ingredients", "allergens",
        "mandatory_mentions", "usage_instructions", "storage_instructions", "alcohol_by_volume", "share_url",
    ]
    summary = {
        "source": SOURCE,
        "evidence_type": EVIDENCE_TYPE,
        "status": "OK" if rows and not errors else ("PARTIAL" if rows else "EMPTY"),
        "inventory_products": len(inventory),
        "products": len(rows),
        "detail_records": len(details),
        "detail_observed_products": sum(1 for row in rows if row.get("detail_observed")),
        "errors": len(errors),
        "error_types": dict(Counter(str(row.get("error", "")).split(":", 1)[0] for row in errors)),
        "coverage": {field: _coverage(rows, field) for field in fields},
        "products_with_multiple_photos": sum(1 for row in rows if int(row.get("photo_count") or 0) >= 2),
        "products_with_label_candidate_photos": sum(1 for row in rows if int(row.get("photo_count") or 0) >= 2),
        "classification": {"classified": 0, "menu_eligible": 0, "policy": "EXTRACTION_ONLY_NO_SEMANTIC_REVIEW"},
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
