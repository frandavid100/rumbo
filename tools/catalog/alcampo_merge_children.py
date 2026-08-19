from __future__ import annotations
import argparse,glob,json,math,sys
from pathlib import Path
from alcampo_direct_catalog_v6 import Product,merge,write_outputs

def main():
 p=argparse.ArgumentParser();p.add_argument('--downloaded',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--min-products',type=int,default=5000);a=p.parse_args()
 products={}; checks=[]; summaries=[]
 for cp in glob.glob(str(a.downloaded/'**/child_check.json'),recursive=True):
  try: checks.append(json.load(open(cp,encoding='utf-8')))
  except Exception: pass
 for sp in glob.glob(str(a.downloaded/'**/summary.json'),recursive=True):
  try: summaries.append(json.load(open(sp,encoding='utf-8')))
  except Exception: pass
 for pp in glob.glob(str(a.downloaded/'**/products.jsonl'),recursive=True):
  for line in open(pp,encoding='utf-8'):
   if not line.strip(): continue
   row=json.loads(line); obj=Product(**row)
   products[obj.product_id]=merge(products[obj.product_id],obj) if obj.product_id in products else obj
 merged=write_outputs(a.out,list(products.values()),checks)
 failed=[c for c in checks if not c.get('ok')]
 expected_total=sum(int(c.get('expected_product_count') or 0) for c in checks)
 report={'child_categories_seen':len(checks),'child_categories_failed':len(failed),'failed':failed,'sum_child_expected_counts':expected_total,'unique_products_after_dedup':merged['counts']['food_products'],'minimum_products':a.min_products,'complete_enumeration':len(failed)==0 and merged['counts']['food_products']>=a.min_products}
 (a.out/'enumeration_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['complete_enumeration'] else 2
if __name__=='__main__': raise SystemExit(main())
