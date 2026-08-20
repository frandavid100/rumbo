from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from playwright.async_api import async_playwright

import carrefour_first_party_sitemap as sm

VERSION = "carrefour-first-party-sitemap-browser-1.0"


async def fetch_text(page, url: str):
    result = await page.evaluate(
        """async (url) => {
          try {
            const r = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
            return {status: r.status, finalUrl: r.url, text: await r.text(), contentType: r.headers.get('content-type') || ''};
          } catch (e) {
            return {status: 0, error: String(e), text: ''};
          }
        }""",
        url,
    )
    return result


async def crawl(page, index_url: str, max_sitemaps: int, delay: float):
    queue = [index_url]
    seen = set()
    products = {}
    diagnostics = []
    while queue and len(seen) < max_sitemaps:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        result = await fetch_text(page, url)
        status = int(result.get("status") or 0)
        text = result.get("text") or ""
        diag = {
            "url": url,
            "status": status,
            "content_type": result.get("contentType"),
            "bytes": len(text.encode()),
        }
        if status != 200:
            diag["error"] = result.get("error") or f"HTTP_{status}"
            diagnostics.append(diag)
            if delay > 0 and queue:
                await asyncio.sleep(delay)
            continue
        try:
            root = ET.fromstring(text.encode())
            kind = sm.local_name(root.tag)
            diag["kind"] = kind
            if kind == "sitemapindex":
                children = []
                for node in root:
                    loc = sm.child_text(node, "loc")
                    if loc and sm.allowed_sitemap(loc):
                        children.append(loc)
                diag["children"] = len(children)
                queue.extend(x for x in children if x not in seen)
            elif kind == "urlset":
                found = 0
                for node in root:
                    loc = sm.child_text(node, "loc")
                    if not loc:
                        continue
                    loc = loc.split("?", 1)[0].rstrip("/")
                    match = sm.PRODUCT_RE.match(loc)
                    if not match:
                        continue
                    sku = match.group(1)
                    products[sku] = {
                        "retailer": "CARREFOUR",
                        "retailer_sku": sku,
                        "canonical_url": loc,
                        "url": loc,
                        "sitemap_lastmod": sm.child_text(node, "lastmod"),
                        "source": sm.SOURCE,
                        "evidence_type": "OBSERVED_LISTING",
                        "source_url": url,
                    }
                    found += 1
                diag["products"] = found
            else:
                diag["warning"] = f"unexpected_root:{kind}"
        except Exception as exc:
            diag["error"] = f"{type(exc).__name__}:{exc}"
        diagnostics.append(diag)
        if delay > 0 and queue:
            await asyncio.sleep(delay)
    return products, diagnostics, sorted(seen), list(queue)


async def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    built_at = sm.now_iso()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="es-ES", viewport={"width": 1365, "height": 900})
        page = await context.new_page()
        warm = await page.goto("https://www.carrefour.es/robots.txt", wait_until="domcontentloaded", timeout=args.timeout * 1000)
        warm_status = warm.status if warm else None
        await page.wait_for_timeout(500)
        products, diagnostics, seen, remaining = await crawl(page, args.index_url, args.max_sitemaps, args.delay)
        await context.close()
        await browser.close()

    rows = []
    evidence = []
    for sku in sorted(products):
        row = dict(products[sku])
        row["observed_at"] = built_at
        row["record_sha256"] = hashlib.sha256((row["canonical_url"] + "|" + (row.get("sitemap_lastmod") or "")).encode()).hexdigest()
        rows.append(row)
        for field in ("retailer_sku", "canonical_url", "sitemap_lastmod"):
            if row.get(field):
                evidence.append({
                    "retailer_sku": sku,
                    "field": field,
                    "value": row[field],
                    "source": sm.SOURCE,
                    "evidence_type": "OBSERVED_LISTING",
                    "source_url": row["source_url"],
                    "observed_at": built_at,
                })

    with (out / "products.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out / "field_evidence.jsonl").open("w", encoding="utf-8") as f:
        for row in evidence:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out / "diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")

    metadata = {
        "retailer": "CARREFOUR",
        "source": args.index_url,
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "extractor_version": VERSION,
        "built_at": built_at,
        "classification_performed": "false",
    }
    sm.write_sqlite(out / "carrefour_first_party_sitemap.sqlite", rows, diagnostics, metadata)
    errors = [d for d in diagnostics if d.get("error")]
    summary = {
        **metadata,
        "warmup_robots_status": warm_status,
        "counts": {
            "sitemaps_visited": len(seen),
            "sitemap_fetch_errors": len(errors),
            "product_urls": len(rows),
            "evidence_rows": len(evidence),
            "remaining_sitemaps": len(remaining),
        },
        "errors": errors[:30],
        "sample": rows[:20],
        "provenance_note": "Product identities and URLs come only from Carrefour's official sitemap-food index, fetched by a normal same-origin Chromium session after loading carrefour.es/robots.txt. No third-party product fields are copied.",
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if rows and not remaining else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index-url", default=sm.INDEX_URL)
    ap.add_argument("--out", default="carrefour-first-party-sitemap-browser")
    ap.add_argument("--max-sitemaps", type=int, default=5000)
    ap.add_argument("--delay", type=float, default=0.2)
    ap.add_argument("--timeout", type=int, default=45)
    args = ap.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
