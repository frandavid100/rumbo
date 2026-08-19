from __future__ import annotations

import asyncio, json, re
from pathlib import Path
from playwright.async_api import async_playwright

TARGETS = [
    "https://www.compraonline.alcampo.es/categories/alimentaci%C3%B3n/conservas-de-pescado/at%C3%BAn/OCConservasAtun",
    "https://www.compraonline.alcampo.es/categories/alimentaci%C3%B3n/OCC10",
]

async def main():
    out=Path('alcampo-dom-probe'); out.mkdir(exist_ok=True)
    report=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        ctx=await browser.new_context(locale='es-ES',user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36')
        page=await ctx.new_page()
        for i,url in enumerate(TARGETS):
            await page.goto(url,wait_until='domcontentloaded',timeout=60000)
            await page.wait_for_timeout(3000)
            before=await page.content()
            for _ in range(12):
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(700)
            after=await page.content()
            hrefs=await page.eval_on_selector_all('a[href*="/products/"]','els=>els.map(a=>a.href)')
            cat_hrefs=await page.eval_on_selector_all('a[href*="/categories/"]','els=>els.map(a=>[a.innerText.trim(),a.href])')
            item={
                'url':url,
                'before_html_length':len(before),
                'after_html_length':len(after),
                'product_hrefs':list(dict.fromkeys(hrefs)),
                'product_href_count':len(set(hrefs)),
                'category_links':cat_hrefs,
                'productId_uuid_count':len(set(re.findall(r'(?i)productId[^0-9a-f]{0,20}([0-9a-f]{8}-[0-9a-f-]{27,36})',after))),
                'retailerProductId_values':sorted(set(re.findall(r'(?i)retailerProductId[^0-9]{0,20}(\d+)',after)))[:500],
                'retailerProductId_count':len(set(re.findall(r'(?i)retailerProductId[^0-9]{0,20}(\d+)',after))),
            }
            report.append(item)
            (out/f'page-{i}.html').write_text(after,encoding='utf-8')
        await browser.close()
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:v for k,v in x.items() if k not in ('product_hrefs','category_links','retailerProductId_values')} for x in report],ensure_ascii=False,indent=2))

if __name__=='__main__': asyncio.run(main())
