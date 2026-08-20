from __future__ import annotations

import argparse
import asyncio
import hashlib
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
BLOCK_RE = re.compile(
    r"sorry,? you have been blocked|attention required|cloudflare|access denied|forbidden|captcha|robot|incapsula|akamai",
    re.I,
)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def html_filename(url: str) -> str:
    m = re.search(r"/R-([^/]+)/p/?(?:\?.*)?$", url, re.I)
    key = m.group(1) if m else hashlib.sha256(url.encode()).hexdigest()[:20]
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", key) + ".html"


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
        row["blocked_text"] = bool((row.get("status") == 403) or BLOCK_RE.search(row["title"] + "\n" + text))
        row["ok"] = bool(row.get("status") and row["status"] < 400 and row["text_chars"] > 1000 and not row["blocked_text"])
        if row["ok"]:
            row["_html"] = html
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}:{exc}"
        row["ok"] = False
    finally:
        await page.close()
    return row


def persist_row(out: Path, html_dir: Path, row: dict) -> dict:
    raw = row.pop("_html", None)
    if raw:
        filename = html_filename(row.get("final_url") or row["url"])
        path = html_dir / filename
        path.write_text(raw, encoding="utf-8")
        row["saved_html"] = str(path.relative_to(out))
        row["page_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    print(json.dumps(row, ensure_ascii=False))
    return row


async def run(args):
    urls = args.url or DEFAULT_URLS
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    html_dir = out / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    stopped_after_block_streak = False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="es-ES",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
            viewport={"width": 1365, "height": 900},
        )

        # Default to a deliberately polite sequential probe. Parallelism remains
        # available for diagnostics, but is opt-in; it is not used to work around
        # retailer blocking.
        if args.concurrency <= 1:
            consecutive_blocks = 0
            for index, url in enumerate(urls):
                row = persist_row(out, html_dir, await inspect(context, url, args.timeout * 1000))
                rows.append(row)
                consecutive_blocks = consecutive_blocks + 1 if row.get("blocked_text") else 0
                if args.max_consecutive_blocks > 0 and consecutive_blocks >= args.max_consecutive_blocks:
                    stopped_after_block_streak = True
                    break
                if index + 1 < len(urls) and args.inter_request_delay_ms > 0:
                    await asyncio.sleep(args.inter_request_delay_ms / 1000)
        else:
            sem = asyncio.Semaphore(args.concurrency)

            async def one(url):
                async with sem:
                    return await inspect(context, url, args.timeout * 1000)

            for task in asyncio.as_completed([one(u) for u in urls]):
                rows.append(persist_row(out, html_dir, await task))

        await context.close()
        await browser.close()

    rows.sort(key=lambda r: r["url"])
    summary = {
        "source": "https://www.carrefour.es",
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "version": "carrefour-first-party-browser-probe-1.3",
        "built_at": now_iso(),
        "probe_policy": {
            "concurrency": args.concurrency,
            "inter_request_delay_ms": args.inter_request_delay_ms,
            "max_consecutive_blocks": args.max_consecutive_blocks,
            "no_block_bypass": True,
        },
        "counts": {
            "requested": len(urls),
            "attempted": len(rows),
            "http_success": sum(bool(r.get("status") and r["status"] < 400) for r in rows),
            "usable_pages": sum(bool(r.get("ok")) for r in rows),
            "saved_html_pages": sum(bool(r.get("saved_html")) for r in rows),
            "with_product_jsonld": sum(bool(r.get("product_jsonld")) for r in rows),
            "with_nutrition_marker": sum(bool(r.get("markers", {}).get("Información nutricional")) for r in rows),
            "blocked": sum(bool(r.get("blocked_text")) for r in rows),
            "errors": sum(bool(r.get("error")) for r in rows),
        },
        "stopped_after_block_streak": stopped_after_block_streak,
        "rows": rows,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="carrefour-first-party-browser-probe")
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--timeout", type=int, default=35)
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--inter-request-delay-ms", type=int, default=5000)
    ap.add_argument("--max-consecutive-blocks", type=int, default=2)
    args = ap.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
