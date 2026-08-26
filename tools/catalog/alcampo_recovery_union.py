from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

from alcampo_direct_catalog_v6 import Product, merge, write_outputs

# Identity-only rows recovered from broad SSR nodes do not carry the structured
# alcohol flag that decorated products have. Fail closed for obvious alcoholic
# beverages while retaining 0.0/sin-alcohol products and foods whose names happen
# to mention an alcoholic ingredient (for example chocolate relleno de cognac).
ALCOHOLIC_BEVERAGE_URL = re.compile(
    r"/products/[^/]*(?:cerveza|cervezas|vino|vinos|whisky|whiskey|ron|ginebra|vodka|brandy|licor|licores|champagne|cava|sidra|vermut|vermouth|sangria)",
    re.I,
)
ZERO_ALCOHOL_URL = re.compile(r"(?:sin[-_ ]+alcohol|0[-.,]0[-_ ]*alcohol)", re.I)


def stable_key(p: Product) -> str:
    return f"sku:{p.sku}" if p.sku else f"product:{p.product_id}"


def load_manifest(path: Path, products: dict[str, Product]) -> tuple[int, int]:
    rows = 0
    before = len(products)
    if not path.exists():
        return rows, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        p = Product(**row)
        rows += 1
        key = stable_key(p)
        products[key] = merge(products[key], p) if key in products else p
    return rows, len(products) - before


def recovery_product_allowed(p: Product) -> bool:
    if p.alcohol is True:
        return False
    category = " ".join(p.category_path or [])
    url = p.product_url or ""
    # Only infer from the URL when the weak identity row came from the broad
    # first-party "Bebidas" node. This avoids excluding foods such as bonbons
    # or sauces that legitimately contain wine/cognac in their commercial name.
    if re.search(r"\bbebidas?\b", category, re.I) and ALCOHOLIC_BEVERAGE_URL.search(url):
        return bool(ZERO_ALCOHOL_URL.search(url))
    return True


def load_recovery_manifest(path: Path, products: dict[str, Product]) -> tuple[int, int, list[str]]:
    rows = 0
    before = len(products)
    excluded: list[str] = []
    if not path.exists():
        return rows, 0, excluded
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = Product(**json.loads(line))
        rows += 1
        if not recovery_product_allowed(p):
            excluded.append(str(p.sku or p.product_id))
            continue
        key = stable_key(p)
        products[key] = merge(products[key], p) if key in products else p
    return rows, len(products) - before, excluded


def read_checks(root: Path) -> list[dict]:
    out = []
    if not root.exists():
        return out
    for path in sorted(root.rglob("child_check.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        row["artifact_path"] = str(path)
        out.append(row)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline-products", type=Path, required=True)
    p.add_argument("--recursive-products", type=Path)
    p.add_argument("--recovery-root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()

    products: dict[str, Product] = {}
    baseline_rows, _ = load_manifest(a.baseline_products, products)
    baseline_unique = len(products)

    recursive_rows = recursive_added = 0
    if a.recursive_products and a.recursive_products.exists():
        recursive_rows, recursive_added = load_manifest(a.recursive_products, products)

    recovery_files = sorted(Path(x) for x in glob.glob(str(a.recovery_root / "**/products.jsonl"), recursive=True))
    recovery_rows = 0
    recovery_added = 0
    recovery_excluded_nonfood: set[str] = set()
    for path in recovery_files:
        rows, added, excluded = load_recovery_manifest(path, products)
        recovery_rows += rows
        recovery_added += added
        recovery_excluded_nonfood.update(excluded)

    checks = read_checks(a.recovery_root)
    union_skus = {str(p.sku) for p in products.values() if p.sku}
    audited_checks = []
    unresolved = []
    decoration_failed = 0
    visible_skus_total = set()
    visible_skus_missing = set()

    for original in checks:
        c = dict(original)
        visible = {str(x) for x in (c.get("html_link_skus") or []) if str(x).strip()}
        # Excluded alcoholic beverages are deliberately outside the food-union
        # completeness claim; do not report them as missing food products.
        visible_food = visible - recovery_excluded_nonfood
        visible_skus_total.update(visible_food)
        missing = sorted(visible_food - union_skus)
        visible_skus_missing.update(missing)
        enum_ok = bool(c.get("enumeration_ok", c.get("ok")))
        coverage_ok = not missing
        c["html_visible_skus"] = len(visible)
        c["html_visible_food_skus"] = len(visible_food)
        c["html_visible_skus_excluded_nonfood"] = sorted(visible & recovery_excluded_nonfood)
        c["html_visible_skus_present_in_union"] = len(visible_food) - len(missing)
        c["html_visible_skus_missing_from_union"] = missing
        c["union_coverage_ok"] = coverage_ok
        c["recovery_enumeration_ok"] = enum_ok and coverage_ok
        if not c.get("decoration_ok", False):
            decoration_failed += 1
        if not c["recovery_enumeration_ok"]:
            unresolved.append(c)
        audited_checks.append(c)

    # Decoration failures are deliberately separate from enumeration failures. The
    # former affect rich fields/nutrition; the latter affect whether we know the
    # retailer listing set. A WAF-blocked /products PUT cannot invalidate product
    # links that Alcampo itself rendered in a 200 category page.
    api_error_categories = sum(int(c.get("api_error_categories") or 0) for c in audited_checks if not c.get("recovery_enumeration_ok"))
    missing_ids = sum(int(c.get("children_without_retailer_category_id") or 0) for c in audited_checks)

    summary = write_outputs(a.out, list(products.values()), audited_checks)
    recovery_targets_exhausted = bool(checks) and not unresolved
    report = {
        "baseline_manifest": str(a.baseline_products),
        "baseline_rows": baseline_rows,
        "baseline_unique": baseline_unique,
        "recursive_manifest": str(a.recursive_products) if a.recursive_products else None,
        "recursive_rows": recursive_rows,
        "recursive_new_unique_vs_baseline": recursive_added,
        "recovery_product_artifacts": len(recovery_files),
        "recovery_rows": recovery_rows,
        "recovery_new_unique": recovery_added,
        "recovery_excluded_nonfood_count": len(recovery_excluded_nonfood),
        "recovery_excluded_nonfood_skus": sorted(recovery_excluded_nonfood),
        "recovery_checks": len(checks),
        "recovery_checks_failed": len(unresolved),
        "recovery_decoration_failed": decoration_failed,
        "recovery_api_error_categories": api_error_categories,
        "recovery_children_without_retailer_id": missing_ids,
        "html_visible_unique_food_skus_audited": len(visible_skus_total),
        "html_visible_unique_skus_missing_from_union": len(visible_skus_missing),
        "missing_visible_skus": sorted(visible_skus_missing),
        "unique_food_products_union": summary["counts"]["food_products"],
        "net_new_unique_vs_13877_baseline": max(0, summary["counts"]["food_products"] - baseline_unique),
        "identity": "retailer_sku_else_product_id",
        "recovery_targets_enumerated_and_covered": recovery_targets_exhausted,
        "completeness_claim": (
            "RECOVERY_TARGETS_ENUMERATED_AND_VISIBLE_SKUS_COVERED; GLOBAL_COMPLETENESS_STILL_REQUIRES_FULL_TREE_AUDIT"
            if recovery_targets_exhausted
            else "RECOVERY_UNION_NOT_PROVEN_COMPLETE"
        ),
        "failed_recovery_targets": unresolved,
    }
    (a.out / "recovery_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if recovery_targets_exhausted else 2


if __name__ == "__main__":
    raise SystemExit(main())
