from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from playwright.async_api import async_playwright

from alcampo_detail_enricher import BASE, Detail, candidate_urls, parse_fields
from nutrition_validation import validate_nutrition

VERSION = "alcampo-detail-browser-v1.0"


def load_targets(path: Path, limit: int) -> list[tuple[str, str | None]]:
    rows = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sku = row.get("sku") or row.get("retailer_sku")
        if sku is None:
            continue
        sku = str(sku)
        if sku in seen:
            continue
        seen.add(sku)
        rows.append((sku, str(row.get("name") or "").strip() or None))
    return rows[:limit] if limit else rows


def parsed_detail(sku: str, requested: str, final: str, status: int | None, body: str) -> Detail:
    _, name, gtin, legal, ingredients, nt = parse_fields(body)
    if all(nt[k] is not None for k in ("calories", "protein_g", "carbohydrate_g", "fat_g")):
        vr = validate_nutrition(nt["calories"], nt["protein_g"], nt["carbohydrate_g"], nt["fat_g"], nt["fiber_g"], nt["salt_g"])
        nutrition_status = "DECLARED_VALID" if vr.valid else "DECLARED_INVALID:" + ",".join(vr.reasons)
    else:
        nutrition_status = "DECLARED_INCOMPLETE"
    return Detail(
        sku, requested, final, status, name, gtin, legal, ingredients,
        nt["calories"], nt["protein_g"], nt["carbohydrate_g"], nt["fat_g"],
        nt["fiber_g"], nt["salt_g"], nt.get("basis"), nutrition_status, None,
        len(body.encode("utf-8", errors="replace")),
    )


async def fetch_one(context, sku: str, name: str | None) -> Detail:
    page = await context.new_page()
    last_error = None
    last_url = candidate_urls(sku, name)[-1]
    try:
        for url in candidate_urls(sku, name):
            last_url = url
            for attempt in range(4):
                try:
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    status = response.status if response else None
                    body = await page.content()
                    if status == 202:
                        last_error = "PENDING_202"
                        await asyncio.sleep(2 + attempt * 2)
                        continue
                    if status in (404, 410):
                        break
                    if status is not None and status >= 400:
                        last_error = f"HTTP_{status}"
                        await asyncio.sleep(2 + attempt)
                        continue
                    return parsed_detail(sku, url, page.url, status, body)
                except Exception as exc:
                    last_error = f"{type(exc).__name__}:{exc}"
                    await asyncio.sleep(2 + attempt)
        return Detail(sku, last_url, None, None, None, None, None, None, None, None, None, None, None, None, None, "FETCH_ERROR", last_error, 0)
    finally:
        await page.close()


async def run(targets: list[tuple[str, str | None]], out: Path, concurrency: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="es-ES", timezone_id="Europe/Madrid")
        sem = asyncio.Semaphore(max(1, concurrency))
        results: list[Detail | None] = [None] * len(targets)

        async def worker(i, target):
            async with sem:
                results[i] = await fetch_one(context, target[0], target[1])
                d = results[i]
                print(f"{i+1}/{len(targets)} sku={target[0]} nutrition={d.nutrition_status} error={d.error}", flush=True)

        await asyncio.gather(*(worker(i, t) for i, t in enumerate(targets)))
        await context.close()
        await browser.close()

    details = [d for d in results if d is not None]
    with (out / "details.jsonl").open("w", encoding="utf-8") as f:
        for d in details:
            f.write(json.dumps(asdict(d), ensure_ascii=False) + "\n")
    counts = {
        "requested": len(targets),
        "fetched": sum(d.error is None for d in details),
        "errors": sum(d.error is not None for d in details),
        "with_gtin": sum(bool(d.gtin) for d in details),
        "with_legal_name": sum(bool(d.legal_name) for d in details),
        "with_ingredients": sum(bool(d.ingredients) for d in details),
        "declared_valid_nutrition": sum(d.nutrition_status == "DECLARED_VALID" for d in details),
        "declared_incomplete_nutrition": sum(d.nutrition_status == "DECLARED_INCOMPLETE" for d in details),
        "declared_invalid_nutrition": sum(d.nutrition_status.startswith("DECLARED_INVALID") for d in details),
    }
    summary = {"source": BASE, "version": VERSION, "concurrency": concurrency, "counts": counts}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("--concurrency", type=int, default=2)
    p.add_argument("--min-valid", type=int, default=1)
    a = p.parse_args()
    summary = asyncio.run(run(load_targets(a.input, a.limit), a.out, a.concurrency))
    return 0 if summary["counts"]["declared_valid_nutrition"] >= a.min_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
