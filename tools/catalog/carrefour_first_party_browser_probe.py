from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

DEFAULT_URLS = [
    "https://www.carrefour.es/supermercado/limonada-carrefour-botella-1-l/R-530362942/p",
    "https://www.carrefour.es/supermercado/bocaditos-carrefour-370-g/R-682401711/p",
    "https://www.carrefour.es/supermercado/leche-condensada-carrefour-397-g/R-521003205/p",
    "https://www.carrefour.es/supermercado/pizza-de-jamon-y-queso-carrefour-580-g/R-prod600097/p",
    "https://www.carrefour.es/supermercado/gofre-azucarado-carrefour-classic-pack-de-6-unidades-de-55-g/R-544101780/p",
    "https://www.carrefour.es/supermercado/mayonesa-carrefour-envase-500-ml-475g/R-VC4AECOMM-013524/p",
    "https://www.carrefour.es/supermercado/palitos-de-mar-carrefour-450-g/R-521034877/p",
    "https://www.carrefour.es/supermercado/pappardelle-al-ragu-findus-300-g/R-VC4AECOMM-701721/p",
]
MARKERS = ["Información nutricional", "Ingredientes", "Denominación legal", "Alérgenos", "Contenido neto"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def inspect(context, url: str, timeout_ms: int):
    page = await context.new_page()
    row = {"url": url, "observed_at": now_iso()}
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        row["status"] = response.status if response else None
        await page.wait_for_timeout(1800)
        row["final_url"] = page.url
        row["title"] = await page.title()
        html = await page.content()
        text = await page.locator("body").inner_text(timeout=5000)
        row["html_bytes"] = len(html.encode("utf-8"))
        row["text_chars"] = len(text)
        row["markers"] = {m: (m.lower() in text.lower()) for m in MARKERS}
        h1 = page.locator("h1").first
        row["h1"] = (await h1.inner_text()).strip() if await h1.count() else None
        row["product_jsonld"] = False
        for script in await page.locator('script[type="application/ld+json"]').all_text_contents():
            if '"Product"' in script or '"@type":"Product"' in script or '"@type": "Product"' in script:
                row["product_jsonld"] = True
                break
        row["blocked_text"] = bool(re.search(r"access denied|forbidden|captcha|robot|incapsula|akamai", text, re.I))
        row["ok"] = bool(row.get("status") and row["status"] < 400 and row["text_chars"] > 1000)
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}:{exc}"
        row["ok"] = False
    finally:
        await page.close()
    return row


async def run(args):
    urls = args.url or DEFAULT_URLS
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="es-ES",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
            viewport={"width": 1365, "height": 900},
        )
        rows = []
        sem = asyncio.Semaphore(max(1, args.concurrency))
        async def one(url):
            async with sem:
                return await inspect(context, url, args.timeout * 1000)
        for task in asyncio.as_completed([one(u) for u in urls]):
            row = await task; rows.append(row)
            print(json.dumps(row, ensure_ascii=False))
        await context.close(); await browser.close()
    rows.sort(key=lambda r: r["url"])
    summary = {
        "source": "https://www.carrefour.es",
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "version": "carrefour-first-party-browser-probe-1.0",
        "built_at": now_iso(),
        "counts": {
            "requested": len(rows),
            "http_success": sum(bool(r.get("status") and r["status"] < 400) for r in rows),
            "usable_pages": sum(bool(r.get("ok")) for r in rows),
            "with_product_jsonld": sum(bool(r.get("product_jsonld")) for r in rows),
            "with_nutrition_marker": sum(bool(r.get("markers", {}).get("Información nutricional")) for r in rows),
            "blocked": sum(bool(r.get("blocked_text")) for r in rows),
            "errors": sum(bool(r.get("error")) for r in rows),
        },
        "rows": rows,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="carrefour-first-party-browser-probe")
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--timeout", type=int, default=35)
    ap.add_argument("--concurrency", type=int, default=2)
    args = ap.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
