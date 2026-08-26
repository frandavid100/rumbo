from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def sku_of(row: dict[str, Any]) -> str:
    return str(row.get("sku") or row.get("retailer_sku") or "").strip()


def useful(value: Any) -> bool:
    return value not in (None, "", [], {})


def score(row: dict[str, Any]) -> int:
    return sum(1 for value in row.values() if useful(value))


def merge_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    # Start from the richest exact first-party observation and only fill blanks.
    # Conflicting observed values are deliberately not guessed or combined.
    ordered = sorted(rows, key=score, reverse=True)
    merged = dict(ordered[0])
    for row in ordered[1:]:
        for key, value in row.items():
            if not useful(merged.get(key)) and useful(value):
                merged[key] = value
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--products", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--minimum", type=int, default=13877)
    args = parser.parse_args()

    candidates = sorted(args.root.glob("*/products.jsonl"))
    if not candidates:
        raise SystemExit("No downloadable Alcampo enumeration products.jsonl artifacts found")

    by_sku: dict[str, list[dict[str, Any]]] = {}
    source_counts: dict[str, int] = {}
    best_report: dict[str, Any] = {}
    best_report_count = -1
    best_report_source = ""

    for products_path in candidates:
        source = products_path.parent.name
        seen_here: set[str] = set()
        with products_path.open(encoding="utf-8") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                row = json.loads(raw)
                sku = sku_of(row)
                if not sku:
                    continue
                by_sku.setdefault(sku, []).append(row)
                seen_here.add(sku)
        source_counts[source] = len(seen_here)

        report_path = products_path.parent / "enumeration_report.json"
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                report = {}
            reported = int(report.get("unique_products_after_dedup") or len(seen_here))
            if reported > best_report_count:
                best_report = report
                best_report_count = reported
                best_report_source = source

    merged = [merge_rows(rows) for _, rows in sorted(by_sku.items())]
    args.products.parent.mkdir(parents=True, exist_ok=True)
    with args.products.open("w", encoding="utf-8") as handle:
        for row in merged:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    report = dict(best_report)
    report.update(
        {
            "complete_enumeration": False,
            "unique_products_after_dedup": len(merged),
            "completeness_basis": (
                "Cumulative union of downloadable FIRST_PARTY_ALCAMPO enumeration artifacts. "
                "Preserves the widest observed SKU inventory but is not proof of complete enumeration."
            ),
            "cumulative_union": True,
            "cumulative_union_sources": source_counts,
            "cumulative_union_best_report_source": best_report_source,
        }
    )
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "artifacts": len(candidates),
        "unique_products": len(merged),
        "largest_single_artifact": max(source_counts.values(), default=0),
        "sources": source_counts,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if len(merged) < args.minimum:
        raise SystemExit(
            f"Cumulative first-party enumeration has only {len(merged)} unique SKUs; "
            f"refusing to regress below stable floor {args.minimum}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
