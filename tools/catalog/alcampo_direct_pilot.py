from __future__ import annotations

import argparse
import concurrent.futures as cf
import html as html_lib
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

BASE = "https://www.compraonline.alcampo.es"
SITEMAP = BASE + "/sitemap.xml"
SAMPLE = BASE + "/products/carbonell-aceite-oliva-5l/898473"
UA = "RumboCatalogPilot/1.0 (+https://github.com/frandavid100/rumbo)"


@dataclass
class Observation:
    url: str
    status: str
    http_ok: bool
    name: str | None
    brand: str | None
    gtin: str | None
    sku: str | None
    ingredients: str | None
    legal_name: str | None
    calories: float | None
    protein_g: float | None
    carbohydrate_g: float | None
    fat_g: float | None
    fiber_g: float | None
    salt_g: float | None
    nutrition_complete: bool
    error: str | None = None


def fetch(url: str, timeout: int = 25) -> str:
    req = Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def textify(raw: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html_lib.unescape(s)).strip()


def first(patterns: list[str], raw: str) -> str | None:
    for p in patterns:
        m = re.search(p, raw, re.I | re.S)
        if m:
            return html_lib.unescape(m.group(1)).strip()
    return None


def num(v: str | None) -> float | None:
    if not v:
        return None
    try:
        return float(v.replace(".", "").replace(",", ".") if "," in v else v)
    except ValueError:
        return None


def nutrition_value(text: str, labels: str) -> float | None:
    patterns = [
        rf"(?:{labels})\s*[:\-]?\s*([0-9]+(?:[.,][0-9]+)?)\s*g\b",
        rf"(?:{labels})[^0-9]{{0,50}}([0-9]+(?:[.,][0-9]+)?)\s*g\b",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return num(m.group(1))
    return None


def parse_product(url: str) -> Observation:
    try:
        raw = fetch(url)
        text = textify(raw)
        name = first([r'<h1[^>]*>(.*?)</h1>', r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)'], raw)
        brand = first([r'"brand"\s*:\s*"([^"]+)"', r'"brand"\s*:\s*\{[^{}]*"name"\s*:\s*"([^"]+)"'], raw)
        gtin = first([r'"gtin13"\s*:\s*"(\d{8,14})"', r'"gtin"\s*:\s*"(\d{8,14})"', r'"ean"\s*:\s*"(\d{8,14})"'], raw)
        sku = first([r'"sku"\s*:\s*"?([A-Za-z0-9_-]+)"?'], raw) or url.rstrip('/').split('/')[-1]
        ingredients = first([
            r"Ingredientes\s*</[^>]+>\s*<[^>]+>(.*?)</[^>]+>",
            r'"ingredients"\s*:\s*"([^"]+)"',
        ], raw)
        legal_name = first([
            r"Denominaci[oó]n legal\s*</[^>]+>\s*<[^>]+>(.*?)</[^>]+>",
            r'"legalName"\s*:\s*"([^"]+)"',
        ], raw)

        kcal = None
        for p in [r"Valor energ[eé]tico[^0-9]{0,80}([0-9]+(?:[.,][0-9]+)?)\s*kcal", r"([0-9]+(?:[.,][0-9]+)?)\s*kcal"]:
            m = re.search(p, text, re.I)
            if m:
                kcal = num(m.group(1)); break
        fat = nutrition_value(text, r"grasas?(?:\s+totales?)?")
        carb = nutrition_value(text, r"hidratos?\s+de\s+carbono")
        protein = nutrition_value(text, r"prote[ií]nas?")
        fiber = nutrition_value(text, r"fibra(?:\s+alimentaria)?")
        salt = nutrition_value(text, r"sal")
        complete = all(v is not None for v in (kcal, fat, carb, protein))
        return Observation(url, "OK", True, name, brand, gtin, sku, ingredients, legal_name,
                           kcal, protein, carb, fat, fiber, salt, complete)
    except Exception as exc:
        return Observation(url, "ERROR", False, None, None, None, None, None, None,
                           None, None, None, None, None, None, False,
                           f"{type(exc).__name__}:{exc}")


def sitemap_urls(max_urls: int) -> tuple[list[str], dict]:
    meta = {"sitemap_url": SITEMAP, "sitemap_ok": False, "sitemaps_seen": 0, "product_urls_seen": 0}
    try:
        root_raw = fetch(SITEMAP)
        root = ET.fromstring(root_raw)
        locs = [x.text.strip() for x in root.iter() if x.tag.endswith('loc') and x.text]
        meta["sitemap_ok"] = True
        urls: list[str] = []
        if any('/products/' in x for x in locs):
            urls.extend(x for x in locs if '/products/' in x)
        else:
            child_maps = [x for x in locs if x.endswith('.xml') or 'sitemap' in x]
            meta["sitemaps_seen"] = len(child_maps)
            for sm in child_maps[:30]:
                if len(urls) >= max_urls:
                    break
                try:
                    raw = fetch(sm)
                    r = ET.fromstring(raw)
                    child_locs = [x.text.strip() for x in r.iter() if x.tag.endswith('loc') and x.text]
                    urls.extend(x for x in child_locs if '/products/' in x)
                    time.sleep(0.05)
                except Exception:
                    continue
        dedup = list(dict.fromkeys(urls))
        meta["product_urls_seen"] = len(dedup)
        return dedup[:max_urls], meta
    except Exception as exc:
        meta["sitemap_error"] = f"{type(exc).__name__}:{exc}"
        return [SAMPLE], meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='alcampo-direct-pilot-output')
    ap.add_argument('--max-products', type=int, default=80)
    ap.add_argument('--workers', type=int, default=12)
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    urls, discovery = sitemap_urls(args.max_products)
    if SAMPLE not in urls:
        urls = [SAMPLE] + urls
    urls = list(dict.fromkeys(urls))[:args.max_products]

    observations: list[Observation] = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, obs in enumerate(ex.map(parse_product, urls), 1):
            observations.append(obs)
            if i % 10 == 0 or i == len(urls):
                print(f"progress={i}/{len(urls)} ok={sum(o.http_ok for o in observations)} nutrition={sum(o.nutrition_complete for o in observations)}", flush=True)

    counts = {
        "requested": len(urls),
        "http_ok": sum(o.http_ok for o in observations),
        "errors": sum(not o.http_ok for o in observations),
        "with_gtin": sum(bool(o.gtin) for o in observations),
        "with_ingredients": sum(bool(o.ingredients) for o in observations),
        "with_legal_name": sum(bool(o.legal_name) for o in observations),
        "nutrition_complete": sum(o.nutrition_complete for o in observations),
    }
    summary = {
        "source": "Alcampo direct",
        "base": BASE,
        "discovery": discovery,
        "counts": counts,
        "sample_product": asdict(observations[0]) if observations else None,
        "assessment": {
            "direct_ci_access": counts["http_ok"] > 0,
            "mass_access_signal": counts["http_ok"] >= max(1, int(len(urls) * 0.9)),
            "nutrition_coverage": counts["nutrition_complete"] / len(urls) if urls else 0,
            "gtin_coverage": counts["with_gtin"] / len(urls) if urls else 0,
        },
        "legal_note": "Technical feasibility only. Redistribution rights must be reviewed separately before publishing a derived catalog.",
    }
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out / 'observations.jsonl').open('w', encoding='utf-8') as fh:
        for o in observations:
            fh.write(json.dumps(asdict(o), ensure_ascii=False) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if counts["http_ok"] else 2


if __name__ == '__main__':
    raise SystemExit(main())
