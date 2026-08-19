from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

TARGETS = [
    "https://www.compraonline.alcampo.es/categories/alimentaci%C3%B3n/OCC10",
    "https://www.compraonline.alcampo.es/categories/veganos/OCC83",
]

async def main() -> int:
    out = Path("alcampo-network-probe")
    out.mkdir(exist_ok=True)
    seen = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(locale="es-ES", user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36")
        page = await context.new_page()

        def capture(kind):
            async def handler(obj):
                try:
                    url = obj.url
                    if any(x in url.lower() for x in ("product", "category", "search", "graphql", "api", "token", "listing", "browse")):
                        item = {"kind": kind, "url": url}
                        if kind == "response":
                            item["status"] = obj.status
                            item["content_type"] = obj.headers.get("content-type")
                            try:
                                if item["content_type"] and "json" in item["content_type"].lower():
                                    text = await obj.text()
                                    item["body_preview"] = text[:4000]
                            except Exception:
                                pass
                        seen.append(item)
                except Exception:
                    pass
            return handler

        page.on("request", capture("request"))
        page.on("response", capture("response"))

        for target in TARGETS:
            seen.append({"kind": "target", "url": target})
            await page.goto(target, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            for _ in range(8):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1200)
            # click any load more / next controls if present
            for selector in ["text=/ver más/i", "text=/cargar más/i", "text=/mostrar más/i", "button[aria-label*=siguiente i]", "a[aria-label*=siguiente i]"]:
                try:
                    loc = page.locator(selector).first
                    if await loc.count() and await loc.is_visible():
                        await loc.click(timeout=3000)
                        await page.wait_for_timeout(2000)
                except Exception:
                    pass

        await browser.close()

    # Deduplicate exact entries preserving order.
    dedup=[]; keys=set()
    for item in seen:
        key=(item.get("kind"), item.get("url"), item.get("status"), item.get("body_preview"))
        if key not in keys:
            keys.add(key); dedup.append(item)
    (out/"network.json").write_text(json.dumps(dedup, ensure_ascii=False, indent=2), encoding="utf-8")

    candidates=[]
    for item in dedup:
        url=item.get("url","")
        body=item.get("body_preview","") or ""
        if re.search(r"nextPageToken|pageToken|product|category|graphql|search|browse", url+body, re.I):
            candidates.append(item)
    (out/"candidates.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(candidates[:30], ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
