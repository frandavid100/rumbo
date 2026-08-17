import json
from collections import Counter
from pathlib import Path
from nutrition_resolver import ProductIdentity, NutritionCandidate, RESOLVER_VERSION, resolve

FIX=Path(__file__).parent/'fixtures'/'nutrition_resolver_probe.json'

def ident(d): return ProductIdentity(d['name'],d.get('brand'),d.get('gtin'),d.get('format'),d.get('ingredients'))
def cand(d): return NutritionCandidate(ident(d),d['nutrition'],d['source'],d['source_url'],d.get('source_record_id'),d.get('observed_at'),d.get('upstream_license'),d.get('redistribution_allowed',False),d.get('source_family'),d.get('claim'))

rows=json.loads(FIX.read_text())
results=[]
for row in rows:
    result=resolve(ident(row['target']),[cand(x) for x in row['candidates']],require_publishable=True)
    results.append((row,result))
    if result.status!=row['expected_status']:
        raise SystemExit(f"Unexpected resolver status for {row['target']['name']}: {result.status} != {row['expected_status']}")
counts=Counter(r.status for _,r in results)
report={
    'resolver_version':RESOLVER_VERSION,
    'targets':len(rows),
    'publishable_resolved':counts['RESOLVED'],
    'build_only':counts['BUILD_ONLY'],
    'review':counts['REVIEW'],
    'unresolved':counts['UNRESOLVED'],
    'technical_resolution_rate':round((counts['RESOLVED']+counts['BUILD_ONLY'])/len(rows),3),
    'publishable_resolution_rate':round(counts['RESOLVED']/len(rows),3),
    'items':[
        {'name':row['target']['name'],'status':r.status,'level':r.level,'publishable':r.publishable,'reason':r.reason,'sources':[m.candidate.source for m in r.matches]}
        for row,r in results
    ]
}
print(json.dumps(report,ensure_ascii=False,indent=2))
