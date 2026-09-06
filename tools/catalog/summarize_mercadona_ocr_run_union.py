from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

VALID = {"DECLARED", "REVIEW", "NO_VISUAL_REGION", "ERROR"}
EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"


def load_run_names(tsv: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    if not tsv.exists():
        return out
    for line in tsv.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out[parts[0]].add(parts[1])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--artifacts-tsv", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    by_run: dict[str, set[str]] = defaultdict(set)
    by_run_status: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    files_by_run: dict[str, set[str]] = defaultdict(set)
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

    result = {
        "policy": "Chronological strict-provenance union diagnostic only; product IDs are never promoted or classified here.",
        "runs_with_strict_ocr_rows": len(rows),
        "final_distinct_union": len(seen),
        "runs": rows,
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"runs_with_strict_ocr_rows": len(rows), "final_distinct_union": len(seen)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
