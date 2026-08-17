from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from nutrition_resolver import NutritionCandidate, ProductIdentity

ADAPTER_VERSION = "1.0.0"
API_ROOT = "https://api.nal.usda.gov/fdc/v1"
SOURCE_NAME = "USDA FoodData Central"
SOURCE_FAMILY = "USDA FoodData Central"
UPSTREAM_LICENSE = "CC0-1.0"
USER_AGENT = "RumboCatalog/0.1 (generic nutrition builder; contact: frandavid100@users.noreply.github.com)"

# Nutrient numbers used by FoodData Central. Names remain a defensive fallback
# because older/exported fixtures are not always shaped exactly like API rows.
NUTRIENT_NUMBERS = {
    "208": "calories",
    "204": "fat_g",
    "205": "carbohydrate_g",
    "203": "protein_g",
    "291": "fiber_g",
}
NAME_KEYS = {
    "energy": "calories",
    "total lipid (fat)": "fat_g",
    "carbohydrate, by difference": "carbohydrate_g",
    "protein": "protein_g",
    "fiber, total dietary": "fiber_g",
}


@dataclass(frozen=True)
class FDCFood:
    fdc_id: int
    description: str
    data_type: str | None
    nutrition: dict[str, float | None]
    raw: dict


@dataclass(frozen=True)
class GenericMapping:
    """Explicitly accepted mapping from a simple Rumbo food to one FDC food.

    The adapter deliberately does not auto-accept fuzzy search results. A caller
    may search FDC to propose candidates, but a GENERIC candidate is only built
    from an explicit mapping carrying the exact FDC id and a review rationale.
    """
    target_name: str
    fdc_id: int
    fdc_description: str
    rationale: str


def _default_transport(url: str, headers: dict[str, str], timeout: float) -> bytes:
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _nutrient_key(row: dict) -> str | None:
    nutrient = row.get("nutrient") if isinstance(row.get("nutrient"), dict) else {}
    number = str(nutrient.get("number") or row.get("nutrientNumber") or "").strip()
    if number in NUTRIENT_NUMBERS:
        return NUTRIENT_NUMBERS[number]
    name = str(nutrient.get("name") or row.get("nutrientName") or "").strip().lower()
    return NAME_KEYS.get(name)


def parse_food(payload: dict) -> FDCFood:
    if not isinstance(payload, dict):
        raise ValueError("Invalid FoodData Central payload")
    fdc_id = payload.get("fdcId")
    if not isinstance(fdc_id, int):
        raise ValueError("FoodData Central record has no integer fdcId")
    description = str(payload.get("description") or "").strip()
    if not description:
        raise ValueError("FoodData Central record has no description")

    nutrition: dict[str, float | None] = {
        "calories": None, "fat_g": None, "carbohydrate_g": None,
        "protein_g": None, "fiber_g": None,
    }
    rows = payload.get("foodNutrients") or []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = _nutrient_key(row)
            if not key:
                continue
            value = _number(row.get("amount") if "amount" in row else row.get("value"))
            if value is not None:
                nutrition[key] = value
    return FDCFood(fdc_id, description, payload.get("dataType"), nutrition, payload)


def fetch_food(
    fdc_id: int,
    *,
    api_key: str,
    timeout: float = 15.0,
    transport: Callable[[str, dict[str, str], float], bytes] = _default_transport,
) -> FDCFood:
    if not api_key:
        raise ValueError("FoodData Central api_key is required")
    url = f"{API_ROOT}/food/{int(fdc_id)}?{urlencode({'api_key': api_key})}"
    raw = transport(url, {"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout)
    return parse_food(json.loads(raw.decode("utf-8")))


def search_foods(
    query: str,
    *,
    api_key: str,
    page_size: int = 10,
    timeout: float = 15.0,
    transport: Callable[[str, dict[str, str], float], bytes] = _default_transport,
) -> list[dict]:
    """Return proposals only; callers must not publish them as GENERIC automatically."""
    if not api_key:
        raise ValueError("FoodData Central api_key is required")
    body = json.dumps({
        "query": query,
        "pageSize": max(1, min(int(page_size), 50)),
        "dataType": ["Foundation", "SR Legacy"],
    }).encode("utf-8")
    url = f"{API_ROOT}/foods/search?{urlencode({'api_key': api_key})}"
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"}

    # transport contract is GET-shaped elsewhere in the catalog code. For tests
    # and offline fixtures, expose a deterministic pseudo-POST envelope instead
    # of silently accepting search results as evidence.
    envelope = {"url": url, "headers": request_headers, "body": body.decode("utf-8")}
    raw = transport("data:application/json," + json.dumps(envelope), request_headers, timeout)
    payload = json.loads(raw.decode("utf-8"))
    foods = payload.get("foods") if isinstance(payload, dict) else None
    return [x for x in (foods or []) if isinstance(x, dict)]


def to_generic_candidate(target: ProductIdentity, mapping: GenericMapping, food: FDCFood) -> NutritionCandidate:
    if mapping.fdc_id != food.fdc_id:
        raise ValueError("Generic mapping FDC id does not match fetched record")
    if mapping.fdc_description.strip().casefold() != food.description.strip().casefold():
        raise ValueError("Generic mapping description no longer matches FDC record")
    if any(food.nutrition.get(k) is None for k in ("calories", "fat_g", "carbohydrate_g", "protein_g")):
        raise ValueError("FoodData Central record lacks core nutrition")
    return NutritionCandidate(
        identity=ProductIdentity(name=target.name, brand=target.brand, gtin=target.gtin, format=target.format, ingredients=target.ingredients),
        nutrition=food.nutrition,
        source=SOURCE_NAME,
        source_url=f"https://fdc.nal.usda.gov/food-details/{food.fdc_id}/nutrients",
        source_record_id=str(food.fdc_id),
        upstream_license=UPSTREAM_LICENSE,
        redistribution_allowed=True,
        source_family=SOURCE_FAMILY,
        claim=f"Generic composition accepted explicitly: {mapping.rationale}",
        evidence_level="GENERIC",
    )
