from __future__ import annotations

import html
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen

from mercadona_weekly_catalog_adapter import deterministic_candidate_ids, fetch_product_ids, stratified_sample
from pilot_large_catalog import _fetch_candidate_products, _is_food_category

BASE = Path(__file__).resolve().parent
FIX = BASE / "fixtures"
OUT = BASE / "cross-retailer-probe-output"
SEED = "rumbo-mercadona-pilot-2026-08"

RETAILERS = {
    "carrefour": {
        "search": "https://www.carrefour.es/supermercado?q={q}",
        "host": "https://www.carrefour.es",
        "product_re": re.compile(r'href=["\']([^"\']+/supermercado/[^"\']+/R-[^"\']+/p[^"\']*)', re.I),
    },
    "dia": {
        "search_candidates": [
            "https://www.dia.es/search?q={q}",
            "https://www.dia.es/search?text={q}",
            "https://www.dia.es/buscar?q={q}",
        ],
        "host": "https://www.dia.es",
        "product_re": re.compile(r'href=["\']([^"\']+/p/[^"\'#?]+)', re.I),
    },
    "bonarea": {
        "search": "https://www.bonarea-online.com/es/shop/find?searchWords={q}",
        "host": "https://www.bonarea-online.com",
        "product_re": re.compile(r'href=["\']([^"\']+/(?:online/producto|es/shop/product)/[^"\']+)', re.I),
    },
}

PRIVATE_MARKERS = {
    "hacendado", "deliplus", "bosque verde", "compy", "mercadona",
}

@dataclass
class Hit:
    retailer: str
    product_id: str
    mercadona_name: str
    mercadona_brand: str | None
    url: str
    candidate_name: str | None
    candidate_brand: str | None
    candidate_gtin: str | None
    similarity: float
    nutrition: dict | None
    identity_status: str


def norm(text: str | None) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).lower()
    return " ".join(text.split())


def fetch_text(url: str, timeout: float = 20.0) -> str:
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; RumboCatalogProbe/1.0; +https://github.com/frandavid100/rumbo)",
        "Accept-Language": "es-ES,es;q=0.9",
    })
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", errors="replace")


def strip_tags(s: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def jsonld_products(page: str) -> list[dict]:
    out = []
    for raw in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page, flags=re.I | re.S):
        try:
            obj = json.loads(html.unescape(raw).strip())
        except Exception:
            continue
        queue = obj if isinstance(obj, list) else [obj]
        while queue:
            x = queue.pop(0)
            if isinstance(x, dict):
                if str(x.get("@type", "")).lower() == "product":
                    out.append(x)
                graph = x.get("@graph")
                if isinstance(graph, list):
                    queue.extend(graph)
    return out


def product_meta(page: str) -> tuple[str | None, str | None, str | None]:
    products = jsonld_products(page)
    if products:
        p = products[0]
        brand = p.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        gtin = p.get("gtin13") or p.get("gtin14") or p.get("gtin12") or p.get("gtin")
        return p.get("name"), str(brand) if brand else None, str(gtin) if gtin else None
    title = re.search(r"<h1[^>]*>(.*?)</h1>", page, flags=re.I | re.S)
    return strip_tags(title.group(1)) if title else None, None, None


def number(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, flags=re.I)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def nutrition_from_text(page: str) -> dict | None:
    text = strip_tags(page)
    kcal = number(r"(?:valor\s+energetico[^0-9]{0,80})?(\d+(?:[.,]\d+)?)\s*kcal", text)
    protein = number(r"prote[ií]nas?\s*(?:\(g\))?\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*g", text)
    carb = number(r"hidratos?\s+de\s+carbono\s*(?:\(g\))?\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*g", text)
    fat = number(r"grasas?\s*(?:\(g\))?\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*g", text)
    if None in (kcal, protein, carb, fat):
        return None
    return {"calories": kcal, "protein_g": protein, "carbohydrate_g": carb, "fat_g": fat}


def product_links(retailer: str, page: str) -> list[str]:
    cfg = RETAILERS[retailer]
    links = []
    for raw in cfg["product_re"].findall(page):
        u = urljoin(cfg["host"], html.unescape(raw))
        if u not in links:
            links.append(u)
    return links[:8]


