from __future__ import annotations

import re
import unicodedata


# Narrow diagnostic rescue for one OCR reading-order failure observed on a
# Mercadona nutrition table: EasyOCR can emit the printed row
# `Hidratos de Carbono 1.6 g` as `1.6g / Carbono / de / Hidratos`.
#
# This helper does not infer a value and does not promote anything by itself. It
# exposes only a literal numeric cell that is immediately adjacent to the three
# reversed label tokens. Cross-engine corroboration, basis checks and the normal
# energy/macro coherence gate remain downstream requirements.
def reversed_carbohydrate_value(text: str) -> float | None:
    folded = unicodedata.normalize("NFD", text or "").lower()
    folded = "".join(c for c in folded if unicodedata.category(c) != "Mn")
    match = re.search(
        r"(?:^|\n)\s*([<>]?)\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:g|9|q|yg|y)\s*\n"
        r"\s*carbono\s*\n\s*de\s*\n\s*hidratos?\s*(?:\n|$)",
        folded,
        flags=re.I,
    )
    if not match or match.group(1) in {"<", ">"}:
        return None
    return float(match.group(2).replace(",", "."))
