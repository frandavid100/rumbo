from __future__ import annotations

import argparse
import concurrent.futures as cf
import html as htmlmod
import http.cookiejar
import json
import re
import threading
import time
import urllib.parse
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor

from nutrition_validation import validate_nutrition

BASE = "https://www.compraonline.alcampo.es"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36"
VERSION = "alcampo-detail-http-v2.2"
_TLS = threading.local()


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
    stops=[]
    tail=text[start:]
    for p in stop_patterns:
        m=re.search(p,tail,re.I)
        if m: stops.append(m.start())
    end=start+(min(stops) if stops else len(tail))
    value=text[start:end].strip(" :-|\n\t")
    return value[:max_len].strip() or None


def clean_html_fragment(value: str | None) -> str | None:
    if not value: return None
    value=re.sub(r"<br\s*/?>","\n",value,flags=re.I)
    value=re.sub(r"<[^>]+>"," ",value)
    value=htmlmod.unescape(value).replace("\xa0"," ")
    value=re.sub(r"[ \t\r\f\v]+"," ",value)
    value=re.sub(r"\n\s*","\n",value)
    return value.strip() or None


def table_value(body: str, labels: tuple[str,...]) -> str | None:
    """Read a labelled two-cell product characteristic without swallowing later rows."""
    for label in labels:
        pattern=(
            r"<tr[^>]*>\s*<t[dh][^>]*>\s*"+label+
            r"\s*</t[dh]>\s*<t[dh][^>]*>(.*?)</t[dh]>\s*</tr>"
        )
        m=re.search(pattern,body,re.I|re.S)
        if m:
            return clean_html_fragment(m.group(1))
    return None


