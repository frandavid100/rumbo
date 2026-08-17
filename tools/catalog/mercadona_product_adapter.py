from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Callable
from urllib.request import Request, urlopen

from mercadona_label_evidence import collect_label_images, LabelImageEvidence

ADAPTER_VERSION = "1.0.0"
API_ROOT = "https://tienda.mercadona.es/api/products"
USER_AGENT = "RumboCatalog/0.1 (catalog builder; contact: frandavid100@users.noreply.github.com)"


@dataclass(frozen=True)
class MercadonaProductSnapshot:
    product_id: str
    sku: str
    ean: str | None
    name: str
    brand: str | None
    source_page: str | None
    payload: dict
    observed_at: str
    snapshot_path: str | None
    label_images: tuple[LabelImageEvidence, ...]


def _default_transport(url: str, headers: dict[str, str], timeout: float) -> bytes:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_product(
    product_id: str | int,
    *,
    snapshot_dir: str | Path | None = None,
    timeout: float = 15.0,
    transport: Callable[[str, dict[str, str], float], bytes] = _default_transport,
) -> MercadonaProductSnapshot:
    product_id = str(product_id).strip()
    if not product_id.isdigit():
        raise ValueError(f"Mercadona product id inválido: {product_id!r}")

    observed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    url = f"{API_ROOT}/{product_id}"
    raw = transport(url, {"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout)
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or str(payload.get("id") or product_id) != product_id:
        raise ValueError("Respuesta de producto Mercadona inválida")

    name = payload.get("display_name") or payload.get("name") or payload.get("slug") or product_id
    sku = str(payload.get("id") or product_id)
    ean = str(payload.get("ean")) if payload.get("ean") else None
    brand = payload.get("brand") if isinstance(payload.get("brand"), str) else None
    source_page = payload.get("share_url") if isinstance(payload.get("share_url"), str) else None
    if not source_page and payload.get("slug"):
        source_page = f"https://tienda.mercadona.es/product/{product_id}/{payload['slug']}"

    snapshot_path = None
    if snapshot_dir is not None:
        base = Path(snapshot_dir)
        base.mkdir(parents=True, exist_ok=True)
        target = base / f"mercadona-product-{product_id}-{observed_at.replace(':','-')}.json"
        target.write_bytes(raw)
        snapshot_path = str(target)

    photos = payload.get("photos") if isinstance(payload.get("photos"), list) else []
    label_images = tuple(collect_label_images(
        retailer_sku=sku,
        product_name=name,
        images=photos,
        source_page=source_page,
        snapshot_dir=None,
        observed_at=observed_at,
    ))
    return MercadonaProductSnapshot(
        product_id=product_id,
        sku=sku,
        ean=ean,
        name=name,
        brand=brand,
        source_page=source_page,
        payload=payload,
        observed_at=observed_at,
        snapshot_path=snapshot_path,
        label_images=label_images,
    )
