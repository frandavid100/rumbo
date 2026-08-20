from __future__ import annotations

import re

import carrefour_first_party_inventory as base

# Carrefour currently serves an official supermarket mirror under actforfood.carrefour.es.
# Keep the same per-field first-party provenance policy, but use the mirror as the
# fetch/discovery host when www.carrefour.es is blocked by the edge WAF.
base.BASE = "https://actforfood.carrefour.es"
base.VERSION = "carrefour-first-party-actforfood-1.0"
base.DEFAULT_ROOTS = [
    "https://actforfood.carrefour.es/supermercado/productos-frescos/cat20002/c",
    "https://actforfood.carrefour.es/supermercado/la-despensa/cat20001/c",
    "https://actforfood.carrefour.es/supermercado/bebidas/cat20003/c",
    "https://actforfood.carrefour.es/supermercado/congelados/cat21449123/c",
]
base.PRODUCT_RE = re.compile(
    r"https?://(?:(?:www|actforfood)\.)?carrefour\.es/supermercado/[^\"'<>\s]+/R-[^/\"'<>\s]+/p/?",
    re.I,
)

if __name__ == "__main__":
    raise SystemExit(base.main())
