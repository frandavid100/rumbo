from __future__ import annotations

import argparse
import concurrent.futures as cf
import html as htmlmod
import json
import re
import time
import urllib.parse
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from nutrition_validation import validate_nutrition

BASE = "https://www.compraonline.alcampo.es"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36"
VERSION = "alcampo-detail-http-v1.0"


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("script","style","noscript","svg"): self.skip += 1
        elif not self.skip and tag.lower() in ("p","div","li","tr","td","th","h1","h2","h3","section","br","dt","dd"): self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag.lower() in ("script","style","noscript","svg") and self.skip: self.skip -= 1
        elif not self.skip and tag.lower() in ("p","div","li","tr","td","th","h1","h2","h3","section","dt","dd"): self.parts.append("\n")
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)
    def text(self):
        raw="".join(self.parts).replace("\xa0"," ")
        raw=re.sub(r"[ \t\r\f\v]+"," ",raw)
        raw=re.sub(r"\n[ \t]+","\n",raw)
        raw=re.sub(r"\n{2,}","\n",raw)
        return raw.strip()


def number(s):
    if s is None: return None
    m=re.search(r"[-+]?\d+(?:[.,]\d+)?",str(s))
    return float(m.group(0).replace(",",".")) if m else None


def section(text: str, start_patterns: tuple[str,...], stop_patterns: tuple[str,...], max_len=10000) -> str | None:
    starts=[]
    for p in start_patterns:
        m=re.search(p,text,re.I)
        if m: starts.append((m.start(),m.end()))
    if not starts: return None
    _, start=min(starts)
    end=min([m.start() for p in stop_patterns for m in [re.search(p,text[start:],re.I)] if m] or [len(text)-start]) + start
    value=text[start:end].strip(" :-|\n\t")
    return value[:max_len].strip() or None


def parse_nutrition(text: str):
    nt=section(text,(r"Datos nutricionales?",r"Informaci[oó]n nutricional"),(
        r"\nIngredientes\b",r"\nAl[eé]rgenos\b",r"\nCaracter[ií]sticas\b",r"\nConservaci[oó]n\b",r"\nAlmacenamiento\b",r"\nProductos similares\b",r"\nOpiniones\b"
    ),max_len=12000) or text
    def g(patterns):
        for p in patterns:
            m=re.search(p+r"[^0-9]{0,45}([0-9]+(?:[.,][0-9]+)?)\s*g\b",nt,re.I)
            if m: return number(m.group(1))
        return None
    kcal=None
    for p in (r"Valor energ[eé]tico\s*\(Kcal\)",r"Valor energ[eé]tico",r"Energ[ií]a"):
        m=re.search(p+r"[^0-9]{0,60}([0-9]+(?:[.,][0-9]+)?)\s*kcal\b",nt,re.I)
        if m: kcal=number(m.group(1)); break
    return {
        "calories":kcal,
        "fat_g":g((r"Grasas?(?!\s+saturadas)",)),
        "carbohydrate_g":g((r"Hidratos?\s+de\s+carbono",r"Carbohidratos?")),
        "protein_g":g((r"Prote[ií]nas?",)),
        "fiber_g":g((r"Fibra(?:\s+alimentaria)?",)),
        "salt_g":g((r"Sal\b",)),
    }


def parse_fields(body: str):
    parser=VisibleText(); parser.feed(body); text=parser.text()
    ingredients=section(text,(r"\nIngredientes\s*:?",r"^Ingredientes\s*:?"),(
        r"\nAl[eé]rgenos\b",r"\nDatos nutricionales?\b",r"\nInformaci[oó]n nutricional\b",r"\nCaracter[ií]sticas\b",r"\nConservaci[oó]n\b",r"\nAlmacenamiento\b",r"\nPreparaci[oó]n\b"
    ),max_len=8000)
    legal=section(text,(r"\nDenominaci[oó]n legal(?: del alimento)?\s*:?",r"\nDenominaci[oó]n del alimento\s*:?"),(
        r"\nIngredientes\b",r"\nAl[eé]rgenos\b",r"\nDatos nutricionales?\b",r"\nCaracter[ií]sticas\b",r"\nConservaci[oó]n\b"
    ),max_len=2000)
    gtin=None
    for p in (r'"gtin13"\s*:\s*"(\d{8,14})"',r'"gtin"\s*:\s*"(\d{8,14})"',r'"ean"\s*:\s*"(\d{8,14})"',r'"barcode"\s*:\s*"(\d{8,14})"'):
        m=re.search(p,body,re.I)
        if m: gtin=m.group(1); break
    title=None
    m=re.search(r"<h1[^>]*>(.*?)</h1>",body,re.I|re.S)
    if m:
        tmp=re.sub(r"<[^>]+>"," ",m.group(1)); title=re.sub(r"\s+"," ",htmlmod.unescape(tmp)).strip() or None
    nutrition=parse_nutrition(text)
    return text,title,gtin,legal,ingredients,nutrition


