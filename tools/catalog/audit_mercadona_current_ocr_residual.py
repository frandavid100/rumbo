from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

EXPECTED_PRODUCTS = 4280
VALID_OCR_STATUSES = frozenset({"DECLARED", "REVIEW", "NO_VISUAL_REGION", "ERROR"})
OCR_EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"

# Operational OCR routing only. These are Mercadona first-party top-level grocery
# sections where a nutrition label can be relevant to Rumbo. They do not assign
# CLASSIFIED/MENU_ELIGIBLE or any nutritional/culinary semantic role.
CORE_GROCERY_CATEGORIES = frozenset(
    {
        "Aceite, especias y salsas",
        "Agua y refrescos",
        "Aperitivos",
        "Arroz, legumbres y pasta",
        "Azúcar, caramelos y chocolate",
        "Cacao, café e infusiones",
        "Carne",
        "Cereales y galletas",
        "Charcutería y quesos",
        "Congelados",
        "Conservas, caldos y cremas",
        "Fruta y verdura",
        "Huevos, leche y mantequilla",
        "Marisco y pescado",
        "Panadería y pastelería",
        "Pizzas y platos preparados",
        "Postres y yogures",
        "Zumos",
    }
)
DEFERRED_TOP_LEVEL_CATEGORIES = frozenset({"Bodega"})
EXPLICIT_NON_FOOD_SUBCATEGORIES = frozenset({"Velas y decoración", "Velas"})
ACTIONABLE_SCOPE_PROFILES = frozenset(
    {"ACTIONABLE_P9_FIRST_PARTY_FOOD_SIGNAL", "ACTIONABLE_P9_CORE_GROCERY_CATEGORY"}
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def p9_photo(row: dict[str, Any]) -> dict[str, Any] | None:
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    return next(
        (
            photo
            for photo in photos
            if isinstance(photo, dict)
            and str(photo.get("perspective")) == "9"
            and bool(photo.get("zoom"))
        ),
        None,
    )


def category_path_names(row: dict[str, Any]) -> list[str]:
    path = row.get("category_path") if isinstance(row.get("category_path"), list) else []
    names = [str(item.get("name")) for item in path if isinstance(item, dict) and item.get("name")]
    if names:
        return names
    fallback = row.get("category_names") if isinstance(row.get("category_names"), list) else []
    return [str(value) for value in fallback if value]


def top_level_category(row: dict[str, Any]) -> str:
    names = category_path_names(row)
    return names[0] if names else "UNKNOWN"


def has_food_signal(row: dict[str, Any]) -> bool:
    return bool(row.get("legal_name") or row.get("legal_denomination") or row.get("allergens"))


def has_packaged_signal(row: dict[str, Any]) -> bool:
    return bool(row.get("packaging")) and row.get("unit_size") is not None


def has_explicit_non_food_subcategory(row: dict[str, Any]) -> bool:
    return bool(set(category_path_names(row)[1:]) & EXPLICIT_NON_FOOD_SUBCATEGORIES)


def ocr_scope_profile(row: dict[str, Any]) -> str:
    """Route residuals for OCR work without assigning semantic catalog status.

    The goal is to distinguish genuinely actionable nutrition-label image work from
    residuals that merely have packaging metadata. The latter was a systematic
    false-positive source in the residual census because packaging is also present
    on cosmetics, cleaning products and other non-food products.
    """
    category = top_level_category(row)
    has_p9 = p9_photo(row) is not None
    first_party_food_signal = bool(row.get("ingredients")) or has_food_signal(row)

    if category in DEFERRED_TOP_LEVEL_CATEGORIES:
        return "DEFERRED_BODEGA"
    if has_explicit_non_food_subcategory(row):
        return "OUT_OF_SCOPE_NON_FOOD_SUBCATEGORY"
    if has_p9 and first_party_food_signal:
        return "ACTIONABLE_P9_FIRST_PARTY_FOOD_SIGNAL"
    if has_p9 and category in CORE_GROCERY_CATEGORIES:
        return "ACTIONABLE_P9_CORE_GROCERY_CATEGORY"
    if not has_p9 and (first_party_food_signal or category in CORE_GROCERY_CATEGORIES):
        return "BLOCKED_NO_P9_FOOD_ROUTE"
    return "OUT_OF_SCOPE_NON_FOOD_OR_MIXED"


def iter_ocr_rows(root: Path) -> Iterable[tuple[Path, dict[str, Any]]]:
    for path in sorted(root.rglob("*.jsonl")):
        try:
            rows = load_jsonl(path)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "")
            product_id = str(row.get("product_id") or "")
            if not product_id or status not in VALID_OCR_STATUSES:
                continue
            # Historical OCR artifacts consistently use this evidence marker. Requiring it
            # prevents candidate/audit JSONL files from being mistaken for processed OCR.
            if row.get("evidence_level") != OCR_EVIDENCE:
                continue
            yield path, row


