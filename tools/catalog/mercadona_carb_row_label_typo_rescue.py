from __future__ import annotations

"""Targeted Mercadona OCR pilot for two observed carbohydrate row-label typos.

This module changes only non-numeric OCR label normalization for an explicitly
bounded exact-image retry. It never repairs a numeric token and never relaxes
basis, energy/macro coherence, independent-family corroboration, provenance, or
any downstream DECLARED acceptance gate.
"""

import re

import nutrition_label_reader as reader
import mercadona_bounded_doctr_rescue as bounded

_ORIGINAL_NORMALIZE_TEXT = reader.normalize_text
_CARB_ROW_LABEL_TYPO = re.compile(
    r"(?im)^([ \t]*)(?:nidratos|hretos)([ \t]+de[ \t]+carbono\b)"
)


def normalize_carb_row_label_typos(text: str) -> str:
    """Repair only two exact line-initial OCR spellings of `Hidratos de carbono`.

    `Nidratos de carbono` was observed in docTR and `hretos de carbono` in
    Tesseract on the same first-party Mercadona nutrition table. The replacement
    is anchored to the start of a line and changes letters only; all numeric OCR
    output is preserved byte-for-byte after the ordinary production normalizer.
    """
    normalized = _ORIGINAL_NORMALIZE_TEXT(text)
    return _CARB_ROW_LABEL_TYPO.sub(
        lambda match: f"{match.group(1)}Hidratos{match.group(2)}",
        normalized,
    )


def install_targeted_normalizer() -> None:
    reader.normalize_text = normalize_carb_row_label_typos


def main() -> int:
    install_targeted_normalizer()
    return bounded.main()


if __name__ == "__main__":
    raise SystemExit(main())
