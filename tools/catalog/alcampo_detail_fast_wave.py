from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import threading
import time
import urllib.parse
from dataclasses import asdict
from pathlib import Path
from urllib.error import HTTPError, URLError

import alcampo_detail_enricher as base
from nutrition_validation import validate_nutrition

VERSION = "alcampo-detail-fast-wave-v1.5"
_TLS = threading.local()


def opener(reset: bool = False):
    if reset or not getattr(_TLS, "opener", None):
        # Keep one cookie jar per worker but avoid category priming: the verified
        # server-rendered product URL already contains the declared detail fields.
        _TLS.opener = base._new_opener()
    return _TLS.opener


def pace_requests(min_interval: float = 1.25):
    """Avoid bursting Alcampo PDP requests from one runner.

    Empirically, the first-party SSR route yields several real product pages and
    then starts returning transient 202 responses when requests are sent in a
    tight burst. A small per-runner interval is both gentler and more useful than
    retrying the same transient response immediately.
    """
    now = time.monotonic()
    last = getattr(_TLS, "last_request_at", None)
    if last is not None:
        wait = min_interval - (now - last)
        if wait > 0:
            time.sleep(wait)
    _TLS.last_request_at = time.monotonic()


def parse_success(sku: str, requested_url: str, status: int, final: str, raw: bytes, body: str):
    _, name, gtin, legal, ingredients, nt = base.parse_fields(body)
    if all(nt[k] is not None for k in ("calories", "protein_g", "carbohydrate_g", "fat_g")):
        vr = validate_nutrition(
            nt["calories"], nt["protein_g"], nt["carbohydrate_g"], nt["fat_g"], nt["fiber_g"], nt["salt_g"]
        )
        nutrition_status = "DECLARED_VALID" if vr.valid else "DECLARED_INVALID:" + ",".join(vr.reasons)
    else:
        nutrition_status = "DECLARED_INCOMPLETE"
    return base.Detail(
        str(sku), requested_url, final, status, name, gtin, legal, ingredients,
        nt["calories"], nt["protein_g"], nt["carbohydrate_g"], nt["fat_g"],
        nt["fiber_g"], nt["salt_g"], nt.get("basis"), nutrition_status, None, len(raw)
    )


def stable_url(sku: str) -> str:
    return f"{base.BASE}/products/x/{urllib.parse.quote(str(sku), safe='')}"


def normalize_exact_url(value: str | None) -> str | None:
    """Accept only first-party Alcampo product URLs already observed in the listing."""
    if not value:
        return None
    url = urllib.parse.urljoin(base.BASE + "/", str(value).strip())
    parsed = urllib.parse.urlparse(url)
    base_parsed = urllib.parse.urlparse(base.BASE)
    if parsed.netloc != base_parsed.netloc or "/products/" not in parsed.path:
        return None
    return url.split("#", 1)[0]


def failure(sku: str, url: str, error: str):
    return base.Detail(
        str(sku), url, None, None, None, None, None, None,
        None, None, None, None, None, None, None, "FETCH_ERROR", error, 0
    )


def fetch_fast(sku: str, name_hint: str | None, exact_url: str | None = None):
    # Once this runner has seen two consecutive first-party 202 responses, all
    # subsequent requests from the same worker have empirically been 202 as well.
    # Do not keep hammering Alcampo for another ~40 SKUs. Mark them as a transient
    # circuit skip so the next fresh runner/wave can retry them safely.
    if getattr(_TLS, "waf_circuit_open", False):
        return failure(str(sku), normalize_exact_url(exact_url) or stable_url(str(sku)), "WAF_PENDING_CIRCUIT_OPEN")

    # Highest-confidence route: use the canonical product URL actually observed in
    # Alcampo's own category/listing HTML. The previous wave discarded that field
    # and reconstructed a slug from the name, which needlessly turned valid products
    # into 202/404 misses when the retailer's slug did not match our transliteration.
    # Keep /products/x/<sku> only as a fallback for a stale/incorrect slug. A 202 is
    # treated as a transient WAF/rate response and is not immediately retried via a
    # second route, which only doubles pressure without adding first-party evidence.
    urls = []
    exact = normalize_exact_url(exact_url)
    if exact:
        urls.append(exact)
    else:
        for u in base.candidate_urls(str(sku), name_hint):
            if "/products/x/" not in u and u not in urls:
                urls.append(u)
                break
    x = stable_url(str(sku))
    if x not in urls:
        urls.append(x)
    urls = urls[:2]
    last = None
    last_url = urls[-1]
    op = opener()
    for idx, url in enumerate(urls):
        last_url = url
        try:
            pace_requests()
            status, final, raw, body = base._request(op, url, base.BASE + "/")
            if status == 202 or ("window.gokuProps" in body and len(body) < 10000):
                streak = int(getattr(_TLS, "waf_pending_streak", 0)) + 1
                _TLS.waf_pending_streak = streak
                if streak >= 2:
                    _TLS.waf_circuit_open = True
                last = f"WAF_PENDING_{status}"
                return failure(str(sku), url, last)
            _TLS.waf_pending_streak = 0
            return parse_success(str(sku), url, status, final, raw, body)
        except HTTPError as exc:
            _TLS.waf_pending_streak = 0
            try:
                preview = exc.read().decode("utf-8", errors="replace")[:160]
            except Exception:
                preview = ""
            last = f"HTTP_{exc.code}:{preview}"
            # Only a concrete missing/stale slug justifies trying /products/x/<sku>.
            if exc.code in (404, 410) and idx < len(urls) - 1:
                op = opener(reset=True)
                continue
            return failure(str(sku), url, last)
        except (URLError, TimeoutError) as exc:
            _TLS.waf_pending_streak = 0
            last = f"{type(exc).__name__}:{exc}"
            if idx < len(urls) - 1:
                op = opener(reset=True)
                continue
        except Exception as exc:
            _TLS.waf_pending_streak = 0
            last = f"{type(exc).__name__}:{exc}"
            if idx < len(urls) - 1:
                op = opener(reset=True)
                continue
    return failure(str(sku), last_url, last or "FETCH_ERROR")


