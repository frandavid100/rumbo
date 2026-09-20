from __future__ import annotations

from typing import Any


def select_unique_current_p9(product: dict[str, Any]) -> tuple[int, dict[str, Any], str]:
    """Return the one unambiguous current first-party perspective=9 photo.

    The selector is intentionally fail-closed. It never falls back to another
    perspective and rejects duplicate/empty image URLs so downstream OCR can
    pin one exact current Mercadona label image without guessing.
    """
    photos = product.get("photos") if isinstance(product.get("photos"), list) else []
    candidates: list[tuple[int, dict[str, Any], str]] = []
    for index, photo in enumerate(photos):
        if not isinstance(photo, dict) or str(photo.get("perspective") or "") != "9":
            continue
        image_url = str(photo.get("zoom") or "").strip()
        if image_url:
            candidates.append((index, photo, image_url))

    if len(candidates) != 1:
        raise ValueError(f"CURRENT_P9_NOT_UNIQUE:{len(candidates)}")

    index, photo, image_url = candidates[0]
    occurrences = sum(
        1
        for candidate in photos
        if isinstance(candidate, dict)
        and str(candidate.get("zoom") or "").strip() == image_url
    )
    if occurrences != 1:
        raise ValueError(f"CURRENT_P9_URL_NOT_UNIQUE:{occurrences}")

    return index, photo, image_url
