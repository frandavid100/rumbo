from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://tienda.mercadona.es/api"
USER_AGENT = "RumboCatalog/0.1 (first-party inventory audit; contact: frandavid100@users.noreply.github.com)"
SOURCE = "MERCADONA_FIRST_PARTY"
EVIDENCE_TYPE = "OBSERVED_API"


@dataclass(frozen=True)
class Observation:
    product_id: str
    ean: str | None
    name: str | None
    brand: str | None
    slug: str | None
    origin: str | None
    packaging: str | None
    price: float | None
    unit_price: float | None
    unit_size: float | None
    unit_name: str | None
    bulk_price: float | None
    category_id: str | None
    category_name: str | None
    image_url: str | None
    photo_count: int
    source_url: str
    source: str
    evidence_type: str
    observed_at: str
    detail_observed: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _url_from_photo(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith("https://"):
        return value
    if isinstance(value, dict):
        for key in ("zoom", "regular", "large", "url", "src", "thumbnail"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.startswith("https://"):
                return candidate
    return None


def _get_json(path: str, *, timeout: float, lang: str | None = None) -> tuple[Any, str]:
    path = path if path.startswith("/") else f"/{path}"
    params = {"lang": lang} if lang else {}
    url = f"{API_ROOT}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        raw = response.read()
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "json" not in content_type and not raw.lstrip().startswith((b"{", b"[")):
            raise ValueError(f"Unexpected content type from {url}: {content_type or 'unknown'}")
        return json.loads(raw.decode("utf-8")), url


def _root_category_ids(payload: Any) -> list[tuple[str, str | None]]:
    values = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        for key in ("results", "categories", "data"):
            if isinstance(payload.get(key), list):
                values = payload[key]
                break
    result: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        category_id = _string(item.get("id"))
        if not category_id or not category_id.isdigit() or category_id in seen:
            continue
        seen.add(category_id)
        result.append((category_id, _string(item.get("name")) or _string(item.get("display_name"))))
    return result


def _product_dicts(value: Any, *, category_id: str | None = None,
                   category_name: str | None = None) -> list[tuple[dict, str | None, str | None]]:
    out: list[tuple[dict, str | None, str | None]] = []
    if isinstance(value, dict):
        current_id = _string(value.get("id")) if any(k in value for k in ("products", "categories")) else category_id
        current_name = (_string(value.get("name")) or _string(value.get("display_name"))) if any(k in value for k in ("products", "categories")) else category_name
        products = value.get("products")
        if isinstance(products, list):
            for product in products:
                if isinstance(product, dict) and _string(product.get("id")):
                    out.append((product, current_id or category_id, current_name or category_name))
        for key, child in value.items():
            if key == "products":
                continue
            if isinstance(child, (dict, list)):
                out.extend(_product_dicts(child, category_id=current_id or category_id,
                                          category_name=current_name or category_name))
    elif isinstance(value, list):
        for child in value:
            out.extend(_product_dicts(child, category_id=category_id, category_name=category_name))
    return out


def _normalize(payload: dict, *, category_id: str | None, category_name: str | None,
               source_url: str, observed_at: str, detail_observed: bool) -> Observation:
    product_id = _string(payload.get("id")) or ""
    price_info = payload.get("price_instructions") if isinstance(payload.get("price_instructions"), dict) else {}
    photos = payload.get("photos") if isinstance(payload.get("photos"), list) else []
    image_url = next((_url_from_photo(x) for x in photos if _url_from_photo(x)), None)
    packaging = (_string(payload.get("packaging")) or _string(payload.get("format"))
                 or _string(payload.get("packaging_name")))
    return Observation(
        product_id=product_id,
        ean=_string(payload.get("ean")) or _string(payload.get("gtin")) or _string(payload.get("barcode")),
        name=_string(payload.get("display_name")) or _string(payload.get("name")),
        brand=_string(payload.get("brand")),
        slug=_string(payload.get("slug")),
        origin=_string(payload.get("origin")),
        packaging=packaging,
        price=_number(price_info.get("unit_price")) or _number(payload.get("price")),
        unit_price=_number(price_info.get("unit_price")),
        unit_size=_number(price_info.get("unit_size")),
        unit_name=_string(price_info.get("unit_name")),
        bulk_price=_number(price_info.get("bulk_price")),
        category_id=category_id,
        category_name=category_name,
        image_url=image_url,
        photo_count=len(photos),
        source_url=source_url,
        source=SOURCE,
        evidence_type=EVIDENCE_TYPE,
        observed_at=observed_at,
        detail_observed=detail_observed,
    )


def _merge_listing(current: tuple[dict, str | None, str | None] | None,
                   incoming: tuple[dict, str | None, str | None]) -> tuple[dict, str | None, str | None]:
    if current is None:
        return incoming
    a, aid, aname = current
    b, bid, bname = incoming
    merged = dict(a)
    for key, value in b.items():
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = value
    return merged, aid or bid, aname or bname


def coverage(rows: list[Observation], field: str) -> dict[str, float | int]:
    total = len(rows)
    present = sum(1 for row in rows if getattr(row, field) not in (None, "", 0, []))
    return {"present": present, "pct": round(100.0 * present / total, 2) if total else 0.0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="mercadona-first-party-probe")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--delay", type=float, default=0.8)
    parser.add_argument("--detail-limit", type=int, default=24)
    args = parser.parse_args()

    out = Path(args.out)
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    observed_at = _now()
    errors: list[dict[str, str]] = []

    try:
        root, root_url = _get_json("/categories/", timeout=args.timeout, lang="es")
    except Exception as exc:
        report = {"source": SOURCE, "status": "BLOCKED", "stage": "categories_root",
                  "error": f"{type(exc).__name__}:{exc}", "observed_at": observed_at}
        (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    (raw_dir / "categories.json").write_text(json.dumps(root, ensure_ascii=False, indent=2), encoding="utf-8")
    roots = _root_category_ids(root)
    listing_by_id: dict[str, tuple[dict, str | None, str | None]] = {}
    category_ok = 0
    for index, (category_id, category_name) in enumerate(roots):
        if index:
            time.sleep(args.delay)
        try:
            payload, url = _get_json(f"/categories/{category_id}/", timeout=args.timeout, lang="es")
            (raw_dir / f"category-{category_id}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            category_ok += 1
            for product, cid, cname in _product_dicts(payload, category_id=category_id, category_name=category_name):
                pid = _string(product.get("id"))
                if pid and pid.isdigit():
                    listing_by_id[pid] = _merge_listing(listing_by_id.get(pid), (product, cid, cname))
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            errors.append({"stage": "category", "id": category_id, "name": category_name or "",
                           "error": f"{type(exc).__name__}:{exc}"})

    listing_rows = [
        _normalize(product, category_id=cid, category_name=cname,
                   source_url=f"{API_ROOT}/categories/{cid}/" if cid else root_url,
                   observed_at=observed_at, detail_observed=False)
        for product, cid, cname in listing_by_id.values()
    ]
    listing_rows.sort(key=lambda x: (len(x.product_id), x.product_id))

    detail_by_id: dict[str, Observation] = {}
    for index, listing in enumerate(listing_rows[: max(0, args.detail_limit)]):
        if index or roots:
            time.sleep(args.delay)
        try:
            payload, url = _get_json(f"/products/{listing.product_id}/", timeout=args.timeout, lang="es")
            if not isinstance(payload, dict) or _string(payload.get("id")) not in (None, listing.product_id):
                raise ValueError("Product detail payload does not match requested id")
            (raw_dir / f"product-{listing.product_id}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            detail_by_id[listing.product_id] = _normalize(
                payload, category_id=listing.category_id, category_name=listing.category_name,
                source_url=url, observed_at=observed_at, detail_observed=True)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            errors.append({"stage": "product", "id": listing.product_id,
                           "name": listing.name or "", "error": f"{type(exc).__name__}:{exc}"})

    combined = [detail_by_id.get(row.product_id, row) for row in listing_rows]
    with (out / "products.jsonl").open("w", encoding="utf-8") as fh:
        for row in combined:
            obj = asdict(row)
            obj["field_evidence"] = {
                key: {"source": SOURCE, "evidence_type": EVIDENCE_TYPE,
                      "source_url": row.source_url, "observed_at": observed_at}
                for key, value in obj.items()
                if key not in {"source", "evidence_type", "observed_at", "detail_observed", "field_evidence"}
                and value not in (None, "", 0, [])
            }
            fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")

    tracked = ["ean", "name", "brand", "origin", "packaging", "price", "unit_price",
               "unit_size", "unit_name", "bulk_price", "category_id", "category_name",
               "image_url", "photo_count"]
    report = {
        "source": SOURCE,
        "evidence_type": EVIDENCE_TYPE,
        "status": "OK" if listing_rows else "EMPTY",
        "observed_at": observed_at,
        "root_categories_discovered": len(roots),
        "root_categories_fetched": category_ok,
        "products_discovered": len(listing_rows),
        "details_requested": min(args.detail_limit, len(listing_rows)),
        "details_fetched": len(detail_by_id),
        "coverage": {field: coverage(combined, field) for field in tracked},
        "errors": errors,
        "error_types": dict(Counter(x["error"].split(":", 1)[0] for x in errors)),
    }
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if listing_rows else 3


if __name__ == "__main__":
    raise SystemExit(main())
