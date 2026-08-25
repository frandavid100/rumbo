from __future__ import annotations

import argparse
import json
from pathlib import Path

import carrefour_first_party_analytics_inventory as analytics

SOURCE = analytics.SOURCE
ANALYTICS_PATH = "/cloud-api/pdp-food-analytics/v1/impressions"
EMPTY = (None, "", [], {})


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def nonempty(value) -> bool:
    return value not in EMPTY


def evidence_key(row: dict) -> tuple:
    return (
        row.get("retailer_sku"), row.get("field"), row.get("source"), row.get("evidence_type"),
        row.get("source_url"), row.get("observed_at"),
        json.dumps(row.get("value"), ensure_ascii=False, sort_keys=True),
    )


def parse_payload(network_row: dict):
    if network_row.get("status") != 200:
        return None
    if ANALYTICS_PATH not in str(network_row.get("url") or ""):
        return None
    body = network_row.get("body_sample")
    if not isinstance(body, str) or not body.strip():
        return None
    # browser inventory only stores body_sample when the full response fits the configured body limit;
    # a truncated sample must never be treated as a declaration.
    body_bytes = network_row.get("body_bytes")
    if isinstance(body_bytes, int) and len(body.encode()) < body_bytes:
        return None
    try:
        payload = json.loads(body)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inventory_dir")
    args = ap.parse_args()
    root = Path(args.inventory_dir)
    products_path = root / "products.jsonl"
    evidence_path = root / "field_evidence.jsonl"
    network_path = root / "network_responses.jsonl"

    products = read_jsonl(products_path)
    evidence = read_jsonl(evidence_path)
    network = read_jsonl(network_path)
    by_sku = {str(row.get("retailer_sku")): row for row in products if row.get("retailer_sku")}
    existing_evidence = {evidence_key(row) for row in evidence}

    analytics_responses = 0
    matched_responses = 0
    fields_added = 0
    evidence_added = 0
    touched_skus = set()

    for network_row in network:
        payload = parse_payload(network_row)
        if payload is None:
            continue
        analytics_responses += 1
        sku = str(network_row.get("retailer_sku") or "").strip()
        target = by_sku.get(sku)
        if not target or target.get("fetch_error"):
            continue
        observed_at = str(target.get("observed_at") or analytics.now_iso())
        parsed, analytics_evidence = analytics.parse_impression(
            sku,
            payload,
            str(network_row.get("url") or analytics.ENDPOINT),
            observed_at,
        )
        if not parsed:
            continue
        matched_responses += 1
        touched_skus.add(sku)

        for field in ("gtin", "brand", "price_eur", "price_currency"):
            value = parsed.get(field)
            if nonempty(value) and not nonempty(target.get(field)):
                target[field] = value
                fields_added += 1

        attrs = parsed.get("attributes")
        if isinstance(attrs, dict) and attrs:
            old = target.get("attributes") if isinstance(target.get("attributes"), dict) else {}
            merged = dict(old)
            before = len(merged)
            for key, value in attrs.items():
                if nonempty(value):
                    merged[key] = value
            target["attributes"] = merged
            fields_added += max(0, len(merged) - before)

        target["analytics_payload_sha256"] = parsed.get("analytics_payload_sha256")
        target["analytics_source_url"] = parsed.get("analytics_source_url")

        for ev in analytics_evidence:
            key = evidence_key(ev)
            if key in existing_evidence:
                continue
            evidence.append(ev)
            existing_evidence.add(key)
            evidence_added += 1

    products.sort(key=lambda row: str(row.get("retailer_sku") or ""))
    evidence.sort(key=lambda row: (
        str(row.get("retailer_sku") or ""), str(row.get("field") or ""),
        str(row.get("observed_at") or ""), str(row.get("evidence_type") or ""),
    ))
    write_jsonl(products_path, products)
    write_jsonl(evidence_path, evidence)

    summary = {
        "source": SOURCE,
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "classification_performed": False,
        "network_responses_seen": len(network),
        "analytics_responses_complete_json": analytics_responses,
        "analytics_responses_matched": matched_responses,
        "product_fields_or_attributes_added": fields_added,
        "evidence_rows_added": evidence_added,
        "products_touched": len(touched_skus),
        "touched_skus": sorted(touched_skus),
        "provenance_note": (
            "Only complete HTTP-200 JSON responses observed directly while loading the matching Carrefour product page "
            "are used. Analytics values are marked OBSERVED_PRODUCT_ANALYTICS, not manufacturer DECLARED data."
        ),
    }
    (root / "analytics_network_augmentation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
