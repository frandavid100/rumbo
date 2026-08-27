"""Run the conservative Mercadona first-party probe against the official v1_1 API.

Mercadona's root category response contains 26 navigation groups; the actual
catalogue endpoints are the nested leaf category ids (for example 112, 164),
not the group ids (12, 19). Keep the extraction/provenance logic in
mercadona_first_party_probe.py unchanged and only adapt endpoint discovery here.
"""

from typing import Any

import mercadona_first_party_probe as probe

probe.API_ROOT = "https://tienda.mercadona.es/api/v1_1"


def _leaf_category_ids(payload: Any) -> list[tuple[str, str | None]]:
    groups = payload.get("results", []) if isinstance(payload, dict) else []
    out: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            continue
        children = group.get("categories")
        if not isinstance(children, list):
            continue
        for child in children:
            if not isinstance(child, dict):
                continue
            category_id = probe._string(child.get("id"))
            if not category_id or not category_id.isdigit() or category_id in seen:
                continue
            seen.add(category_id)
            name = probe._string(child.get("name")) or probe._string(child.get("display_name"))
            out.append((category_id, name))
    return out


probe._root_category_ids = _leaf_category_ids

if __name__ == "__main__":
    raise SystemExit(probe.main())
