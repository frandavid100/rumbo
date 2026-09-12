from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Iterable

SOURCE = "MERCADONA_FIRST_PARTY"
EVIDENCE_TYPE = "OBSERVED_API"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_token(value: Any) -> str | None:
    if value is None or isinstance(value, bool) or isinstance(value, float):
        return None
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def load_jsonl_tree(root: Path, pattern: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob(pattern)):
        rows.extend(load_jsonl(path))
    return rows


def is_http_404_fetch_error(value: str) -> bool:
    text = str(value or "")
    return "HTTPError" in text and re.search(r"(?<!\d)404(?!\d)", text) is not None


def audit_identity_rows(
    anchors: Iterable[dict[str, Any]],
    details: Iterable[dict[str, Any]],
    errors: Iterable[dict[str, Any]],
    *,
    observed_at: str | None = None,
    anchor_source: str = "MERCADONA_OCR_RUN_UNION/latest_usable_products",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    anchor_by_id: dict[str, str] = {}
    for row in anchors:
        product_id = normalize_token(row.get("product_id"))
        ean = normalize_token(row.get("ean"))
        if not product_id or not ean:
            raise ValueError("Every identity anchor must contain non-empty product_id and ean")
        prior = anchor_by_id.get(product_id)
        if prior is not None and prior != ean:
            raise ValueError(f"Conflicting anchor EANs for product_id={product_id}: {prior} vs {ean}")
        anchor_by_id[product_id] = ean

    details_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in details:
        product_id = normalize_token(row.get("product_id"))
        if product_id:
            details_by_id[product_id].append(row)

    errors_by_id: dict[str, list[str]] = defaultdict(list)
    for row in errors:
        product_id = normalize_token(row.get("product_id"))
        if product_id:
            errors_by_id[product_id].append(str(row.get("error") or "UNKNOWN_FETCH_ERROR"))

    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)
    for product_id, anchor_ean in sorted(anchor_by_id.items(), key=lambda item: (len(item[0]), item[0])):
        current_rows = details_by_id.get(product_id, [])
        current_eans = {
            ean
            for ean in (normalize_token(row.get("ean")) for row in current_rows)
            if ean is not None
        }
        current_names = sorted({
            str(row.get("name")).strip()
            for row in current_rows
            if isinstance(row.get("name"), str) and row.get("name").strip()
        })
        source_urls = sorted({
            str(row.get("source_url")).strip()
            for row in current_rows
            if isinstance(row.get("source_url"), str) and row.get("source_url").strip()
        })
        fetch_errors = sorted(set(errors_by_id.get(product_id, [])))

        if len(current_eans) > 1:
            status = "AMBIGUOUS_CURRENT_IDENTITY"
        elif len(current_eans) == 1:
            current_ean = next(iter(current_eans))
            status = "MATCH" if current_ean == anchor_ean else "REASSIGNED_PRODUCT_ID"
        elif current_rows:
            status = "MISSING_CURRENT_EAN"
        elif fetch_errors and all(is_http_404_fetch_error(error) for error in fetch_errors):
            status = "CURRENT_PRODUCT_NOT_FOUND"
        elif fetch_errors:
            status = "FETCH_ERROR"
        else:
            status = "NO_CURRENT_OBSERVATION"

        counts[status] += 1
        rows.append({
            "product_id": product_id,
            "anchor_ean": anchor_ean,
            "current_eans": sorted(current_eans),
            "current_names": current_names,
            "source_urls": source_urls,
            "fetch_errors": fetch_errors,
            "status": status,
            "canonical_mutation_allowed": False,
        })

    audited = len(anchor_by_id)
    matched = counts.get("MATCH", 0)
    reassigned = counts.get("REASSIGNED_PRODUCT_ID", 0)
    current_not_found = counts.get("CURRENT_PRODUCT_NOT_FOUND", 0)
    unresolved = audited - matched - reassigned
    report = {
        "schema_version": "1.1.0",
        "source": SOURCE,
        "evidence_type": EVIDENCE_TYPE,
        "anchor_source": anchor_source,
        "observed_at": observed_at or _now(),
        "policy": (
            "Compare the immutable EAN attached to each canonically usable Mercadona OCR product_id "
            "with a fresh official first-party product-detail observation. A different current EAN "
            "proves product_id reuse/reassignment and is reported only as an identity hazard; this "
            "audit never mutates historical canonical OCR nutrition. An explicit HTTP 404 is recorded "
            "separately as CURRENT_PRODUCT_NOT_FOUND: it proves that the current product-detail endpoint "
            "does not expose that id at audit time, but it does not prove reassignment. Missing/unavailable "
            "current identity fails closed and remains unresolved."
        ),
        "anchored_products": audited,
        "matched_products": matched,
        "reassigned_product_ids": reassigned,
        "current_not_found_products": current_not_found,
        "unresolved_products": unresolved,
        "status_counts": dict(sorted(counts.items())),
        "reassigned_ids": [row["product_id"] for row in rows if row["status"] == "REASSIGNED_PRODUCT_ID"],
        "current_not_found_ids": [row["product_id"] for row in rows if row["status"] == "CURRENT_PRODUCT_NOT_FOUND"],
        "unresolved_ids": [
            row["product_id"]
            for row in rows
            if row["status"] not in {"MATCH", "REASSIGNED_PRODUCT_ID"}
        ],
        "images_downloaded": False,
        "images_persisted": False,
        "nutrition_values_changed": False,
        "missing_values_inferred": False,
        "classified": 0,
        "menu_eligible": 0,
    }
    return report, rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchors", required=True)
    ap.add_argument("--details-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--anchor-source", default="MERCADONA_OCR_RUN_UNION/latest_usable_products")
    args = ap.parse_args()

    anchors = load_jsonl(Path(args.anchors))
    details_root = Path(args.details_root)
    details = load_jsonl_tree(details_root, "details-*.jsonl")
    errors = load_jsonl_tree(details_root, "errors-*.jsonl")
    report, rows = audit_identity_rows(anchors, details, errors, anchor_source=args.anchor_source)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "identities.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (out / "reassigned.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
            if row["status"] == "REASSIGNED_PRODUCT_ID"
        ),
        encoding="utf-8",
    )
    (out / "unresolved.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
            if row["status"] not in {"MATCH", "REASSIGNED_PRODUCT_ID"}
        ),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
