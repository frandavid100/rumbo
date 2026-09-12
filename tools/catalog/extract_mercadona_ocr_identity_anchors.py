from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from summarize_mercadona_ocr_run_union import (
    EVIDENCE,
    VALID,
    has_strict_raw_provenance,
    is_canonical_status_row,
    normalize_ean,
    reconcile_latest_observations,
)


def extract_identity_anchors(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    observations: list[tuple[int, str, str, Any, bool, Any]] = []
    source_rows = 0
    for path in sorted(root.rglob("*.jsonl")):
        rel = path.relative_to(root)
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
            product_id = str(row.get("product_id") or "").strip()
            status = str(row.get("status") or "")
            if not product_id or status not in VALID or row.get("evidence_level") != EVIDENCE:
                continue
            if not is_canonical_status_row(row):
                continue
            source_rows += 1
            observations.append(
                (
                    int(run_id),
                    product_id,
                    status,
                    row.get("nutrition"),
                    has_strict_raw_provenance(row),
                    normalize_ean(row.get("ean")),
                )
            )

    latest = reconcile_latest_observations(observations)
    anchors: list[dict[str, Any]] = []
    unresolved_ids: list[str] = []
    conflict_ids: list[str] = []
    unverified_ids: list[str] = []
    for product_id, item in sorted(latest.items(), key=lambda pair: (len(pair[0]), pair[0])):
        ean = normalize_ean(item.get("identity_ean"))
        if ean is None:
            unresolved_ids.append(product_id)
            continue
        if item.get("identity_conflict_run_ids"):
            conflict_ids.append(product_id)
        if item.get("identity_unverified_run_ids"):
            unverified_ids.append(product_id)
        anchors.append({
            "product_id": product_id,
            "ean": ean,
            "canonical_status": item.get("status"),
            "latest_run_id": item.get("latest_run_id"),
            "usable_complete": item.get("usable_complete") is True,
            "identity_anchor_source": item.get("identity_anchor_source"),
            "identity_conflict_run_ids": item.get("identity_conflict_run_ids", []),
            "identity_conflict_eans": item.get("identity_conflict_eans", []),
            "identity_unverified_run_ids": item.get("identity_unverified_run_ids", []),
        })

    summary = {
        "schema_version": "1.0.0",
        "policy": "Reuse summarize_mercadona_ocr_run_union.reconcile_latest_observations; emit only products with an exact earliest raw-live EAN anchor. Derived canonical/replay rows do not participate.",
        "raw_live_exact_evidence_rows": source_rows,
        "canonical_products": len(latest),
        "anchored_products": len(anchors),
        "identity_unresolved_products": len(unresolved_ids),
        "identity_unresolved_product_ids": unresolved_ids,
        "identity_conflict_products": len(conflict_ids),
        "identity_conflict_product_ids": conflict_ids,
        "identity_unverified_products": len(unverified_ids),
        "identity_unverified_product_ids": unverified_ids,
        "images_downloaded": False,
        "images_persisted": False,
    }
    return anchors, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--summary", required=True)
    args = ap.parse_args()

    anchors, summary = extract_identity_anchors(Path(args.root))
    Path(args.jsonl).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in anchors),
        encoding="utf-8",
    )
    Path(args.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if anchors else 2


if __name__ == "__main__":
    raise SystemExit(main())
