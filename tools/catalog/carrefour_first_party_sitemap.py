from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SOURCE = "CARREFOUR_FIRST_PARTY"
INDEX_URL = "https://www.carrefour.es/crs/cdn-static/sitemap-food/index.xml"
VERSION = "carrefour-first-party-sitemap-1.1"
PRODUCT_RE = re.compile(r"^https://www\.carrefour\.es/supermercado/.+/R-([^/]+)/p/?(?:\?.*)?$", re.I)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RumboCatalog/1.0; +https://github.com/frandavid100/rumbo)",
    "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.5",
    "Accept-Language": "es-ES,es;q=0.9",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def fetch_xml(url: str, timeout: int = 40) -> bytes:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=timeout) as response:
        raw = response.read()
    if raw[:2] == b"\x1f\x8b" or url.lower().endswith(".gz"):
        raw = gzip.decompress(raw)
    return raw


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(node, name: str):
    for child in node:
        if local_name(child.tag) == name:
            return (child.text or "").strip() or None
    return None


def allowed_sitemap(url: str) -> bool:
    """Follow only official same-host Carrefour sitemap children.

    Product extraction remains much stricter (`/supermercado/.../R-.../p`), so allowing
    Carrefour's other robots-declared sitemap indexes cannot turn corporate/tech URLs into
    supermarket evidence. This lets us test alternate official sitemap roots when the dedicated
    food CDN index is WAF-blocked.
    """
    p = urlparse(url)
    if p.scheme != "https" or p.netloc not in {"www.carrefour.es", "carrefour.es"}:
        return False
    path = p.path.lower()
    return path.endswith((".xml", ".xml.gz", ".gz")) or "sitemap" in path or "siteindex" in path


def crawl(index_url: str, max_sitemaps: int, delay: float):
    queue = [index_url]
    seen = set()
    products = {}
    diagnostics = []
    while queue and len(seen) < max_sitemaps:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            raw = fetch_xml(url)
            root = ET.fromstring(raw)
            kind = local_name(root.tag)
            diag = {"url": url, "bytes": len(raw), "kind": kind}
            if kind == "sitemapindex":
                children = []
                for node in root:
                    loc = child_text(node, "loc")
                    if loc and allowed_sitemap(loc):
                        children.append(loc)
                diag["children"] = len(children)
                queue.extend(x for x in children if x not in seen)
            elif kind == "urlset":
                found = 0
                for node in root:
                    loc = child_text(node, "loc")
                    if not loc:
                        continue
                    loc = loc.split("?", 1)[0].rstrip("/")
                    m = PRODUCT_RE.match(loc)
                    if not m:
                        continue
                    sku = m.group(1)
                    lastmod = child_text(node, "lastmod")
                    products[sku] = {
                        "retailer": "CARREFOUR",
                        "retailer_sku": sku,
                        "canonical_url": loc,
                        "url": loc,
                        "sitemap_lastmod": lastmod,
                        "source": SOURCE,
                        "evidence_type": "OBSERVED_LISTING",
                        "source_url": url,
                    }
                    found += 1
                diag["products"] = found
            else:
                diag["warning"] = f"unexpected_root:{kind}"
            diagnostics.append(diag)
        except Exception as exc:
            diagnostics.append({"url": url, "error": f"{type(exc).__name__}:{exc}"})
        if delay > 0 and queue:
            time.sleep(delay)
    return products, diagnostics, sorted(seen), list(queue)


def write_sqlite(path: Path, rows: list[dict], diagnostics: list[dict], metadata: dict):
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS sitemap_products(
      retailer_sku TEXT PRIMARY KEY,
      canonical_url TEXT NOT NULL,
      sitemap_lastmod TEXT,
      source TEXT NOT NULL,
      evidence_type TEXT NOT NULL,
      source_sitemap TEXT NOT NULL,
      observed_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sitemap_diagnostics(
      source_sitemap TEXT PRIMARY KEY,
      payload_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
    """)
    for row in rows:
        db.execute(
            "INSERT OR REPLACE INTO sitemap_products VALUES(?,?,?,?,?,?,?)",
            (
                row["retailer_sku"], row["canonical_url"], row.get("sitemap_lastmod"), SOURCE,
                "OBSERVED_LISTING", row["source_url"], row["observed_at"],
            ),
        )
    for d in diagnostics:
        db.execute("INSERT OR REPLACE INTO sitemap_diagnostics VALUES(?,?)", (d["url"], json.dumps(d, ensure_ascii=False)))
    for k, v in metadata.items():
        db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)", (k, str(v)))
    db.commit()
    db.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index-url", default=INDEX_URL)
    ap.add_argument("--out", default="carrefour-first-party-sitemap")
    ap.add_argument("--max-sitemaps", type=int, default=500)
    ap.add_argument("--delay", type=float, default=0.2)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    built_at = now_iso()
    products, diagnostics, seen, remaining = crawl(args.index_url, args.max_sitemaps, args.delay)
    rows = []
    evidence = []
    for sku in sorted(products):
        row = dict(products[sku])
        row["observed_at"] = built_at
        row["record_sha256"] = hashlib.sha256((row["canonical_url"] + "|" + (row.get("sitemap_lastmod") or "")).encode()).hexdigest()
        rows.append(row)
        for field in ("retailer_sku", "canonical_url", "sitemap_lastmod"):
            if row.get(field):
                evidence.append({
                    "retailer_sku": sku,
                    "field": field,
                    "value": row[field],
                    "source": SOURCE,
                    "evidence_type": "OBSERVED_LISTING",
                    "source_url": row["source_url"],
                    "observed_at": built_at,
                })

    with (out / "products.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out / "field_evidence.jsonl").open("w", encoding="utf-8") as f:
        for row in evidence:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out / "diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")

    errors = [d for d in diagnostics if d.get("error")]
    metadata = {
        "retailer": "CARREFOUR",
        "source": args.index_url,
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "extractor_version": VERSION,
        "built_at": built_at,
        "classification_performed": "false",
    }
    write_sqlite(out / "carrefour_first_party_sitemap.sqlite", rows, diagnostics, metadata)
    summary = {
        **metadata,
        "counts": {
            "sitemaps_visited": len(seen),
            "sitemap_fetch_errors": len(errors),
            "product_urls": len(rows),
            "evidence_rows": len(evidence),
            "remaining_sitemaps": len(remaining),
        },
        "errors": errors[:30],
        "sample": rows[:20],
        "provenance_note": (
            "Product identities and URLs come only from the selected official carrefour.es sitemap root "
            "and same-host sitemap children. Only canonical /supermercado/.../R-.../p product URLs are retained; "
            "no third-party product fields are copied."
        ),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    if not rows:
        return 2
    if remaining:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
