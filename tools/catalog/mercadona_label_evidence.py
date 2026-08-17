from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import time
from typing import Iterable

ADAPTER_VERSION = "1.0.0"


@dataclass(frozen=True)
class LabelImageEvidence:
    retailer: str
    retailer_sku: str
    product_name: str
    image_url: str
    image_index: int
    observed_at: str
    source_page: str | None
    redistribution_allowed: bool
    purpose: str
    snapshot_path: str | None = None


def _url_from_image(value) -> str | None:
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    if isinstance(value, dict):
        for key in ("zoom", "large", "url", "src", "image", "original"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                return candidate
    return None


def collect_label_images(
    *,
    retailer_sku: str,
    product_name: str,
    images: Iterable,
    source_page: str | None = None,
    snapshot_dir: str | Path | None = None,
    observed_at: str | None = None,
) -> list[LabelImageEvidence]:
    """Register Mercadona pack images as build-time label evidence.

    Mercadona's own help says product images are provided so shoppers can read
    packaging information, including nutritional information. We therefore keep
    every high-resolution pack image as candidate label evidence, but we do not
    redistribute it and we do not guess which image contains nutrition without
    actually reading the label.
    """
    observed_at = observed_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    result: list[LabelImageEvidence] = []
    serializable = []
    for index, raw in enumerate(images):
        url = _url_from_image(raw)
        if not url:
            continue
        serializable.append({"index": index, "url": url})
        result.append(LabelImageEvidence(
            retailer="Mercadona",
            retailer_sku=str(retailer_sku),
            product_name=product_name,
            image_url=url,
            image_index=index,
            observed_at=observed_at,
            source_page=source_page,
            redistribution_allowed=False,
            purpose="PACK_LABEL_CANDIDATE",
        ))
    if snapshot_dir is not None and result:
        base = Path(snapshot_dir)
        base.mkdir(parents=True, exist_ok=True)
        payload = {
            "retailer":"Mercadona", "sku":str(retailer_sku), "name":product_name,
            "source_page":source_page, "observed_at":observed_at,
            "adapter_version":ADAPTER_VERSION, "images":serializable,
            "redistribution_allowed":False,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode()
        digest = hashlib.sha256(raw).hexdigest()[:12]
        path = base / f"mercadona-{retailer_sku}-{digest}.json"
        path.write_bytes(raw)
        result = [LabelImageEvidence(**{**x.__dict__, "snapshot_path":str(path)}) for x in result]
    return result


def nutrition_image_candidates(evidence: Iterable[LabelImageEvidence]) -> list[LabelImageEvidence]:
    """Return images eligible for a later vision/OCR label-reading stage.

    Deliberately does not infer nutritional content from filenames or position.
    All pack images remain candidates until a reader verifies the table.
    """
    return [x for x in evidence if x.purpose == "PACK_LABEL_CANDIDATE"]
