from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


SOURCE = "RADARSUPER_CANDIDATE_ONLY"


def canonicalize(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def main() -> int:
    ap = argparse.ArgumentParser(description="Export Carrefour product URLs as identity candidates only; no fields are promoted to first-party evidence.")
    ap.add_argument("sqlite")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    db = sqlite3.connect(args.sqlite)
    rows = db.execute(
        """
        SELECT retailer_sku, url
        FROM retailer_listings
        WHERE retailer='CARREFOUR'
          AND url IS NOT NULL
          AND url LIKE 'https://www.carrefour.es/%'
        ORDER BY retailer_sku
        """
    ).fetchall()
    db.close()

    seen: set[str] = set()
    out_rows = []
    for retailer_sku, url in rows:
        clean = canonicalize(url)
        if clean in seen:
            continue
        seen.add(clean)
        out_rows.append({
            "retailer": "CARREFOUR",
            "retailer_sku_candidate": retailer_sku,
            "canonical_url": clean,
            "candidate_source": SOURCE,
            "evidence_policy": "IDENTITY_CANDIDATE_ONLY_NOT_CARREFOUR_EVIDENCE",
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "retailer": "CARREFOUR",
        "candidate_source": SOURCE,
        "candidate_urls": len(out_rows),
        "first_party_fields_copied": 0,
        "policy": "URLs are seeds for direct Carrefour verification only. No RadarSuper field may become CARREFOUR_FIRST_PARTY evidence without direct observation on carrefour.es.",
    }
    out.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