def load_targets(path: Path):
    out = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sku = row.get("sku") or row.get("retailer_sku")
        if sku is None or str(sku) in seen:
            continue
        seen.add(str(sku))
        name = str(row.get("name") or "").strip() or None
        exact_url = row.get("url") or row.get("product_url") or row.get("canonical_url")
        out.append((str(sku), name, normalize_exact_url(str(exact_url)) if exact_url else None))
    return out


def summarize(details, requested: int, targets):
    exact_url_targets = sum(bool(t[2]) for t in targets)
    return {
        "source": base.BASE,
        "version": VERSION,
        "counts": {
            "requested": requested,
            "targets_with_observed_product_url": exact_url_targets,
            "completed_rows": len(details),
            "fetched": sum(d.error is None for d in details),
            "errors": sum(d.error is not None for d in details),
            "circuit_skips": sum("CIRCUIT_OPEN" in str(d.error or "") for d in details),
            "with_name": sum(bool(d.name) for d in details),
            "with_gtin": sum(bool(d.gtin) for d in details),
            "with_legal_name": sum(bool(d.legal_name) for d in details),
            "with_ingredients": sum(bool(d.ingredients) for d in details),
            "with_nutrition_basis": sum(bool(d.nutrition_basis) for d in details),
            "declared_valid_nutrition": sum(d.nutrition_status == "DECLARED_VALID" for d in details),
            "declared_incomplete_nutrition": sum(d.nutrition_status == "DECLARED_INCOMPLETE" for d in details),
            "declared_invalid_nutrition": sum(d.nutrition_status.startswith("DECLARED_INVALID") for d in details),
            "downloaded_html_bytes": sum(d.html_bytes for d in details),
        },
        "policy": "FIRST_PARTY_PRODUCT_SLUG_PACED_STOP_AFTER_TWO_CONSECUTIVE_202_X_ONLY_FOR_MISSING_SLUG_CHECKPOINT_EACH_RESULT",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    targets = load_targets(args.input)
    details = []
    path = args.out / "details.jsonl"
    # Create the file before network work starts, so GitHub's always() artifact
    # step can salvage completed rows even if a runner is cancelled or times out.
    with path.open("w", encoding="utf-8", buffering=1) as fh:
        with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futures = {ex.submit(fetch_fast, sku, name, exact_url): sku for sku, name, exact_url in targets}
            for n, fut in enumerate(cf.as_completed(futures), 1):
                sku = futures[fut]
                try:
                    detail = fut.result()
                except Exception as exc:
                    detail = failure(str(sku), stable_url(str(sku)), f"WORKER:{type(exc).__name__}:{exc}")
                details.append(detail)
                fh.write(json.dumps(asdict(detail), ensure_ascii=False) + "\n")
                if n % 10 == 0:
                    fh.flush()
                    try:
                        os.fsync(fh.fileno())
                    except OSError:
                        pass
                    valid = sum(d.nutrition_status == "DECLARED_VALID" for d in details)
                    print(f"checkpoint={n}/{len(targets)} valid={valid}", flush=True)
    summary = summarize(details, len(targets), targets)
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
