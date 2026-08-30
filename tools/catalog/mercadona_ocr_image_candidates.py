from __future__ import annotations

from typing import Any, Iterable


def photos(row: dict[str, Any]) -> list[dict[str, Any]]:
    raw = row.get("photos")
    if not isinstance(raw, list):
        return []
    return [photo for photo in raw if isinstance(photo, dict)]


def has_p9_zoom(row: dict[str, Any]) -> bool:
    return any(
        str(photo.get("perspective")) == "9" and bool(photo.get("zoom"))
        for photo in photos(row)
    )


def non_p9_zoom_candidates(
    row: dict[str, Any],
    *,
    preferred_perspectives: Iterable[str | int] = ("10", "4", "2", "1"),
) -> list[tuple[int, dict[str, Any]]]:
    """Return real Mercadona non-p9 zoom photos in an explicit, auditable order.

    Perspective is routing metadata only. It never establishes that an image is a
    nutrition label and never makes OCR output usable; downstream parser, energy
    coherence and independent-engine corroboration remain mandatory.
    """
    preference = {str(value): index for index, value in enumerate(preferred_perspectives)}
    candidates: list[tuple[int, dict[str, Any]]] = []
    for index, photo in enumerate(photos(row)):
        if not photo.get("zoom") or str(photo.get("perspective")) == "9":
            continue
        candidates.append((index, photo))
    return sorted(
        candidates,
        key=lambda hit: (
            preference.get(str(hit[1].get("perspective")), len(preference)),
            hit[0],
        ),
    )


def structured_ingredients_no_p9_candidate(
    row: dict[str, Any],
    *,
    preferred_perspectives: Iterable[str | int] = ("10", "4", "2", "1"),
) -> tuple[int, dict[str, Any]] | None:
    if not row.get("ingredients") or has_p9_zoom(row):
        return None
    candidates = non_p9_zoom_candidates(row, preferred_perspectives=preferred_perspectives)
    return candidates[0] if candidates else None
