from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://tienda.mercadona.es/api/v1_1"
USER_AGENT = "RumboCatalog/0.1 (first-party inventory audit; contact: frandavid100@users.noreply.github.com)"
SOURCE = "MERCADONA_FIRST_PARTY"
EVIDENCE_TYPE = "OBSERVED_API"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _clean_html(value: Any) -> str | None:
    text = _string(value)
    if not text:
        return None
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text or None


def _get_json(product_id: str, *, timeout: float) -> tuple[dict[str, Any], str]:
    url = f"{API_ROOT}/products/{product_id}?{urlencode({'lang': 'es'})}"
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        raw = response.read()
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "json" not in content_type and not raw.lstrip().startswith(b"{"):
            raise ValueError(f"Unexpected content type: {content_type or 'unknown'}")
        payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Product detail payload is not an object")
    if _string(payload.get("id")) not in (None, product_id):
        raise ValueError("Product detail payload does not match requested id")
    return payload, url


def _category_path(value: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []

    def walk(nodes: Any) -> None:
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if not isinstance(node, dict):
                continue
            cid = _string(node.get("id"))
            name = _string(node.get("name")) or _string(node.get("display_name"))
            if cid or name:
                row: dict[str, str] = {}
                if cid:
                    row["id"] = cid
                if name:
                    row["name"] = name
                level = _string(node.get("level"))
                if level:
                    row["level"] = level
                out.append(row)
            walk(node.get("categories"))

    walk(value)
    return out


def _photo_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        row: dict[str, Any] = {}
        for key in ("zoom", "regular", "thumbnail"):
            url = _string(item.get(key))
            if url:
                row[key] = url
        if item.get("perspective") is not None:
            row["perspective"] = item.get("perspective")
        if row:
            rows.append(row)
    return rows


def _supplier_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        name = _string(item.get("name")) if isinstance(item, dict) else _string(item)
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _field_evidence(row: dict[str, Any], *, source_url: str, observed_at: str) -> dict[str, dict[str, str]]:
    ignored = {"source", "evidence_type", "observed_at", "source_url", "field_evidence", "detail_observed"}
    evidence: dict[str, dict[str, str]] = {}
    for key, value in row.items():
        if key in ignored or value in (None, "", [], {}):
            continue
        evidence[key] = {
            "source": SOURCE,
            "evidence_type": EVIDENCE_TYPE,
            "observed_at": observed_at,
            "source_url": source_url,
        }
    return evidence


def normalize(payload: dict[str, Any], *, source_url: str, observed_at: str) -> dict[str, Any]:
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    nutrition = payload.get("nutrition_information") if isinstance(payload.get("nutrition_information"), dict) else {}
    price = payload.get("price_instructions") if isinstance(payload.get("price_instructions"), dict) else {}
    photos = _photo_rows(payload.get("photos"))
    suppliers = _supplier_names(details.get("suppliers"))
    category_path = _category_path(payload.get("categories"))

    row: dict[str, Any] = {
        "product_id": _string(payload.get("id")),
        "ean": _string(payload.get("ean")) or _string(payload.get("gtin")) or _string(payload.get("barcode")),
        "name": _string(payload.get("display_name")) or _string(payload.get("name")),
        "brand": _string(payload.get("brand")) or _string(details.get("brand")),
        "slug": _string(payload.get("slug")),
        "origin": _string(payload.get("origin")) or _string(details.get("origin")),
        "packaging": _string(payload.get("packaging")),
        "published": payload.get("published") if isinstance(payload.get("published"), bool) else None,
        "status": _string(payload.get("status")),
        "unavailable_from": _string(payload.get("unavailable_from")),
        "unavailable_weekdays": payload.get("unavailable_weekdays") if isinstance(payload.get("unavailable_weekdays"), list) else [],
        "is_bulk": payload.get("is_bulk") if isinstance(payload.get("is_bulk"), bool) else None,
        "is_variable_weight": payload.get("is_variable_weight") if isinstance(payload.get("is_variable_weight"), bool) else None,
        "is_new_arrival": payload.get("is_new_arrival") if isinstance(payload.get("is_new_arrival"), bool) else None,
        "share_url": _string(payload.get("share_url")),
        "thumbnail": _string(payload.get("thumbnail")),
        "photos": photos,
        "photo_count": len(photos),
        "category_path": category_path,
        "price": _number(price.get("unit_price")) or _number(payload.get("price")),
        "unit_price": _number(price.get("unit_price")),
        "unit_size": _number(price.get("unit_size")),
        "unit_name": _string(price.get("unit_name")),
        "bulk_price": _number(price.get("bulk_price")),
        "reference_price": _number(price.get("reference_price")),
        "reference_format": _string(price.get("reference_format")),
        "size_format": _string(price.get("size_format")),
        "total_units": price.get("total_units") if isinstance(price.get("total_units"), (int, float)) and not isinstance(price.get("total_units"), bool) else None,
        "drained_weight": _number(price.get("drained_weight")),
        "tax_percentage": _number(price.get("tax_percentage")),
        "legal_name": _clean_html(details.get("legal_name")),
        "description": _clean_html(details.get("description")),
        "suppliers": suppliers,
        "danger_mentions": _clean_html(details.get("danger_mentions")),
        "mandatory_mentions": _clean_html(details.get("mandatory_mentions")),
        "production_variant": _clean_html(details.get("production_variant")),
        "usage_instructions": _clean_html(details.get("usage_instructions")),
        "storage_instructions": _clean_html(details.get("storage_instructions")),
        "alcohol_by_volume": _number(details.get("alcohol_by_volume")),
        "is_prepared_by_mercadona": details.get("is_prepared_by_mercadona") if isinstance(details.get("is_prepared_by_mercadona"), bool) else None,
        "ingredients": _clean_html(nutrition.get("ingredients")),
        "allergens": _clean_html(nutrition.get("allergens")),
        "ingredients_raw": _string(nutrition.get("ingredients")),
        "allergens_raw": _string(nutrition.get("allergens")),
        "source_url": source_url,
        "source": SOURCE,
        "evidence_type": EVIDENCE_TYPE,
        "observed_at": observed_at,
        "detail_observed": True,
    }
    row["field_evidence"] = _field_evidence(row, source_url=source_url, observed_at=observed_at)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard-index", type=int, required=True)
    ap.add_argument("--shard-count", type=int, required=True)
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--delay", type=float, default=0.4)
    args = ap.parse_args()

    inventory_path = Path(args.inventory)
    rows = [json.loads(line) for line in inventory_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows.sort(key=lambda row: (len(str(row.get("product_id") or "")), str(row.get("product_id") or "")))
    selected = [row for i, row in enumerate(rows) if i % args.shard_count == args.shard_index]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    details_path = out / f"details-{args.shard_index:02d}.jsonl"
    errors_path = out / f"errors-{args.shard_index:02d}.jsonl"
    observed_at = _now()
    details: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for index, listing in enumerate(selected):
        pid = _string(listing.get("product_id"))
        if not pid:
            continue
        if index:
            time.sleep(args.delay)
        try:
            payload, url = _get_json(pid, timeout=args.timeout)
            details.append(normalize(payload, source_url=url, observed_at=observed_at))
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            errors.append({"product_id": pid, "error": f"{type(exc).__name__}:{exc}"})

    details_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in details), encoding="utf-8")
    errors_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in errors), encoding="utf-8")
    summary = {
        "source": SOURCE,
        "evidence_type": EVIDENCE_TYPE,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "inventory_products": len(rows),
        "requested": len(selected),
        "fetched": len(details),
        "errors": len(errors),
        "observed_at": observed_at,
    }
    (out / f"summary-{args.shard_index:02d}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if details else 2


if __name__ == "__main__":
    raise SystemExit(main())
