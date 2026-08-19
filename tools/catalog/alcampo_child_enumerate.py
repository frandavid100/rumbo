from __future__ import annotations
import argparse,json,math
from pathlib import Path
from alcampo_direct_catalog_v8 import collect_root
from alcampo_direct_catalog_v6 import write_outputs

def main():
 p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--rid',required=True);p.add_argument('--expected',type=int,default=0);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 products,meta=collect_root(a.label,a.rid,0)
 summary=write_outputs(a.out,products,[meta])
 got=summary['counts']['food_products']
 # Expected count includes possible alcoholic items, so allow a small margin; API errors are never accepted silently.
 required=max(1,math.floor(a.expected*0.88)) if a.expected else 1
 check={'label':a.label,'rid':a.rid,'expected_product_count':a.expected,'required_minimum':required,'food_products':got,'api_errors':meta.get('errors',[]),'ok':not meta.get('errors') and got>=required}
 (a.out/'child_check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(check,ensure_ascii=False,indent=2))
 return 0 if check['ok'] else 2
if __name__=='__main__': raise SystemExit(main())
