from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from nutrition_resolver import NutritionCandidate, ProductIdentity

ADAPTER_VERSION = "1.0.1"
API_ROOT = "https://world.openfoodfacts.org/api/v2/product"
FIELDS = "code,product_name,product_name_es,brands,quantity,ingredients_text,ingredients_text_es,nutriments,selected_images,last_modified_t"
USER_AGENT = "RumboCatalog/0.1 (catalog builder; contact: frandavid100@users.noreply.github.com)"


@dataclass(frozen=True)
class OFFFetchResult:
    gtin: str
    found: bool
    payload: dict
    snapshot_path: str | None
    observed_at: str


def _default_transport(url: str, headers: dict[str, str], timeout: float) -> bytes:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_product(
    gtin: str,
    *,
    snapshot_dir: str | Path | None = None,
    timeout: float = 15.0,
    transport: Callable[[str, dict[str, str], float], bytes] = _default_transport,
) -> OFFFetchResult:
    gtin = str(gtin).strip()
    if not gtin.isdigit() or len(gtin) not in {8, 12, 13, 14}:
        raise ValueError(f"GTIN inválido: {gtin!r}")
    observed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    url = f"{API_ROOT}/{gtin}.json?fields={FIELDS}"
    try:
        raw = transport(url, {"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout)
    except HTTPError as exc:
        # OFF API v2 commonly answers 404 for an unknown GTIN. Absence is normal
        # enrichment debt, not an acquisition failure.
        if exc.code != 404:
            raise
        raw = b'{"status":0}'
    payload = json.loads(raw.decode("utf-8"))
    path = None
    if snapshot_dir is not None:
        base = Path(snapshot_dir)
        base.mkdir(parents=True, exist_ok=True)
        target = base / f"{gtin}-{observed_at.replace(':','-')}.json"
        target.write_bytes(raw)
        path = str(target)
    found = payload.get("status") == 1 and isinstance(payload.get("product"), dict)
    return OFFFetchResult(gtin, found, payload, path, observed_at)


def _n(nutriments: dict, key: str):
    value = nutriments.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def to_candidate(result: OFFFetchResult) -> NutritionCandidate | None:
    if not result.found:
        return None
    p = result.payload["product"]
    n = p.get("nutriments") or {}
    nutrition = {
        "calories": _n(n, "energy-kcal_100g"),
        "fat_g": _n(n, "fat_100g"),
        "carbohydrate_g": _n(n, "carbohydrates_100g"),
        "protein_g": _n(n, "proteins_100g"),
        "fiber_g": _n(n, "fiber_100g"),
    }
    identity = ProductIdentity(
        name=p.get("product_name_es") or p.get("product_name") or result.gtin,
        brand=p.get("brands"),
        gtin=result.gtin,
        format=p.get("quantity"),
        ingredients=p.get("ingredients_text_es") or p.get("ingredients_text"),
    )
    return NutritionCandidate(
        identity=identity,
        nutrition=nutrition,
        source="Open Food Facts",
        source_url=f"https://world.openfoodfacts.org/product/{result.gtin}",
        source_record_id=result.gtin,
        observed_at=result.observed_at,
        upstream_license="ODbL",
        redistribution_allowed=True,
        source_family="Open Food Facts",
        claim="Datos de producto enlazados por GTIN; snapshot conservado por el importador",
    )
