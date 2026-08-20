from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import threading
from dataclasses import asdict
from pathlib import Path
from urllib.error import HTTPError, URLError

import alcampo_detail_enricher as base
from nutrition_validation import validate_nutrition

VERSION = "alcampo-detail-fast-wave-v1"
_TLS = threading.local()


def opener(reset: bool = False):
    if reset or not getattr(_TLS, "opener", None):
        _TLS.opener = base._new_opener()
        # Priming is useful when it works but must never turn a fast wave into a
        # long retry loop. One first-party category request per fresh session only.
        try:
            base._prime(_TLS.opener)
        except Exception:
            pass
    return _TLS.opener


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


def fetch_fast(sku: str, name_hint: str | None):
    urls = base.candidate_urls(str(sku), name_hint)
    last = None
    last_url = urls[-1]
    op = opener()
    # Exactly one request per candidate URL. If the WAF returns 202, reset the
    # cookie jar before the stable /products/x/<sku> fallback rather than burning
    # minutes polling the same pending session.
    for idx, url in enumerate(urls):
        last_url = url
        try:
            status, final, raw, body = base._request(op, url, base.BASE + "/")
            if status == 202 or ("window.gokuProps" in body and len(body) < 10000):
                last = f"WAF_PENDING_{status}"
                if idx < len(urls) - 1:
                    op = opener(reset=True)
                continue
            return parse_success(str(sku), url, status, final, raw, body)
        except HTTPError as exc:
            try:
                preview = exc.read().decode("utf-8", errors="replace")[:160]
            except Exception:
                preview = ""
            last = f"HTTP_{exc.code}:{preview}"
            if idx < len(urls) - 1:
                op = opener(reset=True)
                continue
        except (URLError, TimeoutError) as exc:
            last = f"{type(exc).__name__}:{exc}"
            if idx < len(urls) - 1:
                op = opener(reset=True)
        except Exception as exc:
            last = f"{type(exc).__name__}:{exc}"
            if idx < len(urls) - 1:
                op = opener(reset=True)
    return base.Detail(
        str(sku), last_url, None, None, None, None, None, None,
        None, None, None, None, None, None, None, "FETCH_ERROR", last, 0
    )


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
        out.append((str(sku), str(row.get("name") or "").strip() or None))
    return out


def summarize(details, requested: int):
    return {
        "source": base.BASE,
        "version": VERSION,
        "counts": {
            "requested": requested,
            "completed_rows": len(details),
            "fetched": sum(d.error is None for d in details),
            "errors": sum(d.error is not None for d in details),
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
        "policy": "ONE_REQUEST_PER_CANONICAL_CANDIDATE_FRESH_SESSION_ON_PENDING_CHECKPOINT_EACH_RESULT",
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
            futures = {ex.submit(fetch_fast, sku, name): sku for sku, name in targets}
            for n, fut in enumerate(cf.as_completed(futures), 1):
                sku = futures[fut]
                try:
                    detail = fut.result()
                except Exception as exc:
                    detail = base.Detail(
                        str(sku), f"{base.BASE}/products/x/{sku}", None, None, None, None, None, None,
                        None, None, None, None, None, None, None, "FETCH_ERROR", f"WORKER:{type(exc).__name__}:{exc}", 0
                    )
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
    summary = summarize(details, len(targets))
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
