from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Callable
from urllib.request import Request, urlopen

DATASET_ROOT = "https://huggingface.co/datasets/manurruis/mercadona-catalog/resolve/main"
USER_AGENT = "RumboCatalog/0.1 (evaluation pilot; contact: frandavid100@users.noreply.github.com)"
ADAPTER_VERSION = "1.1.0"

# Merchandise can appear inside otherwise-food categories (the pilot found
# birthday candles under bakery/pastry). Keep this an explicit conservative
# exclusion list: unknown products remain discoverable elsewhere; they simply
# must not enter a food-classification sample as if they were edible.
NON_FOOD_NAME_PATTERNS = (
    r"\bvela(?:s)? de cumpleanos?\b",
    r"\bvela(?:s)? numero\b",
    r"\bbengala(?:s)? de cumpleanos?\b",
)


@dataclass(frozen=True)
class WeeklyCatalogProduct:
    product_id: str
    ean: str | None
    name: str
    brand: str | None
    legal_name: str | None
    ingredients: str | None
    family: str | None
    subcategory: str | None
    category_key: str
    payload: dict
    photos: tuple[Any, ...]
    observed_at: str


def _transport(url: str, headers: dict[str, str], timeout: float) -> bytes:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _get_json(path: str, *, timeout: float = 20.0,
              transport: Callable[[str, dict[str, str], float], bytes] = _transport) -> Any:
    url = f"{DATASET_ROOT}/{path}?download=true"
    raw = transport(url, {"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout)
    return json.loads(raw.decode("utf-8"))


def _collect_ids(value: Any, out: list[str]) -> None:
    if isinstance(value, (str, int)):
        s = str(value).strip()
        if s.isdigit():
            out.append(s)
    elif isinstance(value, list):
        for x in value:
            _collect_ids(x, out)
    elif isinstance(value, dict):
        for key in ("product_ids", "ids", "products", "data"):
            if key in value:
                _collect_ids(value[key], out)
                return
        for x in value.values():
            _collect_ids(x, out)


def fetch_product_ids(*, timeout: float = 20.0,
                      transport: Callable[[str, dict[str, str], float], bytes] = _transport) -> list[str]:
    payload = _get_json("product_ids.json", timeout=timeout, transport=transport)
    ids: list[str] = []
    _collect_ids(payload, ids)
    result = sorted(set(ids), key=lambda x: (len(x), x))
    if len(result) < 100:
        raise ValueError(f"Unexpectedly small Mercadona product index: {len(result)}")
    return result


def deterministic_candidate_ids(ids: list[str], *, seed: str, limit: int) -> list[str]:
    def key(product_id: str) -> str:
        return hashlib.sha256(f"{seed}:{product_id}".encode()).hexdigest()
    return sorted(ids, key=key)[: min(limit, len(ids))]


def _string(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def _fold(value: str | None) -> str:
    import unicodedata
    text = unicodedata.normalize("NFD", (value or "").lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def is_non_food_product(product: WeeklyCatalogProduct) -> bool:
    text = _fold(" ".join(x for x in (product.name, product.legal_name) if x))
    return any(re.search(pattern, text) for pattern in NON_FOOD_NAME_PATTERNS)


def _ingredients(payload: dict) -> str | None:
    for key in ("ingredients", "ingredients_text", "ingredients_text_es"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for sub in ("text", "description", "value"):
                candidate = _string(value.get(sub))
                if candidate:
                    return candidate
    nutrition_info = payload.get("nutrition_information")
    if isinstance(nutrition_info, dict):
        for key in ("ingredients", "ingredients_text"):
            value = nutrition_info.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _category_parts(payload: dict) -> tuple[str | None, str | None]:
    family = None
    subcategory = None
    for key in ("category", "categories"):
        value = payload.get(key)
        if isinstance(value, dict):
            family = family or _string(value.get("parent_name")) or _string(value.get("family"))
            subcategory = subcategory or _string(value.get("name")) or _string(value.get("display_name"))
        elif isinstance(value, str):
            subcategory = subcategory or value.strip() or None
        elif isinstance(value, list) and value:
            names = []
            for item in value:
                if isinstance(item, str):
                    names.append(item.strip())
                elif isinstance(item, dict):
                    names.append(_string(item.get("name")) or _string(item.get("display_name")) or "")
            names = [x for x in names if x]
            if names:
                family = family or names[0]
                subcategory = subcategory or names[-1]
    family = family or _string(payload.get("category_name")) or _string(payload.get("family"))
    subcategory = subcategory or _string(payload.get("subcategory")) or _string(payload.get("subcategory_name"))
    return family, subcategory


def fetch_product(product_id: str, *, timeout: float = 20.0,
                  transport: Callable[[str, dict[str, str], float], bytes] = _transport) -> WeeklyCatalogProduct:
    product_id = str(product_id).strip()
    if not product_id.isdigit():
        raise ValueError(f"Invalid Mercadona product id: {product_id!r}")
    payload = _get_json(f"products/{product_id}.json", timeout=timeout, transport=transport)
    if not isinstance(payload, dict):
        raise ValueError("Invalid weekly Mercadona product payload")
    observed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    name = (_string(payload.get("display_name")) or _string(payload.get("name"))
            or _string(payload.get("slug")) or product_id)
    ean_raw = payload.get("ean") or payload.get("gtin") or payload.get("barcode")
    ean = str(ean_raw).strip() if ean_raw is not None and str(ean_raw).strip().isdigit() else None
    brand = _string(payload.get("brand"))
    legal_name = (_string(payload.get("legal_name")) or _string(payload.get("legal_description"))
                  or _string(payload.get("description")))
    family, subcategory = _category_parts(payload)
    category_key = subcategory or family or "UNCATEGORIZED"
    photos = payload.get("photos") if isinstance(payload.get("photos"), list) else []
    return WeeklyCatalogProduct(
        product_id=product_id, ean=ean, name=name, brand=brand, legal_name=legal_name,
        ingredients=_ingredients(payload), family=family, subcategory=subcategory,
        category_key=category_key, payload=payload, photos=tuple(photos), observed_at=observed_at,
    )


def stratified_sample(products: list[WeeklyCatalogProduct], *, size: int,
                      per_category_cap: int = 15) -> list[WeeklyCatalogProduct]:
    products = [product for product in products if not is_non_food_product(product)]
    by_category: dict[str, list[WeeklyCatalogProduct]] = {}
    for product in products:
        by_category.setdefault(product.category_key, []).append(product)
    for values in by_category.values():
        values.sort(key=lambda x: x.product_id)
    ordered_categories = sorted(by_category, key=lambda key: (len(by_category[key]), key))
    selected: list[WeeklyCatalogProduct] = []
    round_index = 0
    while len(selected) < size:
        progressed = False
        for category in ordered_categories:
            values = by_category[category]
            if round_index < len(values) and round_index < per_category_cap:
                selected.append(values[round_index])
                progressed = True
                if len(selected) >= size:
                    break
        if not progressed:
            break
        round_index += 1
    if len(selected) < size:
        chosen = {x.product_id for x in selected}
        remaining = sorted((x for x in products if x.product_id not in chosen), key=lambda x: x.product_id)
        selected.extend(remaining[: size - len(selected)])
    return selected[:size]