def collect_processed(root: Path) -> tuple[set[str], dict[str, set[str]], Counter[str]]:
    processed: set[str] = set()
    sources: dict[str, set[str]] = defaultdict(set)
    statuses: Counter[str] = Counter()
    seen_status_by_product: dict[str, set[str]] = defaultdict(set)
    for path, row in iter_ocr_rows(root):
        product_id = str(row["product_id"])
        processed.add(product_id)
        sources[product_id].add(str(path))
        seen_status_by_product[product_id].add(str(row["status"]))
    for product_id, product_statuses in seen_status_by_product.items():
        # Status changes can occur in conservative parser replays. For the residual census,
        # only whether a product has already been processed matters; keep a diagnostic count
        # for ambiguous historical status histories instead of picking a canonical status.
        if len(product_statuses) == 1:
            statuses[next(iter(product_statuses))] += 1
        else:
            statuses["MULTIPLE_HISTORICAL_STATUSES"] += 1
    return processed, sources, statuses


def residual_profile(row: dict[str, Any]) -> str:
    if p9_photo(row) is None:
        return "NO_P9"
    if row.get("ingredients"):
        return "P9_STRUCTURED_INGREDIENTS"
    if has_food_signal(row):
        return "P9_NO_INGREDIENTS_FOOD_SIGNAL"
    if has_packaged_signal(row):
        return "P9_NO_INGREDIENTS_PACKAGED_SIGNAL"
    return "P9_NO_INGREDIENTS_OTHER"


