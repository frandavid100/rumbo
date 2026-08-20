from __future__ import annotations
import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright
from alcampo_detail_enricher import parse_fields

TARGET='https://www.compraonline.alcampo.es/products/x/522881'
INTEREST=('product','nutrition','ingredient','detail','pdp','webproduct','api/')
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36'

async def main():
    out=Path('alcampo-detail-network-probe'); out.mkdir(exist_ok=True)
    rows=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        ctx=await browser.new_context(locale='es-ES',user_agent=UA,viewport={'width':1280,'height':720})
        page=await ctx.new_page()
        async def on_req(req):
            if req.resource_type not in ('xhr','fetch'): return
            rows.append({'kind':'request','method':req.method,'url':req.url,'resource_type':req.resource_type,'post_data':req.post_data,'headers':{k:v for k,v in req.headers.items() if k.lower() in ('content-type','accept','x-requested-with')}})
        async def on_resp(resp):
            req=resp.request
            if req.resource_type not in ('xhr','fetch'): return
            row={'kind':'response','method':req.method,'url':resp.url,'status':resp.status,'content_type':resp.headers.get('content-type','')}
            try:
                text=await resp.text()
                row['body_preview']=text[:30000]
                row['body_length']=len(text)
            except Exception as exc: row['body_error']=f'{type(exc).__name__}:{exc}'
            rows.append(row)
        page.on('request',on_req); page.on('response',on_resp)
        main_resp=await page.goto(TARGET,wait_until='domcontentloaded',timeout=60000)
        await page.wait_for_timeout(5000)
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await page.wait_for_timeout(2500)
        body=await page.content()
        final_url=page.url
        title=await page.title()
        status=main_resp.status if main_resp else None
        (out/'page.html').write_text(body,encoding='utf-8')
        _,name,gtin,legal,ingredients,nt=parse_fields(body)
        rendered={
            'status':status,
            'final_url':final_url,
            'title':title,
            'html_bytes':len(body.encode('utf-8')),
            'name':name,
            'gtin':gtin,
            'legal_name':legal,
            'ingredients':ingredients,
            'nutrition':nt,
        }
        (out/'rendered_detail.json').write_text(json.dumps(rendered,ensure_ascii=False,indent=2),encoding='utf-8')
        await browser.close()
    (out/'network.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    interesting=[r for r in rows if any(t in (r.get('url','')+(r.get('body_preview') or '')).lower() for t in INTEREST)]
    (out/'interesting.json').write_text(json.dumps(interesting,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={
        'target':TARGET,
        'main_status':rendered['status'],
        'final_url':rendered['final_url'],
        'rendered_name':rendered['name'],
        'rendered_gtin':rendered['gtin'],
        'rendered_legal_name':rendered['legal_name'],
        'rendered_ingredients':bool(rendered['ingredients']),
        'rendered_nutrition_complete':all(rendered['nutrition'].get(k) is not None for k in ('calories','fat_g','carbohydrate_g','protein_g')),
        'rendered_nutrition_basis':rendered['nutrition'].get('basis'),
        'xhr_fetch_records':len(rows),
        'interesting':len(interesting),
        'requests':[{'method':r.get('method'),'url':r.get('url'),'post_data':r.get('post_data')} for r in interesting if r.get('kind')=='request'],
    }
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(asyncio.run(main()))