@dataclass
class Detail:
    sku:str
    requested_url:str
    canonical_url:str|None
    status:int|None
    name:str|None
    gtin:str|None
    legal_name:str|None
    ingredients:str|None
    calories:float|None
    protein_g:float|None
    carbohydrate_g:float|None
    fat_g:float|None
    fiber_g:float|None
    salt_g:float|None
    nutrition_status:str
    error:str|None
    html_bytes:int=0


def fetch_one(sku: str, attempts=5) -> Detail:
    url=f"{BASE}/products/x/{urllib.parse.quote(str(sku),safe='')}"
    last=None
    for attempt in range(1,attempts+1):
        req=Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"es-ES,es;q=0.9","Cache-Control":"no-cache"})
        try:
            with build_opener().open(req,timeout=60) as r:
                status=getattr(r,"status",200); final=r.geturl(); raw=r.read(); body=raw.decode("utf-8",errors="replace")
            if status==202 or "window.gokuProps" in body and len(body)<10000:
                last=f"WAF_PENDING_{status}"; time.sleep(min(attempt*1.0,5)); continue
            text,name,gtin,legal,ingredients,nt=parse_fields(body)
            if all(nt[k] is not None for k in ("calories","protein_g","carbohydrate_g","fat_g")):
                vr=validate_nutrition(nt["calories"],nt["protein_g"],nt["carbohydrate_g"],nt["fat_g"],nt["fiber_g"],nt["salt_g"])
                ns="DECLARED_VALID" if vr.valid else "DECLARED_INVALID:"+",".join(vr.reasons)
            else: ns="DECLARED_INCOMPLETE"
            return Detail(str(sku),url,final,status,name,gtin,legal,ingredients,nt["calories"],nt["protein_g"],nt["carbohydrate_g"],nt["fat_g"],nt["fiber_g"],nt["salt_g"],ns,None,len(raw))
        except HTTPError as exc:
            try: preview=exc.read().decode("utf-8",errors="replace")[:200]
            except Exception: preview=""
            last=f"HTTP_{exc.code}:{preview}"
            if exc.code in (403,408,425,429,500,502,503,504): time.sleep(min(attempt*1.2,6)); continue
            break
        except Exception as exc:
            last=f"{type(exc).__name__}:{exc}"; time.sleep(min(attempt*1.0,5))
    return Detail(str(sku),url,None,None,None,None,None,None,None,None,None,None,None,None,"FETCH_ERROR",last,0)


def load_skus(path: Path | None, explicit: list[str], limit: int):
    skus=[]
    if path:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            row=json.loads(line); sku=row.get("sku") or row.get("retailer_sku")
            if sku is not None: skus.append(str(sku))
    skus.extend(str(x) for x in explicit)
    skus=list(dict.fromkeys(skus))
    return skus[:limit] if limit else skus


def run(out:Path,skus:list[str],workers:int):
    out.mkdir(parents=True,exist_ok=True); details=[]; done=0
    with cf.ThreadPoolExecutor(max_workers=max(1,workers)) as ex:
        for d in ex.map(fetch_one,skus):
            details.append(d); done+=1
            if done%25==0 or done==len(skus):
                valid=sum(x.nutrition_status=="DECLARED_VALID" for x in details); err=sum(x.error is not None for x in details)
                print(f"progress={done}/{len(skus)} valid={valid} errors={err}",flush=True)
            time.sleep(0.02)
    with (out/"details.jsonl").open("w",encoding="utf-8") as f:
        for d in details: f.write(json.dumps(asdict(d),ensure_ascii=False)+"\n")
    counts={"requested":len(skus),"fetched":sum(d.error is None for d in details),"errors":sum(d.error is not None for d in details),"with_name":sum(bool(d.name) for d in details),"with_gtin":sum(bool(d.gtin) for d in details),"with_legal_name":sum(bool(d.legal_name) for d in details),"with_ingredients":sum(bool(d.ingredients) for d in details),"declared_valid_nutrition":sum(d.nutrition_status=="DECLARED_VALID" for d in details),"declared_incomplete_nutrition":sum(d.nutrition_status=="DECLARED_INCOMPLETE" for d in details),"declared_invalid_nutrition":sum(d.nutrition_status.startswith("DECLARED_INVALID") for d in details),"downloaded_html_bytes":sum(d.html_bytes for d in details)}
    summary={"source":BASE,"version":VERSION,"counts":counts}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(summary,ensure_ascii=False,indent=2)); return summary


def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path);p.add_argument("--sku",action="append",default=[]);p.add_argument("--limit",type=int,default=0);p.add_argument("--workers",type=int,default=4);p.add_argument("--out",type=Path,default=Path("alcampo-detail-output"));p.add_argument("--min-valid",type=int,default=0)
    a=p.parse_args(); skus=load_skus(a.input,a.sku,a.limit); s=run(a.out,skus,a.workers); return 0 if s["counts"]["declared_valid_nutrition"]>=a.min_valid else 2
if __name__=="__main__": raise SystemExit(main())
