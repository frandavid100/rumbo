from __future__ import annotations

import io
import json
import os
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from aesan_2022_match_probe import Match, _float, _load_persisted_resolved_ids, _name_similarity, _same_brand, digits, norm
from mercadona_weekly_catalog_adapter import deterministic_candidate_ids, fetch_product_ids, stratified_sample
from pilot_large_catalog import _fetch_candidate_products, _is_food_category

SEED = "rumbo-mercadona-pilot-2026-08"
SAMPLE_SIZE = 300
CANDIDATE_POOL = 900


def fetch_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "RumboCatalogProbe/1.0"})
    with urlopen(req, timeout=90) as response:
        return response.read()


def main() -> int:
    url = os.environ["AESAN_2022_EXCEL_URL"]
    out = Path(os.environ.get("AESAN_PROBE_OUTPUT_DIR", "aesan-2022-fast-probe-output"))
    out.mkdir(parents=True, exist_ok=True)

    data = fetch_bytes(url)
    df = pd.read_excel(io.BytesIO(data), sheet_name="DATOS", header=1)
    cols = {
        "gtin": "EAN",
        "name": "Nombre comercial",
        "brand": "Marca",
        "kcal": "Energía \n(kCal/ 100g ó 100 ml)",
        "fat": "Grasa total \n(g/ 100 g ó 100 ml)",
        "carb": "Hidratos de carbono \n(g/ 100g ó 100 ml)",
        "protein": "Proteínas \n(g/100 g ó 100 ml)",
    }
    missing_cols = [v for v in cols.values() if v not in df.columns]
    if missing_cols:
        raise RuntimeError(f"AESAN DATOS schema changed; missing {missing_cols}; columns={list(df.columns)}")

    hist = []
    by_gtin: dict[str, list[dict]] = defaultdict(list)
    by_brand: dict[str, list[dict]] = defaultdict(list)
    for idx, row in df.iterrows():
        nutrition = {
            "kcal_100": _float(row.get(cols["kcal"])),
            "fat_100": _float(row.get(cols["fat"])),
            "carb_100": _float(row.get(cols["carb"])),
            "protein_100": _float(row.get(cols["protein"])),
        }
        if any(v is None for v in nutrition.values()):
            continue
        h = {
            "index": int(idx),
            "name": str(row.get(cols["name"]) or ""),
            "brand": str(row.get(cols["brand"]) or ""),
            "gtin": digits(row.get(cols["gtin"])),
            "nutrition": nutrition,
        }
        if not norm(h["name"]):
            continue
        hist.append(h)
        if len(h["gtin"]) >= 8:
            by_gtin[h["gtin"]].append(h)
        nb = norm(h["brand"])
        if nb:
            by_brand[nb].append(h)

    ids = fetch_product_ids()
    candidates = deterministic_candidate_ids(ids, seed=SEED, limit=CANDIDATE_POOL)
    products, errors = _fetch_candidate_products(candidates, 16)
    food = [p for p in products if _is_food_category(p.category_key)]
    sample = stratified_sample(food, size=SAMPLE_SIZE, per_category_cap=24)
    resolved = _load_persisted_resolved_ids()
    pending = [p for p in sample if str(p.product_id) not in resolved]

    accepted: list[Match] = []
    review: list[dict] = []
    for p in pending:
        pgtin = digits(p.ean)
        exact = by_gtin.get(pgtin, []) if len(pgtin) >= 8 else []
        if exact:
            h = exact[0]
            accepted.append(Match(str(p.product_id), p.name, p.brand, p.ean, h["name"], h["brand"], h["gtin"], 1.0, "EXACT_GTIN", h["nutrition"]))
            continue

        pbrand = norm(p.brand)
        candidates_h = list(by_brand.get(pbrand, [])) if pbrand else []
        # Conservative fallback for variants such as "Hacendado / Mercadona".
        if not candidates_h and pbrand:
            candidates_h = [h for h in hist if _same_brand(p.brand, h["brand"])]
        scored = []
        for h in candidates_h:
            sim = _name_similarity(p.name, h["name"])
            if sim >= 0.78:
                scored.append((sim, h))
        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            continue
        score, h = scored[0]
        margin = score - scored[1][0] if len(scored) > 1 else score
        payload = Match(str(p.product_id), p.name, p.brand, p.ean, h["name"], h["brand"], h["gtin"], round(score, 4), "HIGH_BRAND_NAME" if score >= 0.92 else "REVIEW_BRAND_NAME", h["nutrition"])
        if score >= 0.92 and margin >= 0.04:
            accepted.append(payload)
        else:
            review.append({**asdict(payload), "runner_up_margin": round(margin, 4)})

    counts = defaultdict(int)
    for m in accepted:
        counts[m.match_class] += 1
    report = {
        "probe_version": "1.1.0-indexed",
        "source": "AESAN products marketed in Spain, observations collected in 2022",
        "source_freshness_warning": "Historical only: AESAN states products may have changed after 2022",
        "excel_url": url,
        "aesan_rows_total": len(df),
        "aesan_rows_with_core_nutrition": len(hist),
        "sample_size": len(sample),
        "already_resolved": len(resolved & {str(p.product_id) for p in sample}),
        "pending_checked": len(pending),
        "high_confidence_historical_matches": len(accepted),
        "high_confidence_rate_of_pending": round(len(accepted) / len(pending), 4) if pending else 0,
        "high_confidence_classes": dict(counts),
        "review_candidates": len(review),
        "matches": [asdict(x) for x in accepted],
        "review": review,
        "acquisition_error_count": len(errors),
        "policy": "Probe only. Historical AESAN matches are not promoted automatically to current evidence.",
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "high-confidence-matches.json").write_text(json.dumps([asdict(x) for x in accepted], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("matches", "review")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
