from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import carrefour_first_party_inventory as base

BASE = "https://www.carrefour.es"
SOURCE = "CARREFOUR_FIRST_PARTY"
VERSION = "carrefour-first-party-category-frontier-1.1"
DEFAULT_ROOTS = list(base.DEFAULT_ROOTS)
CATEGORY_RE = re.compile(
    r'(?:href|canonical)\s*=\s*["\']([^"\']*/supermercado/[^"\']+/cat\d+/c(?:\?[^"\']*)?)["\']',
    re.I,
)
ABS_CATEGORY_RE = re.compile(
    r'https?://(?:www\.)?carrefour\.es/supermercado/[^"\'<>\s]+/cat\d+/c(?:\?[^"\'<>\s]*)?',
    re.I,
)
SKU_RE = re.compile(r"/R-([^/]+)/p/?$", re.I)
BLOCK_RE = re.compile(
    r"sorry,? you have been blocked|attention required|cloudflare|access denied|forbidden|captcha|robot|incapsula|akamai",
    re.I,
)
HEADERS = dict(base.HEADERS)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_category_url(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    value = html_lib.unescape(value).replace("\\/", "/").strip()
    if not value:
        return None
    absolute = urljoin(BASE, value)
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"} or parts.netloc.lower() not in {"carrefour.es", "www.carrefour.es"}:
        return None
    path = re.sub(r"/+", "/", parts.path).rstrip("/")
    if not re.fullmatch(r"/supermercado/.+/cat\d+/c", path, re.I):
        return None
    url = urlunsplit(("https", "www.carrefour.es", path, "", ""))
    if base.ALCOHOL_RE.search(url):
        return None
    return url


def category_urls_from_html(raw: str) -> list[str]:
    found: set[str] = set()
    variants = (raw, raw.replace("\\/", "/"))
    for variant in variants:
        for value in CATEGORY_RE.findall(variant):
            url = canonical_category_url(value)
            if url:
                found.add(url)
        for value in ABS_CATEGORY_RE.findall(variant):
            url = canonical_category_url(value)
            if url:
                found.add(url)
    return sorted(found)


def fetch_category_http(url: str, timeout: int, attempts: int) -> tuple[int | None, str, str, str | None, str]:
    last: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            request = Request(url, headers=HEADERS)
            with urlopen(request, timeout=timeout) as response:
                raw_bytes = response.read()
                return response.status, response.geturl(), raw_bytes.decode("utf-8", "replace"), None, "HTTP"
        except Exception as exc:
            last = exc
            if attempt + 1 < max(1, attempts):
                time.sleep(0.6 * (attempt + 1))
    return None, url, "", f"{type(last).__name__}:{last}" if last else "UNKNOWN_FETCH_ERROR", "HTTP"


class BrowserCategoryFetcher:
    def __init__(self, timeout: int):
        from playwright.sync_api import sync_playwright

        self.timeout_ms = max(5, timeout) * 1000
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            locale="es-ES",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
            viewport={"width": 1365, "height": 900},
        )
        self._page = self._context.new_page()

    def fetch(self, url: str) -> tuple[int | None, str, str, str | None, str]:
        try:
            response = self._page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            status = response.status if response else None
            self._page.wait_for_timeout(900)
            final_url = self._page.url
            raw = self._page.content()
            title = self._page.title()
            try:
                text = self._page.locator("body").inner_text(timeout=4000)
            except Exception:
                text = ""
            if status == 403 or BLOCK_RE.search(title + "\n" + text):
                return status, final_url, raw, "BLOCKED:CLOUDFLARE_OR_WAF", "PLAYWRIGHT"
            if status is None or status >= 400:
                return status, final_url, raw, f"HTTP_STATUS:{status}", "PLAYWRIGHT"
            return status, final_url, raw, None, "PLAYWRIGHT"
        except Exception as exc:
            return None, url, "", f"{type(exc).__name__}:{exc}", "PLAYWRIGHT"

    def close(self) -> None:
        try:
            self._page.close()
        finally:
            try:
                self._context.close()
            finally:
                try:
                    self._browser.close()
                finally:
                    self._playwright.stop()


