from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SOURCE = "CARREFOUR_FIRST_PARTY"
VERSION = "carrefour-first-party-analytics-inventory-1.1"
BASE = "https://www.carrefour.es"
ENDPOINT = BASE + "/cloud-api/pdp-food-analytics/v1/impressions"
SKU_RE = re.compile(r"/R-([^/]+)/p/?(?:\?.*)?$", re.I)
GTIN_RE = re.compile(r"\d{8}|\d{12,14}")
SKU_VALID_RE = re.compile(r"[A-Za-z0-9._-]{3,80}")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer": "https://www.carrefour.es/supermercado/",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def valid_gtin(value: str) -> bool:
    if not GTIN_RE.fullmatch(value):
        return False
    digits = [int(c) for c in value]
    check = digits.pop()
    total = 0
    weight = 3
    for digit in reversed(digits):
        total += digit * weight
        weight = 1 if weight == 3 else 3
    return (10 - total % 10) % 10 == check


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
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


def candidate_skus(paths: list[str], explicit: list[str] | None = None) -> list[str]:
    # Explicit smoke/probe SKUs are kept first. Discovered candidates follow, with numeric
    # retailer IDs ahead of marketplace-style IDs because the food PDP endpoint is keyed by
    # Carrefour's own R-<numeric> food identifiers.
    priority = []
    seen_priority = set()
    for value in explicit or []:
        sku = str(value or "").strip()
        if sku and SKU_VALID_RE.fullmatch(sku) and sku not in seen_priority:
            priority.append(sku)
            seen_priority.add(sku)

    skus = set()
    for raw_path in paths:
        for row in read_jsonl(Path(raw_path)):
            sku = str(row.get("retailer_sku") or "").strip()
            if not sku:
                url = str(row.get("url") or row.get("canonical_url") or "")
                match = SKU_RE.search(url)
                sku = match.group(1) if match else ""
            if sku and SKU_VALID_RE.fullmatch(sku) and sku not in seen_priority:
                skus.add(sku)
    discovered = sorted(skus, key=lambda s: (not s.isdigit(), int(s) if s.isdigit() else s))
    return priority + discovered


def fetch_one(sku: str, timeout: int) -> tuple[int | None, dict | None, str | None, str]:
    query = urlencode({"product_id": f"R-{sku}", "referer": ""})
    url = ENDPOINT + "?" + query
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=timeout) as response:
            status = int(response.status)
            raw = response.read()
        try:
            payload = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception as exc:
            return status, None, f"INVALID_JSON:{type(exc).__name__}", url
        return status, payload if isinstance(payload, dict) else None, None, url
    except HTTPError as exc:
        return int(exc.code), None, f"HTTP_{exc.code}", url
    except URLError as exc:
        return None, None, f"URL_ERROR:{exc.reason}", url
    except Exception as exc:
        return None, None, f"{type(exc).__name__}:{exc}", url


