#!/usr/bin/env python3
"""Build a discovery-only queue of Carrefour candidate URLs not yet directly verified.

The candidate input may come from external discovery sources such as RadarSuper. This
script NEVER promotes those hints to Carrefour first-party evidence. It only removes
product IDs already present in the verified cumulative first-party staging and emits a
bounded, deterministic work queue plus counts for auditing.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


SKU_IN_URL_RE = re.compile(r"/R-([^/]+)/p(?:$|[?#])", re.IGNORECASE)


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if isinstance(value, dict):
            rows.append(value)
    return rows


def norm_sku(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def candidate_sku(row: dict[str, Any]) -> tuple[str | None, str]:
    # The RadarSuper export's retailer_sku_candidate may be an external slug, while the
    # canonical Carrefour URL embeds Carrefour's real R- product identifier. Prefer the
    # official-looking URL identifier as a discovery hint; it still becomes evidence only
    # after direct observation on Carrefour.
    url = str(row.get("canonical_url") or row.get("url") or "").strip()
    match = SKU_IN_URL_RE.search(url)
    if match:
        return norm_sku(match.group(1)), "CARREFOUR_URL_CANDIDATE"
    for key in ("retailer_sku", "sku", "product_id", "retailer_sku_candidate"):
        sku = norm_sku(row.get(key))
        if sku:
            return sku, f"FIELD_{key.upper()}_CANDIDATE"
    return None, "MISSING"


def candidate_key(row: dict[str, Any]) -> tuple[int, int, str, str]:
    has_gtin_hint = 0 if norm_sku(row.get("gtin_hint_external")) else 1
    has_name_hint = 0 if str(row.get("name_hint_external") or "").strip() else 1
    name = str(row.get("name_hint_external") or "").casefold()
    sku = norm_sku(row.get("retailer_sku")) or ""
    return (has_gtin_hint, has_name_hint, name, sku)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="fixtures/carrefour_candidate_urls_radarsuper.jsonl", type=Path)
    parser.add_argument("--verified", default="fixtures/carrefour_first_party_products_cumulative.jsonl", type=Path)
    parser.add_argument("--output", default="fixtures/carrefour_unverified_candidates_head.jsonl", type=Path)
    parser.add_argument("--summary", default="fixtures/carrefour_unverified_candidates_summary.json", type=Path)
    parser.add_argument("--limit", type=int, default=250)
    args = parser.parse_args()

    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")

    verified_rows = list(read_jsonl(args.verified))
    verified_skus = {
        sku
        for row in verified_rows
        if str(row.get("source") or "") == "CARREFOUR_FIRST_PARTY"
        for sku in [norm_sku(row.get("retailer_sku"))]
        if sku
    }

    candidate_rows = list(read_jsonl(args.candidates))
    by_sku: dict[str, tuple[dict[str, Any], str]] = {}
    missing_sku = 0
    id_source_counts: dict[str, int] = {}
    for row in candidate_rows:
        sku, id_source = candidate_sku(row)
        id_source_counts[id_source] = id_source_counts.get(id_source, 0) + 1
        if not sku:
            missing_sku += 1
            continue
        by_sku.setdefault(sku, (row, id_source))

    unverified: list[dict[str, Any]] = []
    already_verified = 0
    for sku, (row, id_source) in by_sku.items():
        if sku in verified_skus:
            already_verified += 1
            continue
        selected = {
            "retailer": "CARREFOUR",
            "candidate_source": str(row.get("candidate_source") or "EXTERNAL_DISCOVERY_ONLY"),
            "candidate_source_url": row.get("candidate_source_url"),
            "retailer_sku": sku,
            "retailer_sku_candidate_source": id_source,
            "external_retailer_sku_candidate": norm_sku(row.get("retailer_sku_candidate")),
            "gtin_hint_external": norm_sku(row.get("gtin") or row.get("ean") or row.get("barcode")),
            "name_hint_external": row.get("name_hint") or row.get("name"),
            "canonical_url_candidate": row.get("canonical_url") or row.get("url"),
            "canonical_url_verified": False,
            "selection_reason": "NOT_YET_DIRECTLY_VERIFIED",
            "evidence_status": "DISCOVERY_ONLY_NOT_CARREFOUR_EVIDENCE",
            "provenance_note": (
                "External discovery hint only. The Carrefour R- identifier parsed from the URL is "
                "used solely to prioritize verification. Do not attribute any field in this row to "
                "Carrefour until an official Carrefour surface is directly observed."
            ),
        }
        unverified.append(selected)

    unverified.sort(key=candidate_key)
    selected_rows = unverified[: args.limit]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in selected_rows),
        encoding="utf-8",
    )

    summary = {
        "source_boundary": {
            "candidate_input": "EXTERNAL_DISCOVERY_ONLY",
            "verified_input": "CARREFOUR_FIRST_PARTY",
            "output_is_first_party_evidence": False,
        },
        "counts": {
            "candidate_rows": len(candidate_rows),
            "candidate_unique_carrefour_url_ids": len(by_sku),
            "candidate_rows_missing_product_id": missing_sku,
            "verified_first_party_unique_skus": len(verified_skus),
            "candidate_ids_already_verified": already_verified,
            "candidate_ids_not_yet_verified": len(unverified),
            "queue_rows_emitted": len(selected_rows),
            "queue_limit": args.limit,
            "unverified_with_external_gtin_hint": sum(1 for row in unverified if row.get("gtin_hint_external")),
            "unverified_with_external_name_hint": sum(1 for row in unverified if row.get("name_hint_external")),
        },
        "candidate_id_source_counts": id_source_counts,
        "queue_order": "external GTIN hint first, then name hint, then casefolded name and Carrefour URL product ID",
        "notes": [
            "This queue is only a prioritization aid for direct official Carrefour verification.",
            "No external candidate value is promoted to CARREFOUR_FIRST_PARTY evidence by this script.",
            "The RadarSuper export carries an external retailer_sku_candidate that can be a slug; the Carrefour R- ID is therefore parsed preferentially from the candidate URL.",
        ],
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["counts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
