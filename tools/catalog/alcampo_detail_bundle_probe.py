from __future__ import annotations
import json,re
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request,urlopen
BASE='https://www.compraonline.alcampo.es'
TARGET=BASE+'/products/alcampo-ecol%C3%B3gico-tofu-procedente-de-agricultura-biol%C3%B3gica-2-x-200-g/522881'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36'
TERMS=re.compile(r'ingredients?|nutrition|nutritional|legalName|regulated|webproduct|product[-_ ]?detail|product[-_ ]?page|/api/|gtin|ean|barcode|allergen',re.I)
SRC=re.compile(r'<script[^>]+src=["\']([^"\']+\.js(?:\?[^"\']*)?)["\']',re.I)
def fetch(u):
 req=Request(u,headers={'User-Agent':UA,'Accept':'*/*','Accept-Language':'es-ES,es;q=0.9'})
 with urlopen(req,timeout=45) as r:return r.read().decode('utf-8','replace')
def contexts(t,radius=900):
 out=[];seen=set()
 for m in TERMS.finditer(t):
  s=t[max(0,m.start()-radius):min(len(t),m.end()+radius)]
  if s not in seen:seen.add(s);out.append(s)
 return out
def main():
 out=Path('alcampo-detail-bundle-probe');out.mkdir(exist_ok=True);html=fetch(TARGET)
 srcs=[]
 for s in SRC.findall(html):
  u=urljoin(TARGET,s)
  if '/static/' in u and u not in srcs:srcs.append(u)
 results=[]
 # HTML itself can contain serialized API identifiers/schema clues.
 hc=contexts(html,1200)
 if hc:results.append({'url':TARGET,'kind':'html','length':len(html),'contexts':hc[:100]})
 for u in srcs:
  try:
   js=fetch(u);ctx=contexts(js)
   if ctx:results.append({'url':u,'kind':'js','length':len(js),'contexts':ctx[:100]});print('MATCH',u,len(js),len(ctx),flush=True)
  except Exception as e:results.append({'url':u,'error':f'{type(e).__name__}:{e}'})
 payload={'target':TARGET,'scripts_seen':len(srcs),'matched':sum('contexts' in r for r in results),'results':results}
 (out/'summary.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'scripts_seen':len(srcs),'matched':payload['matched']},indent=2));return 0 if payload['matched'] else 2
if __name__=='__main__':raise SystemExit(main())
