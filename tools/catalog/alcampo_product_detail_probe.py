from __future__ import annotations
import json,re
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
BASE='https://www.compraonline.alcampo.es'
CORRECT=BASE+'/products/alcampo-ecol%C3%B3gico-tofu-procedente-de-agricultura-biol%C3%B3gica-2-x-200-g/522881'
URLS=[CORRECT,BASE+'/products/x/522881',BASE+'/products/product/522881',BASE+'/products/522881']
UAS={
'browser':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36',
'googlebot':'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
'bingbot':'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)',
'facebook':'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
}
def fetch(url,ua):
 req=Request(url,headers={'User-Agent':ua,'Accept-Language':'es-ES,es;q=0.9','Accept':'text/html,application/xhtml+xml'})
 try:
  with urlopen(req,timeout=45) as r: return r.status,r.geturl(),r.read().decode('utf-8','replace')
 except HTTPError as e: return e.code,e.geturl(),e.read().decode('utf-8','replace')
def main():
 out=Path('alcampo-product-detail-probe');out.mkdir(exist_ok=True); rows=[]
 for u in URLS:
  for uname,ua in UAS.items():
   try:s,final,b=fetch(u,ua)
   except Exception as e: rows.append({'url':u,'ua':uname,'error':f'{type(e).__name__}:{e}'});continue
   text=re.sub(r'<[^>]+>',' ',b); text=re.sub(r'\s+',' ',text)
   row={'url':u,'ua':uname,'status':s,'final_url':final,'length':len(b),'has_ingredients':bool(re.search(r'Ingredientes',text,re.I)),'has_nutrition':bool(re.search(r'Datos nutricionales|Informaci[oó]n nutricional|Valor energ[eé]tico',text,re.I)),'has_tofu':bool(re.search(r'Tofu',text,re.I)),'js_disabled':bool(re.search(r'JavaScript is disabled|javascript.*disabled',text,re.I)),'preview':text[:1500]}
   rows.append(row); print(json.dumps({k:row[k] for k in ('ua','status','final_url','length','has_ingredients','has_nutrition','js_disabled')},ensure_ascii=False),flush=True)
 (out/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 return 0 if any(r.get('has_nutrition') for r in rows) else 2
if __name__=='__main__': raise SystemExit(main())
