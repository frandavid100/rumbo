from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

TARGETS = [
    "https://www.compraonline.alcampo.es/categories/Alimentaci%C3%B3n/OCC10",
    "https://www.compraonline.alcampo.es/categories/frescos/OC17",
    "https://www.compraonline.alcampo.es/products/alcampo-ecol%C3%B3gico-tofu-procedente-de-agricultura-biol%C3%B3gica-2-x-200-g/522881",
]

INTERESTING = re.compile(r"/api/|webproductpagews|product|catalog|category|search|browse|listing|page(token)?", re.I)


def selected_headers(headers: dict[str, str]) -> dict[str, str]:
    keep = {"content-type", "accept", "x-requested-with", "x-correlation-id", "x-api-key", "origin", "referer"}
    return {k: v for k, v in headers.items() if k.lower() in keep}


async def main() -> int:
    out = Path("alcampo-network-probe-v2")
    out.mkdir(exist_ok=True)
    events: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="es-ES",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36",
        )
        page = await context.new_page()

        async def on_request(req):
            try:
                if req.resource_type not in ("xhr", "fetch") or not INTERESTING.search(req.url):
                    return
                events.append({
                    "kind": "request", "resource_type": req.resource_type, "method": req.method,
                    "url": req.url, "post_data": req.post_data, "headers": selected_headers(req.headers),
                })
            except Exception as exc:
                events.append({"kind": "request_error", "error": repr(exc)})

        async def on_response(resp):
            try:
                req = resp.request
                if req.resource_type not in ("xhr", "fetch") or not INTERESTING.search(resp.url):
                    return
                ct = resp.headers.get("content-type", "")
                item = {
                    "kind": "response", "resource_type": req.resource_type, "method": req.method,
                    "url": resp.url, "status": resp.status, "content_type": ct,
                    "request_post_data": req.post_data, "request_headers": selected_headers(req.headers),
                }
                if "json" in ct.lower() or "/api/" in resp.url:
                    try:
                        text = await resp.text(); item["body"] = text[:1_000_000]; item["body_length"] = len(text)
                    except Exception as exc:
                        item["body_error"] = repr(exc)
                events.append(item)
            except Exception as exc:
                events.append({"kind": "response_error", "error": repr(exc)})

        page.on("request", on_request)
        page.on("response", on_response)

        for target in TARGETS:
            events.append({"kind": "target", "url": target})
            try:
                await page.goto(target, wait_until="domcontentloaded", timeout=60_000)
                await page.wait_for_timeout(3500)
                if "/categories/" in target:
                    for _ in range(18):
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await page.wait_for_timeout(800)
                        for selector in ["text=/ver más/i", "text=/cargar más/i", "text=/mostrar más/i", "button[aria-label*=siguiente i]", "a[aria-label*=siguiente i]"]:
                            try:
                                loc = page.locator(selector).first
                                if await loc.count() and await loc.is_visible():
                                    await loc.click(timeout=1200); await page.wait_for_timeout(1200)
                            except Exception:
                                pass
            except Exception as exc:
                events.append({"kind": "target_error", "url": target, "error": repr(exc)})

        # Force a genuine product-search interaction to reveal the product-search API recipe.
        try:
            await page.goto("https://www.compraonline.alcampo.es/", wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(2500)
            candidates = [
                'input[placeholder*="Buscar" i]', 'input[aria-label*="Buscar" i]', 'input[type="search"]'
            ]
            search = None
            for sel in candidates:
                loc = page.locator(sel).first
                if await loc.count() and await loc.is_visible():
                    search = loc; break
            if search is not None:
                events.append({"kind": "search_probe", "term": "atun"})
                await search.fill("atun")
                await page.wait_for_timeout(1200)
                await search.press("Enter")
                await page.wait_for_timeout(5000)
                for _ in range(6):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(900)
        except Exception as exc:
            events.append({"kind": "search_probe_error", "error": repr(exc)})

        await browser.close()

    (out / "network.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    api = [e for e in events if INTERESTING.search(e.get("url", ""))]
    (out / "api.json").write_text(json.dumps(api, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = []
    for e in api:
        row = {k: e.get(k) for k in ("kind", "method", "url", "status", "post_data", "request_post_data", "content_type", "body_length") if e.get(k) is not None}
        body = e.get("body")
        if body: row["body_preview"] = body[:12_000]
        headers = e.get("headers") or e.get("request_headers")
        if headers: row["headers"] = headers
        summary.append(row)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    recipes = []
    seen = set()
    for e in api:
        if e.get("kind") not in ("request", "response"): continue
        method, url = e.get("method"), e.get("url")
        post = e.get("post_data") if e.get("kind") == "request" else e.get("request_post_data")
        key = (method, url, post)
        if key in seen: continue
        seen.add(key); recipes.append({"method": method, "url": url, "post_data": post})
    (out / "recipes.json").write_text(json.dumps(recipes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(recipes[:160], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