def sku_from_url(url: str) -> str | None:
    match = SKU_RE.search(url.split("?", 1)[0].rstrip("/"))
    return match.group(1) if match else None


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def run(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    roots = []
    for value in args.root or DEFAULT_ROOTS:
        url = canonical_category_url(value)
        if url and url not in roots:
            roots.append(url)

    queue: deque[tuple[str, str | None, int]] = deque((url, None, 0) for url in roots)
    queued = set(roots)
    visited: set[str] = set()
    audit: list[dict] = []
    products: dict[str, dict] = {}
    stop_reason = "frontier_exhausted"
    browser = BrowserCategoryFetcher(args.timeout) if args.browser else None

    try:
        while queue:
            if args.max_categories > 0 and len(visited) >= args.max_categories:
                stop_reason = "max_categories_reached"
                break
            url, parent, depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)
            observed_at = now_iso()
            if browser is not None:
                status, final_url, raw, error, fetch_mode = browser.fetch(url)
            else:
                status, final_url, raw, error, fetch_mode = fetch_category_http(url, args.timeout, args.attempts)
            canonical_final = canonical_category_url(final_url) or url
            children = category_urls_from_html(raw) if raw else []
            product_urls = base.product_urls_from_html(raw) if raw else []

            for product_url in product_urls:
                sku = sku_from_url(product_url)
                if not sku:
                    continue
                candidate = {
                    "retailer": "CARREFOUR",
                    "retailer_sku": sku,
                    "url": product_url,
                    "source": SOURCE,
                    "evidence_type": "OBSERVED_LISTING",
                    "source_url": canonical_final,
                    "observed_at": observed_at,
                    "capture_method": f"CATEGORY_FRONTIER_{fetch_mode}",
                    "provenance_note": "Only the Carrefour product URL/SKU was observed here; no product facts are inferred from category discovery.",
                }
                existing = products.get(sku)
                if existing is None:
                    products[sku] = candidate
                else:
                    sources = existing.setdefault("additional_source_urls", [])
                    if canonical_final != existing.get("source_url") and canonical_final not in sources:
                        sources.append(canonical_final)

            enqueued_children = 0
            if depth < args.max_depth:
                for child in children:
                    if child in visited or child in queued:
                        continue
                    queued.add(child)
                    queue.append((child, canonical_final, depth + 1))
                    enqueued_children += 1

            audit.append(
                {
                    "url": url,
                    "final_url": final_url,
                    "canonical_url": canonical_final,
                    "parent_url": parent,
                    "depth": depth,
                    "source": SOURCE,
                    "observed_at": observed_at,
                    "fetch_mode": fetch_mode,
                    "http_status": status,
                    "fetch_error": error,
                    "html_bytes": len(raw.encode("utf-8")) if raw else 0,
                    "page_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw else None,
                    "child_categories_found": len(children),
                    "child_categories_enqueued": enqueued_children,
                    "product_urls_found": len(product_urls),
                }
            )
            print(json.dumps({"category": canonical_final, "depth": depth, "mode": fetch_mode, "status": status, "children": len(children), "products": len(product_urls), "error": error}, ensure_ascii=False))
            if args.delay > 0 and queue:
                time.sleep(args.delay)
    finally:
        if browser is not None:
            browser.close()

    candidates = [products[key] for key in sorted(products)]
    audit.sort(key=lambda row: (row.get("depth", 0), row.get("canonical_url") or row.get("url") or ""))
    write_jsonl(out / "category_audit.jsonl", audit)
    write_jsonl(out / "product_candidates.jsonl", candidates)

    errors = [row for row in audit if row.get("fetch_error")]
    status_counts: dict[str, int] = {}
    mode_counts: dict[str, int] = {}
    for row in audit:
        key = str(row.get("http_status") if row.get("http_status") is not None else "ERROR")
        status_counts[key] = status_counts.get(key, 0) + 1
        mode = str(row.get("fetch_mode") or "UNKNOWN")
        mode_counts[mode] = mode_counts.get(mode, 0) + 1

    remaining = [url for url, _, _ in queue]
    summary = {
        "retailer": "CARREFOUR",
        "source": SOURCE,
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "extractor_version": VERSION,
        "built_at": now_iso(),
        "classification_performed": False,
        "roots": roots,
        "counts": {
            "categories_visited": len(visited),
            "categories_successful": sum(1 for row in audit if row.get("http_status") and row["http_status"] < 400 and not row.get("fetch_error")),
            "categories_failed": len(errors),
            "categories_discovered_total": len(queued),
            "categories_remaining": len(queue),
            "unique_product_candidates": len(candidates),
        },
        "fetch_mode_counts": mode_counts,
        "http_status_counts": status_counts,
        "stop_reason": stop_reason,
        "max_depth": args.max_depth,
        "max_categories": args.max_categories,
        "frontier_exhausted": not queue,
        "inventory_complete": False,
        "inventory_complete_note": "Category frontier exhaustion does not prove complete Carrefour product inventory because product-list pagination may be dynamic or inaccessible.",
        "remaining_category_sample": remaining[:50],
        "error_sample": errors[:30],
        "product_sample": candidates[:20],
        "provenance_note": "All discovered category and product URLs come only from official carrefour.es supermarket category HTML. No third-party product facts are copied or inferred.",
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="carrefour-first-party-category-frontier")
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--max-categories", type=int, default=220)
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--browser", action="store_true", help="Use a standard Playwright browser session for official category pages.")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