def no_p9_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Persist only first-party metadata/URLs needed to assess alternate photos later."""
    return {
        "product_id": str(row.get("product_id") or ""),
        "ean": row.get("ean"),
        "name": row.get("name"),
        "brand": row.get("brand"),
        "top_level_category": top_level_category(row),
        "ocr_scope_profile": ocr_scope_profile(row),
        "has_structured_ingredients": bool(row.get("ingredients")),
        "has_food_signal": has_food_signal(row),
        "has_packaged_signal": has_packaged_signal(row),
        "packaging": row.get("packaging"),
        "unit_size": row.get("unit_size"),
        "photos": row.get("photos") if isinstance(row.get("photos"), list) else [],
        "source": "MERCADONA_FIRST_PARTY/label image candidate",
        "redistribution_allowed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }


def audit(
    products: list[dict[str, Any]],
    processed_ids: set[str],
    expected_processed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(products) != EXPECTED_PRODUCTS:
        raise ValueError(f"expected {EXPECTED_PRODUCTS} first-party products, got {len(products)}")
    product_ids = {str(row.get("product_id") or "") for row in products}
    if "" in product_ids or len(product_ids) != EXPECTED_PRODUCTS:
        raise ValueError("first-party inventory product ids are missing or not unique")
    unknown_processed = sorted(processed_ids - product_ids)
    if unknown_processed:
        raise ValueError(f"processed OCR ids absent from first-party inventory: {unknown_processed[:10]}")
    if len(processed_ids) != expected_processed:
        raise ValueError(f"expected {expected_processed} distinct processed OCR products, reconstructed {len(processed_ids)}")

    residual = [row for row in products if str(row.get("product_id") or "") not in processed_ids]
    profile_counts = Counter(residual_profile(row) for row in residual)
    scope_counts = Counter(ocr_scope_profile(row) for row in residual)
    p9_residual = [row for row in residual if p9_photo(row) is not None]
    no_p9_residual = [row for row in residual if p9_photo(row) is None]
    actionable_p9 = [row for row in residual if ocr_scope_profile(row) in ACTIONABLE_SCOPE_PROFILES]
    blocked_no_p9 = [row for row in residual if ocr_scope_profile(row) == "BLOCKED_NO_P9_FOOD_ROUTE"]
    deferred_bodega = [row for row in residual if ocr_scope_profile(row) == "DEFERRED_BODEGA"]
    out_of_scope = [
        row
        for row in residual
        if ocr_scope_profile(row) in {"OUT_OF_SCOPE_NON_FOOD_SUBCATEGORY", "OUT_OF_SCOPE_NON_FOOD_OR_MIXED"}
    ]
    p9_category_counts = Counter(top_level_category(row) for row in p9_residual)
    no_p9_category_counts = Counter(top_level_category(row) for row in no_p9_residual)
    p9_profile_category_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in p9_residual:
        p9_profile_category_counts[residual_profile(row)][top_level_category(row)] += 1

    rows = []
    for row in sorted(
        p9_residual,
        key=lambda r: (residual_profile(r), top_level_category(r), str(r.get("product_id") or "")),
    ):
        photo = p9_photo(row)
        rows.append(
            {
                "product_id": str(row.get("product_id") or ""),
                "ean": row.get("ean"),
                "name": row.get("name"),
                "brand": row.get("brand"),
                "top_level_category": top_level_category(row),
                "profile": residual_profile(row),
                "ocr_scope_profile": ocr_scope_profile(row),
                "has_structured_ingredients": bool(row.get("ingredients")),
                "has_food_signal": has_food_signal(row),
                "has_packaged_signal": has_packaged_signal(row),
                "packaging": row.get("packaging"),
                "unit_size": row.get("unit_size"),
                "p9_url": (photo or {}).get("zoom"),
                "source": "MERCADONA_FIRST_PARTY/label image",
                "redistribution_allowed": False,
                "CLASSIFIED": 0,
                "MENU_ELIGIBLE": 0,
            }
        )

    no_p9_rows = [
        no_p9_payload(row)
        for row in sorted(
            no_p9_residual,
            key=lambda r: (top_level_category(r), str(r.get("product_id") or "")),
        )
    ]

    summary = {
        "audit_policy_version": "1.2.0",
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": OCR_EVIDENCE,
        "redistribution_allowed": False,
        "inventory_products": len(products),
        "processed_reconstructed": len(processed_ids),
        "processed_pct": round(len(processed_ids) * 100 / len(products), 4),
        "residual_total": len(residual),
        "residual_profiles": dict(sorted(profile_counts.items())),
        "ocr_scope_profile_counts": dict(sorted(scope_counts.items())),
        "ocr_actionable_p9_total": len(actionable_p9),
        "ocr_actionable_p9_product_ids": sorted(str(row.get("product_id") or "") for row in actionable_p9),
        "ocr_blocked_no_p9_food_route_total": len(blocked_no_p9),
        "ocr_blocked_no_p9_food_route_product_ids": sorted(str(row.get("product_id") or "") for row in blocked_no_p9),
        "ocr_deferred_bodega_total": len(deferred_bodega),
        "ocr_deferred_bodega_product_ids": sorted(str(row.get("product_id") or "") for row in deferred_bodega),
        "ocr_out_of_scope_total": len(out_of_scope),
        "p9_residual_total": len(p9_residual),
        "p9_residual_top_level_categories": dict(sorted(p9_category_counts.items())),
        "p9_residual_profile_categories": {
            profile: dict(sorted(counts.items()))
            for profile, counts in sorted(p9_profile_category_counts.items())
        },
        "p9_residual_product_ids": [row["product_id"] for row in rows],
        "no_p9_residual_total": len(no_p9_rows),
        "no_p9_residual_top_level_categories": dict(sorted(no_p9_category_counts.items())),
        "no_p9_residual_product_ids": [row["product_id"] for row in no_p9_rows],
        "policy": (
            "Exact residual census after reconstructing the distinct product-id union from persisted successful OCR artifacts. "
            "Perspective=9 routing profiles and the separate no-p9 census use only first-party metadata. Operational OCR scope "
            "additionally prevents generic packaging metadata on cosmetics/cleaning products from being treated as a nutrition-label "
            "candidate; it uses Mercadona first-party category paths plus direct first-party food signals only and does not assign "
            "CLASSIFIED, MENU_ELIGIBLE, culinary roles or nutritional semantics. Bodega remains explicitly deferred. No OCR is run, "
            "no image is downloaded, and no nutrition is promoted. The no-p9 JSONL persists only first-party photo URLs/metadata so "
            "alternate-perspective label candidates can be audited without retaining image bytes."
        ),
        "images_downloaded": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "structured_api_macros_claimed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
    # Keep this helper output on the summary object only transiently; main removes it
    # before serializing summary.json and writes it as its own auditable JSONL.
    summary["_no_p9_rows"] = no_p9_rows
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", required=True)
    parser.add_argument("--ocr-artifacts", required=True)
    parser.add_argument("--expected-processed", type=int, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    products = load_jsonl(Path(args.products))
    processed_ids, sources, historical_status_counts = collect_processed(Path(args.ocr_artifacts))
    rows, summary = audit(products, processed_ids, args.expected_processed)
    no_p9_rows = summary.pop("_no_p9_rows")
    summary["reconstructed_historical_status_counts"] = dict(sorted(historical_status_counts.items()))
    summary["products_with_multiple_artifact_sources"] = sum(1 for paths in sources.values() if len(paths) > 1)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "residual-p9.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (out / "residual-no-p9.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in no_p9_rows),
        encoding="utf-8",
    )
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
