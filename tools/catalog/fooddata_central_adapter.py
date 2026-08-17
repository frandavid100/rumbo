from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from nutrition_resolver import NutritionCandidate, ProductIdentity

ADAPTER_VERSION = "1.1.0"
API_ROOT = "https://api.nal.usda.gov/fdc/v1"
SOURCE_NAME = "USDA FoodData Central"
SOURCE_FAMILY = "USDA FoodData Central"
UPSTREAM_LICENSE = "CC0-1.0"
USER_AGENT = "RumboCatalog/0.1 (generic nutrition builder; contact: frandavid100@users.noreply.github.com)"

# FDC exposes both historic nutrient numbers and current nutrient ids depending
# on data type/API representation. Energy must also be interpreted with its unit:
# a kJ row must never be mistaken for kcal.
NUTRIENT_IDENTIFIERS = {
    # Protein
    "203": ("protein_g", 10), "1003": ("protein_g", 20),
    # Total lipid (fat)
    "204": ("fat_g", 10), "1004": ("fat_g", 20),
    # Carbohydrate by difference
    "205": ("carbohydrate_g", 10), "1005": ("carbohydrate_g", 20),
    # Fiber, total dietary
    "291": ("fiber_g", 10), "1079": ("fiber_g", 20),
    # Energy. 1008 is the classic Energy field; Foundation Foods may expose
    # Atwater general/specific energy via 2047/2048.
    "208": ("calories", 5), "1008": ("calories", 30),
    "2047": ("calories", 25), "2048": ("calories", 20),
}
NAME_KEYS = {
    "energy": ("calories", 5),
    "metabolizable energy (atwater general factor)": ("calories", 25),
    "metabolizable energy (atwater specific factor)": ("calories", 20),
    "total lipid (fat)": ("fat_g", 5),
    "carbohydrate, by difference": ("carbohydrate_g", 5),
    "protein": ("protein_g", 5),
    "fiber, total dietary": ("fiber_g", 5),
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
    """Explicitly accepted mapping from a simple Rumbo food to one FDC record."""
    target_name: str
    fdc_id: int
    fdc_description: str
    rationale: str


def _default_get(url: str, headers: dict[str, str], timeout: float) -> bytes:
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def _default_post(url: str, headers: dict[str, str], body: bytes, timeout: float) -> bytes:
    req = Request(url, headers=headers, data=body, method="POST")
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _unit(row: dict) -> str:
    nutrient = row.get("nutrient") if isinstance(row.get("nutrient"), dict) else {}
    value = nutrient.get("unitName") or row.get("unitName") or row.get("unit") or ""
    return str(value).strip().lower()


def _nutrient_key(row: dict) -> tuple[str, int] | None:
    nutrient = row.get("nutrient") if isinstance(row.get("nutrient"), dict) else {}
    identifiers = (
        nutrient.get("id"), row.get("nutrientId"),
        nutrient.get("number"), row.get("nutrientNumber"),
    )
    found = None
    for raw in identifiers:
        if raw is None:
            continue
        value = NUTRIENT_IDENTIFIERS.get(str(raw).strip())
        if value and (found is None or value[1] > found[1]):
            found = value
    if found is None:
        name = str(nutrient.get("name") or row.get("nutrientName") or "").strip().lower()
        found = NAME_KEYS.get(name)
    if found and found[0] == "calories":
        unit = _unit(row)
        # Accept kcal explicitly, or unit-less legacy/test fixtures. Never accept kJ.
        if unit in {"kj", "kilojoule", "kilojoules"}:
            return None
        if unit and unit not in {"kcal", "kilocalorie", "kilocalories"}:
            return None
    return found


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
    priorities = {key: -1 for key in nutrition}
    rows = payload.get("foodNutrients") or []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            identified = _nutrient_key(row)
            if not identified:
                continue
            key, priority = identified
            value = _number(row.get("amount") if "amount" in row else row.get("value"))
            if value is not None and priority > priorities[key]:
                nutrition[key] = value
                priorities[key] = priority
    return FDCFood(fdc_id, description, payload.get("dataType"), nutrition, payload)


def fetch_food(
    fdc_id: int,
    *,
    api_key: str,
    timeout: float = 15.0,
    transport: Callable[[str, dict[str, str], float], bytes] = _default_get,
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
    transport: Callable[[str, dict[str, str], bytes, float], bytes] = _default_post,
) -> list[dict]:
    """Return Foundation/SR proposals only; never auto-publish a search result."""
    if not api_key:
        raise ValueError("FoodData Central api_key is required")
    body = json.dumps({
        "query": query,
        "pageSize": max(1, min(int(page_size), 50)),
        "dataType": ["Foundation", "SR Legacy"],
    }).encode("utf-8")
    url = f"{API_ROOT}/foods/search?{urlencode({'api_key': api_key})}"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"}
    raw = transport(url, headers, body, timeout)
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