def search_pages(retailer: str, query: str) -> list[tuple[str, str]]:
    cfg = RETAILERS[retailer]
    urls = []
    if "search" in cfg:
        urls = [cfg["search"].format(q=quote_plus(query))]
    else:
        urls = [x.format(q=quote_plus(query)) for x in cfg["search_candidates"]]
    pages = []
    for u in urls:
        try:
            page = fetch_text(u)
            pages.append((u, page))
            if product_links(retailer, page):
                break
        except Exception:
            continue
    return pages


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def identity_status(merc_name: str, merc_brand: str | None, cand_name: str | None,
                    cand_brand: str | None, gtin: str | None, score: float) -> str:
    # GTIN exposed by the retailer is the preferred automatic identity path.
    if gtin and score >= 0.78:
        return "GTIN_CANDIDATE"
    mb, cb = norm(merc_brand), norm(cand_brand)
    if mb and cb and mb == cb and score >= 0.90:
        return "STRONG_NAME_BRAND_CANDIDATE"
    if score >= 0.94:
        return "STRONG_NAME_CANDIDATE_REVIEW"
    return "WEAK_CANDIDATE"


def persisted_nutrition_ids() -> set[str]:
    ids = set()
    structured = FIX / "pilot_300_structured_resolved.json"
    if structured.exists():
        ids |= {str(x["product_id"]) for x in json.loads(structured.read_text(encoding="utf-8"))}
    for path in FIX.glob("pilot_300_declared_label_evidence*.json"):
        ids |= {str(x["product_id"]) for x in json.loads(path.read_text(encoding="utf-8"))}
    generic = FIX / "generic_fdc_accepted_mappings.json"
    if generic.exists():
        ids |= {str(x["product_id"]) for x in json.loads(generic.read_text(encoding="utf-8"))}
    return ids


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    limit = int(os.environ.get("CROSS_RETAILER_PENDING_SAMPLE", "60"))
    delay = float(os.environ.get("CROSS_RETAILER_DELAY", "0.35"))

    ids = fetch_product_ids()
    candidate_ids = deterministic_candidate_ids(ids, seed=SEED, limit=900)
    products, acquisition_errors = _fetch_candidate_products(candidate_ids, 16)
    foods = [p for p in products if _is_food_category(p.category_key)]
    sample = stratified_sample(foods, size=300, per_category_cap=24)
    already = persisted_nutrition_ids()
    pending = [p for p in sample if str(p.product_id) not in already]
    pending = pending[:limit]

    hits: list[Hit] = []
    retailer_stats = {r: {"searched": 0, "search_pages_with_products": 0, "nutrition_candidates": 0,
                          "strong_candidates": 0, "gtin_candidates": 0} for r in RETAILERS}

    for idx, p in enumerate(pending, 1):
        name = p.name
        brand = p.brand
        # Private Mercadona brands cannot be the same commercial product at another retailer.
        if any(marker in norm(name + " " + (brand or "")) for marker in PRIVATE_MARKERS):
            continue
        query = " ".join(x for x in [brand or "", name] if x).strip()
        for retailer in RETAILERS:
            retailer_stats[retailer]["searched"] += 1
            pages = search_pages(retailer, query)
            links = []
            for _, page in pages:
                for link in product_links(retailer, page):
                    if link not in links:
                        links.append(link)
            if links:
                retailer_stats[retailer]["search_pages_with_products"] += 1
            best: Hit | None = None
            for link in links[:5]:
                try:
                    product_page = fetch_text(link)
                except Exception:
                    continue
                cand_name, cand_brand, cand_gtin = product_meta(product_page)
                score = similarity(name, cand_name or "")
                nutrition = nutrition_from_text(product_page)
                status = identity_status(name, brand, cand_name, cand_brand, cand_gtin, score)
                hit = Hit(retailer, str(p.product_id), name, brand, link, cand_name, cand_brand,
                          cand_gtin, round(score, 4), nutrition, status)
                if best is None or hit.similarity > best.similarity:
                    best = hit
            if best and best.nutrition:
                hits.append(best)
                retailer_stats[retailer]["nutrition_candidates"] += 1
                if best.identity_status.startswith("STRONG"):
                    retailer_stats[retailer]["strong_candidates"] += 1
                if best.identity_status == "GTIN_CANDIDATE":
                    retailer_stats[retailer]["gtin_candidates"] += 1
            time.sleep(delay)
        print(f"cross-retailer={idx}/{len(pending)} hits={len(hits)}", flush=True)

    strong = [h for h in hits if h.identity_status in {"GTIN_CANDIDATE", "STRONG_NAME_BRAND_CANDIDATE"}]
    report = {
        "version": "1.0.0",
        "pilot_sample": 300,
        "persisted_nutrition_ids": len(already),
        "pending_total_estimate": max(0, 300 - len(already)),
        "pending_probed": len(pending),
        "retailer_stats": retailer_stats,
        "nutrition_candidate_hits": len(hits),
        "strong_identity_candidates": len(strong),
        "policy": "No cross-retailer nutrition is accepted automatically without exact product identity; private-label Mercadona products are skipped.",
        "hits": [asdict(x) for x in hits],
        "acquisition_errors": acquisition_errors,
    }
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"hits", "acquisition_errors"}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
