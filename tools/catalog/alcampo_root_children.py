from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
from dataclasses import asdict
from pathlib import Path

from alcampo_direct_catalog_v6 import allowed_food, merge
from alcampo_direct_catalog_v8 import ApiSession, collect_root as collect_api_root, page_url


def stable_key(p) -> str:
    return f"sku:{p.sku}" if p.sku else f"product:{p.product_id}"


def audit_current_frontier() -> dict:
    """Sweep every canonical direct child through Alcampo's own paginated API.

    This is intentionally anchored to the independently captured root-child snapshot.
    It is a bounded first-party audit: no third-party data, no WAF bypass, and every
    subtree is checked against Alcampo's own current productCount when available.
    """
    fixture = Path("fixtures/alcampo_root_children_latest.json")
    data = json.loads(fixture.read_text(encoding="utf-8"))
    frontier: dict[str, dict] = {}
    for root in data.get("roots") or []:
        root_label = str(root.get("root_label") or root.get("root_retailer_category_id") or "")
        for child in root.get("children") or []:
            rid = str(child.get("retailerCategoryId") or "").strip()
            if not rid:
                continue
            row = {
                "rid": rid,
                "label": str(child.get("name") or rid),
                "root": root_label,
                "expected": int(child.get("productCount") or 0),
            }
            prev = frontier.get(rid)
            if prev is None or row["expected"] > prev["expected"]:
                frontier[rid] = row

    checks: list[dict] = []
    products: dict[str, object] = {}

    def job(row: dict):
        try:
            plist, meta = collect_api_root(row["label"], row["rid"], 0)
            return row, plist, meta, None
        except Exception as exc:
            return row, [], {}, f"{type(exc).__name__}:{exc}"

    # Six workers keeps the sweep fast enough for the 15-minute isolated job while
    # remaining conservative relative to the much more aggressive failed root crawl.
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(job, row) for row in sorted(frontier.values(), key=lambda x: x["rid"])]
        for fut in cf.as_completed(futures):
            row, plist, meta, fatal = fut.result()
            kept = [p for p in plist if allowed_food(p)]
            for p in kept:
                key = stable_key(p)
                products[key] = merge(products[key], p) if key in products else p
            observed = len(plist)
            expected = int(row["expected"] or 0)
            required = max(1, int(expected * 0.95)) if expected else 1
            errors = list(meta.get("errors") or [])
            if fatal:
                errors.append(fatal)
            checks.append({
                **row,
                "pages": int(meta.get("pages") or 0),
                "observed_decorated_products": observed,
                "observed_food_products": len(kept),
                "required_95pct": required,
                "errors": errors,
                "ok": bool(not errors and observed >= required),
            })

    checks.sort(key=lambda x: x["rid"])
    product_rows = [asdict(p) for p in products.values()]
    product_rows.sort(key=lambda p: (str(p.get("sku") or ""), str(p.get("product_id") or "")))
    failures = [c for c in checks if not c["ok"]]
    return {
        "method": "ALCAMPO_FIRST_PARTY_V6_PAGETOKEN_DIRECT_CHILD_FRONTIER_SWEEP",
        "root_snapshot_roots": len(data.get("roots") or []),
        "frontier_subtrees": len(frontier),
        "frontier_subtrees_ok": len(checks) - len(failures),
        "frontier_subtrees_failed": len(failures),
        "failed_rids": [c["rid"] for c in failures],
        "checks": checks,
        "unique_food_products": len(product_rows),
        "identity": "retailer_sku_else_product_id",
        "products": product_rows,
        "complete_against_current_root_snapshot": bool(checks and not failures),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--rid", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    s = ApiSession()
    payload = s.json(page_url(a.rid, None), attempts=20)
    info = payload.get("additionalPageInfo") or {}
    cats = []
    for c in info.get("categories") or []:
        if isinstance(c, dict) and c.get("retailerCategoryId"):
            cats.append({
                "root_label": a.label,
                "root_retailer_category_id": a.rid,
                "name": c.get("name"),
                "categoryId": c.get("categoryId"),
                "retailerCategoryId": c.get("retailerCategoryId"),
                "productCount": c.get("productCount"),
            })
    result = {
        "root_label": a.label,
        "root_retailer_category_id": a.rid,
        "children": cats,
        "child_product_count_sum": sum(int(c.get("productCount") or 0) for c in cats),
    }

    # The Alimentación matrix cell acts as a single audit coordinator. The other
    # root cells remain lightweight discovery jobs and therefore do not multiply
    # the complete frontier sweep tenfold.
    if a.rid == "OCC10" and Path("fixtures/alcampo_root_children_latest.json").exists():
        result["frontier_api_audit"] = audit_current_frontier()

    (a.out / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    printable = dict(result)
    if "frontier_api_audit" in printable:
        audit = dict(printable["frontier_api_audit"])
        audit["products"] = f"<{len(audit.get('products') or [])} product rows persisted in summary.json>"
        printable["frontier_api_audit"] = audit
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0 if cats else 2


if __name__ == "__main__":
    raise SystemExit(main())
