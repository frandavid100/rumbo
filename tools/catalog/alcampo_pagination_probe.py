from __future__ import annotations
import json, urllib.parse
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
BASE='https://www.compraonline.alcampo.es'; EP=BASE+'/api/webproductpagews/v6/product-pages'; RID='OC100402'; UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36'
def call(params):
 u=EP+'?'+urllib.parse.urlencode(params,doseq=True); req=Request(u,headers={'User-Agent':UA,'Accept':'application/json, text/plain, */*','Accept-Language':'es-ES,es;q=0.9','Referer':BASE+'/categories/alimentaci%C3%B3n/conservas-de-pescado/OC100402?sortBy=favorite'})
 try:
  with urlopen(req,timeout=60) as r: return u,r.status,r.read().decode('utf-8','replace')
 except HTTPError as e: return u,e.code,e.read().decode('utf-8','replace')
def count(o):
 return sum(len(g.get('decoratedProducts') or [])+len(g.get('otherProductIds') or []) for g in o.get('productGroups') or [])
def main():
 out=Path('alcampo-pagination-probe');out.mkdir(exist_ok=True)
 first=[('maxProductsToDecorate','300'),('maxPageSize','300'),('includeAdditionalPageInfo','true'),('retailerCategoryId',RID)]
 u,s,b=call(first); obj=json.loads(b); token=(obj.get('metadata') or {}).get('nextPageToken'); rows=[{'name':'first','url':u,'status':s,'count':count(obj),'token':token}]
 variants={
 'client_exact_no_tag':[('maxProductsToDecorate','300'),('maxPageSize','300'),('includeAdditionalPageInfo','false'),('pageToken',token),('retailerCategoryId',RID)],
 'omit_additional':[('maxProductsToDecorate','300'),('maxPageSize','300'),('pageToken',token),('retailerCategoryId',RID)],
 'tag_repeat':[('maxProductsToDecorate','300'),('maxPageSize','300'),('includeAdditionalPageInfo','false'),('pageToken',token),('retailerCategoryId',RID),('tag','web'),('tag','category-item')],
 'tag_indices':[('maxProductsToDecorate','300'),('maxPageSize','300'),('includeAdditionalPageInfo','false'),('pageToken',token),('retailerCategoryId',RID),('tag[0]','web'),('tag[1]','category-item')],
 'tag_comma':[('maxProductsToDecorate','300'),('maxPageSize','300'),('includeAdditionalPageInfo','false'),('pageToken',token),('retailerCategoryId',RID),('tag','web,category-item')],
 'token_only':[('maxProductsToDecorate','300'),('maxPageSize','300'),('includeAdditionalPageInfo','false'),('pageToken',token)],
 }
 for name,p in variants.items():
  u,s,b=call(p); row={'name':name,'url':u,'status':s,'body_preview':b[:1500]}
  try:
   o=json.loads(b); row.update({'count':count(o),'next':(o.get('metadata') or {}).get('nextPageToken'),'top_keys':list(o)})
  except Exception: pass
  rows.append(row); print(name,s,row.get('count'),row.get('body_preview','')[:200],flush=True)
 (out/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 return 0 if any(r.get('status')==200 and r.get('name')!='first' for r in rows) else 2
if __name__=='__main__': raise SystemExit(main())
