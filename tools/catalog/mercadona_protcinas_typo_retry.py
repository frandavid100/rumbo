from __future__ import annotations

"""Narrow live retry for the observed OCR row-label typo ``Protcinas``.

The normal Mercadona OCR pipeline stays conservative.  This module changes no
numeric token and does not relax any acceptance gate; it only repairs the exact
standalone OCR row label ``Protcinas`` to ``Proteinas`` before the existing
nutrition parser runs.  The retry still has to recover all four core macros in
one fresh observation, an explicit 100 g/100 ml basis, coherent energy/macros
and independent OCR-family corroboration.
"""

import re

import nutrition_label_reader as reader


_BASE_NORMALIZE_TEXT = reader.normalize_text


def normalize_text_with_protcinas(text: str) -> str:
    normalized = _BASE_NORMALIZE_TEXT(text)
    # Observed repeatedly for the printed ``Proteinas`` row on product 86395.
    # Restrict the repair to an entire standalone row label, with only optional
    # row punctuation, so prose/ingredients containing the same token are not
    # reinterpreted as nutrition structure.
    return re.sub(
        r"(?im)^([ \t]*)protcinas([ \t]*[:;]?[ \t]*)$",
        r"\1Proteinas\2",
        normalized,
    )


def install_protcinas_normalizer() -> None:
    reader.normalize_text = normalize_text_with_protcinas


def main() -> int:
    install_protcinas_normalizer()
    import mercadona_preselected_three_of_four_variant_rescue as rescue

    return rescue.main()


if __name__ == "__main__":
    raise SystemExit(main())