def parse_impression(sku: str, payload: dict, source_url: str, observed_at: str) -> tuple[dict | None, list[dict]]:
    impressions = payload.get("impressions")
    if not isinstance(impressions, list) or not impressions:
        return None, []
    matches = []
    for item in impressions:
        if not isinstance(item, dict):
            continue
        internal = str(item.get("item_internal_id") or "").strip()
        if internal == sku:
            matches.append(item)
    if len(matches) != 1:
        return None, []
    item = matches[0]

    raw_eans = item.get("item_ean")
    if isinstance(raw_eans, str):
        raw_eans = [raw_eans]
    if not isinstance(raw_eans, list):
        raw_eans = []
    gtins = sorted({str(v).strip() for v in raw_eans if valid_gtin(str(v).strip())})
    gtin = gtins[0] if len(gtins) == 1 else None

    brand = str(item.get("item_brand") or "").strip() or None
    currency = str(item.get("currency") or "").strip() or None
    price = item.get("price") if isinstance(item.get("price"), (int, float)) else None
    attrs = {}
    mapping = {
        "carrefour_item_id": "item_id",
        "carrefour_sms_id": "item_sms",
        "carrefour_analytics_category_id": "item_category",
        "carrefour_provider": "item_provider",
        "carrefour_provider_type": "item_provider_type",
        "carrefour_shipping": "item_shipping",
        "carrefour_coupon": "coupon",
        "carrefour_analytics_name": "item_name",
    }
    for target, source in mapping.items():
        value = item.get(source)
        if value not in (None, "", [], {}):
            attrs[target] = value

    row = {
        "retailer": "CARREFOUR",
        "retailer_sku": sku,
        "source": SOURCE,
        "observed_at": observed_at,
        "gtin": gtin,
        "brand": brand,
        "price_eur": price,
        "price_currency": currency or ("EUR" if price is not None else None),
        "attributes": attrs,
        "analytics_only_observed": True,
        "analytics_payload_sha256": hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "analytics_source_url": source_url,
    }

    evidence = []
    for field in ("retailer_sku", "gtin", "brand", "price_eur", "price_currency", "attributes"):
        value = row.get(field)
        if value in (None, "", [], {}):
            continue
        evidence.append({
            "retailer_sku": sku,
            "field": field,
            "value": value,
            "source": SOURCE,
            "evidence_type": "OBSERVED_PRODUCT_ANALYTICS",
            "source_url": source_url,
            "observed_at": observed_at,
            "provenance_note": "Observed directly in Carrefour's public pdp-food-analytics response for this retailer SKU; not a manufacturer declaration.",
        })
    return row, evidence


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-jsonl", action="append", default=[])
    ap.add_argument("--sku", action="append", default=[], help="Explicit Carrefour retailer SKU(s), tested before discovered candidates.")
    ap.add_argument("--out", default="carrefour-first-party-analytics")
    ap.add_argument("--max-products", type=int, default=60)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--rotate", action="store_true")
    ap.add_argument("--stop-after-blocks", type=int, default=3)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    all_skus = candidate_skus(args.seed_jsonl, args.sku)
    explicit_count = len(candidate_skus([], args.sku))
    # Rotation is only applied to discovered candidates; explicit validation SKUs must remain first.
    if args.rotate and len(all_skus) > explicit_count:
        prefix = all_skus[:explicit_count]
        tail = all_skus[explicit_count:]
        offset = int(datetime.now(timezone.utc).timestamp() // 3600) % len(tail)
        all_skus = prefix + tail[offset:] + tail[:offset]
    selected = all_skus[: args.max_products] if args.max_products > 0 else all_skus

    products = []
    evidence = []
    audit = []
    consecutive_blocks = 0
    for index, sku in enumerate(selected, 1):
        observed_at = now_iso()
        status, payload, error, source_url = fetch_one(sku, args.timeout)
        row = None
        ev = []
        if payload is not None and not error:
            row, ev = parse_impression(sku, payload, source_url, observed_at)
            if row is None:
                error = "NO_MATCHING_IMPRESSION"
        blocked = status in {403, 429}
        consecutive_blocks = consecutive_blocks + 1 if blocked else 0
        if row:
            products.append(row)
            evidence.extend(ev)
        audit.append({
            "retailer_sku": sku,
            "source": SOURCE,
            "source_url": source_url,
            "observed_at": observed_at,
            "http_status": status,
            "error": error,
            "matched": bool(row),
        })
        print(json.dumps({"index": index, "sku": sku, "status": status, "matched": bool(row), "error": error}, ensure_ascii=False))
        if args.stop_after_blocks > 0 and consecutive_blocks >= args.stop_after_blocks:
            break
        if index < len(selected) and args.delay > 0:
            time.sleep(args.delay)

    products.sort(key=lambda r: r["retailer_sku"])
    evidence.sort(key=lambda r: (r["retailer_sku"], r["field"]))
    (out / "products.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in products), encoding="utf-8")
    (out / "field_evidence.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in evidence), encoding="utf-8")
    (out / "audit.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in audit), encoding="utf-8")

    attempted = len(audit)
    matched = len(products)
    summary = {
        "retailer": "CARREFOUR",
        "source": SOURCE,
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "extractor_version": VERSION,
        "built_at": now_iso(),
        "classification_performed": False,
        "endpoint": ENDPOINT,
        "counts": {
            "candidate_skus": len(all_skus),
            "explicit_skus": explicit_count,
            "attempted": attempted,
            "matched": matched,
            "http_403": sum(r.get("http_status") == 403 for r in audit),
            "http_429": sum(r.get("http_status") == 429 for r in audit),
            "gtin": sum(bool(r.get("gtin")) for r in products),
            "brand": sum(bool(r.get("brand")) for r in products),
            "price": sum(r.get("price_eur") is not None for r in products),
            "evidence_rows": len(evidence),
        },
        "coverage": {
            "gtin_pct_of_matched": round(100 * sum(bool(r.get("gtin")) for r in products) / matched, 2) if matched else 0.0,
            "brand_pct_of_matched": round(100 * sum(bool(r.get("brand")) for r in products) / matched, 2) if matched else 0.0,
            "price_pct_of_matched": round(100 * sum(r.get("price_eur") is not None for r in products) / matched, 2) if matched else 0.0,
        },
        "sample": products[:10],
        "provenance_note": "All populated fields come directly from Carrefour's public pdp-food-analytics endpoint. Candidate SKUs may originate in external discovery files, but external field values are never copied or attributed to Carrefour.",
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    return 0 if matched else 2


if __name__ == "__main__":
    raise SystemExit(main())
