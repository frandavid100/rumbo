from __future__ import annotations

from typing import Any, Iterable, TypeVar


T = TypeVar("T")


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


def structured_ingredients_p9_alternative_candidate(
    row: dict[str, Any],
    *,
    required_perspective: str | int,
) -> tuple[int, dict[str, Any]] | None:
    """Return one genuine non-p9 image for a p9 food row, never a semantic claim.

    This helper exists for bounded rescue OCR on products whose official p9 image
    has already remained REVIEW. The required alternative perspective is explicit
    so pilot yields can be audited by image view instead of silently mixing them.
    """
    wanted = str(required_perspective)
    if wanted == "9" or not row.get("ingredients") or not has_p9_zoom(row):
        return None
    for index, photo in enumerate(photos(row)):
        if str(photo.get("perspective")) == wanted and photo.get("zoom"):
            return index, photo
    return None


def deterministic_shard_window(
    items: list[T],
    *,
    shard_index: int,
    shard_count: int,
    skip_first: int = 0,
    limit: int = 0,
) -> list[T]:
    """Select a stable shard and optional suffix window without reprocessing its prefix.

    The caller must sort ``items`` deterministically before calling this helper.  This
    makes bounded follow-up OCR runs auditable: a pilot may process the first N items
    of every shard and a later run can continue with ``skip_first=N`` instead of
    downloading and OCRing the pilot rows again.
    """
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard_index must be within shard_count")
    if skip_first < 0:
        raise ValueError("skip_first must be non-negative")
    if limit < 0:
        raise ValueError("limit must be non-negative")

    selected = [item for index, item in enumerate(items) if index % shard_count == shard_index]
    if skip_first:
        selected = selected[skip_first:]
    if limit:
        selected = selected[:limit]
    return selected
