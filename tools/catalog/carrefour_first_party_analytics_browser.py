from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import async_playwright

import carrefour_first_party_analytics_inventory as direct

SOURCE = direct.SOURCE
VERSION = "carrefour-first-party-analytics-browser-1.0"


async def browser_fetch(page, sku: str):
    query = urlencode({"product_id": f"R-{sku}", "referer": ""})
    url = direct.ENDPOINT + "?" + query
    result = await page.evaluate(
        """async (url) => {
          try {
            const response = await fetch(url, {
              credentials: 'same-origin',
              cache: 'no-store',
              headers: {'Accept': 'application/json,text/plain,*/*'}
            });
            const text = await response.text();
            return {
              status: response.status,
              finalUrl: response.url,
              contentType: response.headers.get('content-type') || '',
              text
            };
          } catch (error) {
            return {status: 0, error: String(error), text: ''};
          }
        }""",
        url,
    )
    status = int(result.get("status") or 0) or None
    text = result.get("text") or ""
    if status != 200:
        return status, None, result.get("error") or f"HTTP_{status}", url, result.get("contentType")
    try:
        payload = json.loads(text)
    except Exception as exc:
        return status, None, f"INVALID_JSON:{type(exc).__name__}", url, result.get("contentType")
    if not isinstance(payload, dict):
        return status, None, "JSON_NOT_OBJECT", url, result.get("contentType")
    return status, payload, None, url, result.get("contentType")


async def run(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    all_skus = direct.candidate_skus(args.seed_jsonl, args.sku)
    explicit_count = len(direct.candidate_skus([], args.sku))
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

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="es-ES",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
            viewport={"width": 1365, "height": 900},
        )
        page = await context.new_page()
        warmups = []
        for warm_url in ("https://www.carrefour.es/robots.txt", "https://www.carrefour.es/supermercado/"):
            try:
                response = await page.goto(warm_url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
                warmups.append({"url": warm_url, "status": response.status if response else None})
            except Exception as exc:
                warmups.append({"url": warm_url, "error": f"{type(exc).__name__}:{exc}"})
            await page.wait_for_timeout(500)

        for index, sku in enumerate(selected, 1):
            observed_at = direct.now_iso()
            status, payload, error, source_url, content_type = await browser_fetch(page, sku)
            row = None
            ev = []
            if payload is not None and not error:
                row, ev = direct.parse_impression(sku, payload, source_url, observed_at)
                if row is None:
                    error = "NO_MATCHING_IMPRESSION"
            blocked = status in {403, 429}
            consecutive_blocks = consecutive_blocks + 1 if blocked else 0
            if row:
                row["analytics_browser_observed"] = True
                products.append(row)
                evidence.extend(ev)
            audit.append({
                "retailer_sku": sku,
                "source": SOURCE,
                "source_url": source_url,
                "observed_at": observed_at,
                "http_status": status,
                "content_type": content_type,
                "error": error,
                "matched": bool(row),
            })
            print(json.dumps({"index": index, "sku": sku, "status": status, "matched": bool(row), "error": error}, ensure_ascii=False))
            if args.stop_after_blocks > 0 and consecutive_blocks >= args.stop_after_blocks:
                break
            if index < len(selected) and args.delay > 0:
                await asyncio.sleep(args.delay)
        await context.close()
        await browser.close()

    products.sort(key=lambda r: r["retailer_sku"])
    evidence.sort(key=lambda r: (r["retailer_sku"], r["field"]))
    (out / "products.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in products), encoding="utf-8")
    (out / "field_evidence.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in evidence), encoding="utf-8")
    (out / "audit.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in audit), encoding="utf-8")

    matched = len(products)
    summary = {
        "retailer": "CARREFOUR",
        "source": SOURCE,
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "extractor_version": VERSION,
        "built_at": direct.now_iso(),
        "classification_performed": False,
        "endpoint": direct.ENDPOINT,
        "warmups": warmups,
        "counts": {
            "candidate_skus": len(all_skus),
            "explicit_skus": explicit_count,
            "attempted": len(audit),
            "matched": matched,
            "http_403": sum(r.get("http_status") == 403 for r in audit),
            "http_429": sum(r.get("http_status") == 429 for r in audit),
            "gtin": sum(bool(r.get("gtin")) for r in products),
            "brand": sum(bool(r.get("brand")) for r in products),
            "price": sum(r.get("price_eur") is not None for r in products),
            "evidence_rows": len(evidence),
        },
        "sample": products[:10],
        "provenance_note": (
            "All populated fields come directly from Carrefour's public pdp-food-analytics endpoint, fetched in a normal "
            "same-origin Chromium session. Candidate SKUs may originate in external discovery files, but external field "
            "values are never copied or attributed to Carrefour."
        ),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if matched else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-jsonl", action="append", default=[])
    ap.add_argument("--sku", action="append", default=[])
    ap.add_argument("--out", default="carrefour-first-party-analytics-browser")
    ap.add_argument("--max-products", type=int, default=20)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--rotate", action="store_true")
    ap.add_argument("--stop-after-blocks", type=int, default=3)
    args = ap.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
