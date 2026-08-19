from __future__ import annotations
import argparse,json
from pathlib import Path
from alcampo_direct_catalog_v8 import ApiSession,page_url

def main():
 p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--rid',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 s=ApiSession(); payload=s.json(page_url(a.rid,None),attempts=20)
 info=payload.get('additionalPageInfo') or {}; cats=[]
 for c in info.get('categories') or []:
  if isinstance(c,dict) and c.get('retailerCategoryId'):
   cats.append({'root_label':a.label,'root_retailer_category_id':a.rid,'name':c.get('name'),'categoryId':c.get('categoryId'),'retailerCategoryId':c.get('retailerCategoryId'),'productCount':c.get('productCount')})
 result={'root_label':a.label,'root_retailer_category_id':a.rid,'children':cats,'child_product_count_sum':sum(int(c.get('productCount') or 0) for c in cats)}
 (a.out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if cats else 2
if __name__=='__main__': raise SystemExit(main())
