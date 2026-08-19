from __future__ import annotations

import asyncio, json, re
from pathlib import Path
from playwright.async_api import async_playwright

TARGETS = [
    "https://www.compraonline.alcampo.es/categories/Alimentaci%C3%B3n/OCC10",
    "https://www.compraonline.alcampo.es/categories/frescos/OC17",
]

async def main() -> int:
    out = Path("alcampo-network-probe-v2"); out.mkdir(exist_ok=True)
    events=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        context=await browser.new_context(locale="es-ES", user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36")
        page=await context.new_page()

        async def on_request(req):
            try:
                if req.resource_type not in ("xhr","fetch"):
                    return
                events.append({
                    "kind":"request","resource_type":req.resource_type,"method":req.method,"url":req.url,
                    "post_data":req.post_data,
                    "headers":{k:v for k,v in req.headers.items() if k.lower() in ("content-type","accept","x-requested-with","authorization")}
                })
            except Exception as e:
                events.append({"kind":"request_error","error":repr(e)})

        async def on_response(resp):
            try:
                req=resp.request
                if req.resource_type not in ("xhr","fetch"):
                    return
                ct=resp.headers.get("content-type","")
                item={"kind":"response","resource_type":req.resource_type,"method":req.method,"url":resp.url,"status":resp.status,"content_type":ct}
                if "json" in ct.lower() or "/api/" in resp.url:
                    try:
                        txt=await resp.text(); item["body"]=txt[:100000]
                    except Exception as e:
                        item["body_error"]=repr(e)
                events.append(item)
            except Exception as e:
                events.append({"kind":"response_error","error":repr(e)})

        page.on("request", on_request)
        page.on("response", on_response)

        for target in TARGETS:
            events.append({"kind":"target","url":target})
            await page.goto(target, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            for _ in range(12):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(900)
                for selector in ["text=/ver más/i","text=/cargar más/i","text=/mostrar más/i"]:
                    try:
                        loc=page.locator(selector).first
                        if await loc.count() and await loc.is_visible():
                            await loc.click(timeout=1500); await page.wait_for_timeout(1200)
                    except Exception:
                        pass

        await browser.close()

    (out/"network.json").write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding="utf-8")
    api=[e for e in events if "/api/" in e.get("url","") or re.search(r"product|category|search|pageToken|nextPageToken", (e.get("body") or ""), re.I)]
    (out/"api.json").write_text(json.dumps(api,ensure_ascii=False,indent=2),encoding="utf-8")
    summary=[]
    for e in api:
        summary.append({k:e.get(k) for k in ("kind","method","url","status","post_data","content_type") if e.get(k) is not None})
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary[:80],ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(asyncio.run(main()))
