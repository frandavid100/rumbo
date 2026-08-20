from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from playwright.async_api import async_playwright

from alcampo_detail_enricher import BASE, UA, Detail, candidate_urls, parse_fields
from nutrition_validation import validate_nutrition

VERSION = "alcampo-detail-browser-v1.2"


def load_targets(path: Path, offset: int, limit: int) -> list[tuple[str, str | None]]:
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
    rows = rows[max(0, offset):]
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


def ordered_urls(sku: str, name: str | None) -> list[str]:
    # /products/x/SKU is retailer-stable and Alcampo redirects it to the current
    # canonical slug. Prefer it over guessing the slug from a catalogue name.
    x = f"{BASE}/products/x/{sku}"
    return list(dict.fromkeys([x, *candidate_urls(sku, name)]))


async def fetch_one(context, sku: str, name: str | None) -> Detail:
    page = await context.new_page()
    urls = ordered_urls(sku, name)
    last_error = None
    last_url = urls[-1]
    try:
        for url in urls:
            last_url = url
            for attempt in range(3):
                try:
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=35000)
                    status = response.status if response else None
                    body = await page.content()
                    if status == 202:
                        last_error = "PENDING_202"
                        await asyncio.sleep(1.5 + attempt * 2)
                        continue
                    if status in (404, 410):
                        break
                    if status is not None and status >= 400:
                        last_error = f"HTTP_{status}"
                        await asyncio.sleep(1.5 + attempt)
                        continue
                    return parsed_detail(sku, url, page.url, status, body)
                except Exception as exc:
                    last_error = f"{type(exc).__name__}:{exc}"
                    await asyncio.sleep(1.5 + attempt)
        return Detail(sku, last_url, None, None, None, None, None, None, None, None, None, None, None, None, None, "FETCH_ERROR", last_error, 0)
    finally:
        await page.close()


async def run(targets: list[tuple[str, str | None]], out: Path, concurrency: int, offset: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    details: list[Detail] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Alcampo's edge/WAF serves the real PDP to this ordinary Chrome UA while
        # the Playwright HeadlessChrome default is rejected with 403.
        context = await browser.new_context(
            locale="es-ES",
            timezone_id="Europe/Madrid",
            user_agent=UA,
            viewport={"width": 1280, "height": 720},
            extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
        )
        sem = asyncio.Semaphore(max(1, concurrency))

        async def worker(target):
            async with sem:
                return await fetch_one(context, target[0], target[1])

        tasks = [asyncio.create_task(worker(t)) for t in targets]
        path = out / "details.jsonl"
        # Stream each completed product immediately so an interrupted shard remains
        # salvageable by GitHub Actions' always() artifact step.
        with path.open("w", encoding="utf-8", buffering=1) as f:
            for n, task in enumerate(asyncio.as_completed(tasks), 1):
                try:
                    d = await task
                except Exception as exc:
                    d = Detail("UNKNOWN", "", None, None, None, None, None, None, None, None, None, None, None, None, None, "FETCH_ERROR", f"WORKER:{type(exc).__name__}:{exc}", 0)
                details.append(d)
                f.write(json.dumps(asdict(d), ensure_ascii=False) + "\n")
                if n % 10 == 0 or n == len(targets):
                    valid = sum(x.nutrition_status == "DECLARED_VALID" for x in details)
                    fetched = sum(x.error is None for x in details)
                    print(f"checkpoint={n}/{len(targets)} offset={offset} fetched={fetched} valid={valid}", flush=True)

        await context.close()
        await browser.close()

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
    summary = {"source": BASE, "version": VERSION, "offset": offset, "concurrency": concurrency, "counts": counts}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("--concurrency", type=int, default=2)
    p.add_argument("--min-fetched", type=int, default=0)
    p.add_argument("--min-valid", type=int, default=1)
    a = p.parse_args()
    targets = load_targets(a.input, a.offset, a.limit)
    summary = asyncio.run(run(targets, a.out, a.concurrency, a.offset))
    c = summary["counts"]
    return 0 if c["fetched"] >= a.min_fetched and c["declared_valid_nutrition"] >= a.min_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