def parse_nutrition(text: str):
    nt=section(text,(r"Datos nutricionales?",r"Informaci[oó]n nutricional",r"Valores? nutricionales?"),(
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
    basis=None
    for pattern in (
        r"(?:por|cada)\s*100\s*(g|ml)\b",
        r"(?:^|\n)\s*100\s*(g|ml)\b",
        r"\b100\s*(g|ml)\s*(?:\n|$)",
    ):
        m=re.search(pattern,nt,re.I)
        if m:
            basis=f"100_{m.group(1).lower()}"; break
    return {
        "calories":kcal,
        "fat_g":g((r"Grasas?(?!\s+saturadas)",)),
        "carbohydrate_g":g((r"Hidratos?\s+de\s+carbono",r"Carbohidratos?")),
        "protein_g":g((r"Prote[ií]nas?",)),
        "fiber_g":g((r"Fibra(?:\s+alimentaria)?",)),
        "salt_g":g((r"Sal\b",)),
        "basis":basis,
    }


def parse_fields(body: str):
    parser=VisibleText(); parser.feed(body); text=parser.text()
    ingredients=section(text,(r"\nIngredientes\s*:?",r"^Ingredientes\s*:?"),(
        r"\nAl[eé]rgenos\b",r"\nDatos nutricionales?\b",r"\nInformaci[oó]n nutricional\b",r"\nCaracter[ií]sticas\b",r"\nConservaci[oó]n\b",r"\nAlmacenamiento\b",r"\nPreparaci[oó]n\b"
    ),max_len=8000)
    if ingredients:
        ingredients=re.sub(r"^Ingredientes\s*:\s*","",ingredients,flags=re.I).strip() or None

    # Prefer the exact characteristics-table cell. The old visible-text fallback could
    # accidentally include every subsequent row (net amount, Nutriscore, claims, etc.).
    legal=table_value(body,(r"Denominaci[oó]n\s+legal(?:\s+del\s+alimento)?",r"Denominaci[oó]n\s+del\s+alimento"))
    if not legal:
        legal=section(text,(r"\nDenominaci[oó]n legal(?: del alimento)?\s*:?",r"\nDenominaci[oó]n del alimento\s*:?"),(
            r"\nCantidad neta\b",r"\nSigno de estimaci[oó]n\b",r"\nNutriscore\b",
            r"\nDeclaraci[oó]n nutricional\b",r"\nDenominaci[oó]n de origen\b",
            r"\nOtros datos\b",r"\nVegano\b",r"\nIngredientes\b",r"\nAl[eé]rgenos\b",
            r"\nDatos nutricionales?\b",r"\nCaracter[ií]sticas\b",r"\nConservaci[oó]n\b",
            r"\nPreparaci[oó]n\b",
        ),max_len=1000)

    gtin=None
    for p in (r'"gtin13"\s*:\s*"(\d{8,14})"',r'"gtin"\s*:\s*"(\d{8,14})"',r'"ean"\s*:\s*"(\d{8,14})"',r'"barcode"\s*:\s*"(\d{8,14})"'):
        m=re.search(p,body,re.I)
        if m: gtin=m.group(1); break
    title=None
    m=re.search(r"<h1[^>]*>(.*?)</h1>",body,re.I|re.S)
    if m:
        title=clean_html_fragment(m.group(1))
    if not title:
        m=re.search(r'<script[^>]+data-test=["\']product-details-structured-data["\'][^>]*>(.*?)</script>',body,re.I|re.S)
        if m:
            try:
                obj=json.loads(htmlmod.unescape(m.group(1)))
                if isinstance(obj,dict) and isinstance(obj.get("name"),str): title=obj["name"].strip() or None
            except Exception:
                pass
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
    nutrition_basis:str|None
    nutrition_status:str
    error:str|None
    html_bytes:int=0


def _new_opener():
    jar=http.cookiejar.CookieJar()
    return build_opener(HTTPCookieProcessor(jar))


def _thread_opener(reset: bool=False):
    if reset or not getattr(_TLS,"opener",None):
        _TLS.opener=_new_opener()
    return _TLS.opener


def _request(opener, url: str, referer: str):
    req=Request(url,headers={
        "User-Agent":UA,
        "Accept":"text/html,application/xhtml+xml",
        "Accept-Language":"es-ES,es;q=0.9",
        "Cache-Control":"no-cache",
        "Referer":referer,
    })
    with opener.open(req,timeout=60) as r:
        status=getattr(r,"status",200); final=r.geturl(); raw=r.read()
    return status,final,raw,raw.decode("utf-8",errors="replace")


def _prime(opener):
    try:
        status,_,_,body=_request(opener,BASE+"/categories/alimentaci%C3%B3n/OCC10",BASE+"/")
        return status != 202 and not ("window.gokuProps" in body and len(body)<10000)
    except Exception:
        return False


def product_slug(name: str | None) -> str | None:
    if not name: return None
    value=htmlmod.unescape(str(name)).strip().lower()
    value=re.sub(r"[^\w]+","-",value,flags=re.UNICODE).strip("-_")
    return value or None


def candidate_urls(sku: str, name_hint: str | None) -> list[str]:
    urls=[]
    slug=product_slug(name_hint)
    if slug:
        urls.append(f"{BASE}/products/{urllib.parse.quote(slug,safe='-')}/{urllib.parse.quote(str(sku),safe='')}")
    urls.append(f"{BASE}/products/x/{urllib.parse.quote(str(sku),safe='')}")
    return list(dict.fromkeys(urls))


def fetch_one(sku: str, name_hint: str | None=None, attempts=10) -> Detail:
    urls=candidate_urls(sku,name_hint)
    last=None
    last_url=urls[-1]
    opener=_thread_opener()
    if not getattr(_TLS,"primed",False):
        _TLS.primed=_prime(opener)
    pending_streak=0
    per_url=max(3,(attempts+len(urls)-1)//len(urls))
    for url_index,url in enumerate(urls):
        last_url=url
        for local_attempt in range(1,per_url+1):
            global_attempt=url_index*per_url+local_attempt
            try:
                status,final,raw,body=_request(opener,url,BASE+"/")
                if status==202 or ("window.gokuProps" in body and len(body)<10000):
                    last=f"WAF_PENDING_{status}"; pending_streak+=1
                    if pending_streak in (3,6):
                        opener=_thread_opener(reset=True); _TLS.primed=_prime(opener)
                    time.sleep(min(0.7*global_attempt,6)); continue
                pending_streak=0
                text,name,gtin,legal,ingredients,nt=parse_fields(body)
                if all(nt[k] is not None for k in ("calories","protein_g","carbohydrate_g","fat_g")):
                    vr=validate_nutrition(nt["calories"],nt["protein_g"],nt["carbohydrate_g"],nt["fat_g"],nt["fiber_g"],nt["salt_g"])
                    ns="DECLARED_VALID" if vr.valid else "DECLARED_INVALID:"+",".join(vr.reasons)
                else: ns="DECLARED_INCOMPLETE"
                return Detail(str(sku),url,final,status,name,gtin,legal,ingredients,nt["calories"],nt["protein_g"],nt["carbohydrate_g"],nt["fat_g"],nt["fiber_g"],nt["salt_g"],nt.get("basis"),ns,None,len(raw))
            except HTTPError as exc:
                try: preview=exc.read().decode("utf-8",errors="replace")[:200]
                except Exception: preview=""
                last=f"HTTP_{exc.code}:{preview}"
                # A guessed slug can be stale or differ from the retailer's canonical
                # transliteration. Move immediately to the stable /products/x/<sku> route.
                if exc.code in (404,410) and url_index < len(urls)-1:
                    break
                if exc.code in (403,408,425,429,500,502,503,504):
                    if exc.code in (403,429) and local_attempt in (3,6):
                        opener=_thread_opener(reset=True); _TLS.primed=_prime(opener)
                    time.sleep(min(global_attempt*1.0,7)); continue
                break
            except (URLError, TimeoutError) as exc:
                last=f"{type(exc).__name__}:{exc}"; time.sleep(min(global_attempt*0.8,6))
            except Exception as exc:
                last=f"{type(exc).__name__}:{exc}"; time.sleep(min(global_attempt*0.8,6))
    return Detail(str(sku),last_url,None,None,None,None,None,None,None,None,None,None,None,None,None,"FETCH_ERROR",last,0)


def load_targets(path: Path | None, explicit: list[str], limit: int):
    targets: dict[str,str|None]={}
    if path:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            row=json.loads(line); sku=row.get("sku") or row.get("retailer_sku")
            if sku is not None:
                key=str(sku)
                targets[key]=str(row.get("name") or "").strip() or targets.get(key)
    for sku in explicit:
        targets.setdefault(str(sku),None)
    rows=list(targets.items())
    return rows[:limit] if limit else rows


def fetch_batch(targets:list[tuple[str,str|None]],workers:int,attempts:int):
    results=[]
    def one(t): return fetch_one(t[0],t[1],attempts=attempts)
    with cf.ThreadPoolExecutor(max_workers=max(1,workers)) as ex:
        for d in ex.map(one,targets): results.append(d)
    return results


def run(out:Path,targets:list[tuple[str,str|None]],workers:int,retry_rounds:int=2):
    out.mkdir(parents=True,exist_ok=True)
    name_by_sku=dict(targets)
    details=fetch_batch(targets,workers,10)
    for round_no in range(1,retry_rounds+1):
        failed=[d.sku for d in details if d.error is not None and (d.error.startswith("WAF_PENDING_") or d.error.startswith("HTTP_403") or d.error.startswith("HTTP_429") or "Timeout" in d.error)]
        if not failed: break
        print(f"retry_round={round_no} transient_failures={len(failed)}",flush=True)
        time.sleep(min(2.0*round_no,6.0))
        retry_targets=[(sku,name_by_sku.get(sku)) for sku in failed]
        retried={d.sku:d for d in fetch_batch(retry_targets,max(1,min(workers,2)),12)}
        details=[retried.get(d.sku,d) if d.sku in retried else d for d in details]
    valid=sum(x.nutrition_status=="DECLARED_VALID" for x in details); err=sum(x.error is not None for x in details)
    print(f"progress={len(details)}/{len(targets)} valid={valid} errors={err}",flush=True)
    with (out/"details.jsonl").open("w",encoding="utf-8") as f:
        for d in details: f.write(json.dumps(asdict(d),ensure_ascii=False)+"\n")
    counts={
        "requested":len(targets),
        "fetched":sum(d.error is None for d in details),
        "errors":sum(d.error is not None for d in details),
        "with_name":sum(bool(d.name) for d in details),
        "with_gtin":sum(bool(d.gtin) for d in details),
        "with_legal_name":sum(bool(d.legal_name) for d in details),
        "with_ingredients":sum(bool(d.ingredients) for d in details),
        "with_nutrition_basis":sum(bool(d.nutrition_basis) for d in details),
        "declared_valid_nutrition":sum(d.nutrition_status=="DECLARED_VALID" for d in details),
        "declared_incomplete_nutrition":sum(d.nutrition_status=="DECLARED_INCOMPLETE" for d in details),
        "declared_invalid_nutrition":sum(d.nutrition_status.startswith("DECLARED_INVALID") for d in details),
        "downloaded_html_bytes":sum(d.html_bytes for d in details),
    }
    summary={"source":BASE,"version":VERSION,"counts":counts,"canonical_slug_fallback":True}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2)); return summary


def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path);p.add_argument("--sku",action="append",default=[]);p.add_argument("--limit",type=int,default=0);p.add_argument("--workers",type=int,default=4);p.add_argument("--retry-rounds",type=int,default=2);p.add_argument("--out",type=Path,default=Path("alcampo-detail-output"));p.add_argument("--min-valid",type=int,default=0)
    a=p.parse_args(); targets=load_targets(a.input,a.sku,a.limit); s=run(a.out,targets,a.workers,a.retry_rounds); return 0 if s["counts"]["declared_valid_nutrition"]>=a.min_valid else 2
if __name__=="__main__": raise SystemExit(main())
