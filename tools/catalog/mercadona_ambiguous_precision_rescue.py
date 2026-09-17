from __future__ import annotations

"""Precision-raster retry for one already-bounded ambiguous Mercadona label.

This wrapper swaps only the temporary primary-column raster variants used by the
existing ambiguity rescue. Parser, energy/macro coherence, provenance and
independent-family acceptance remain unchanged. Values are never copied from a
historical run or fused across crops.
"""

import mercadona_ambiguous_primary_column_rescue as rescue
import mercadona_bounded_doctr_rescue as bounded
from mercadona_primary_precision_variants import build_precision_primary_column_variants


def _bounded_with_precision_variants():
    bounded.build_bounded_primary_column_variants = build_precision_primary_column_variants
    return bounded


def main() -> int:
    rescue._bounded_module = _bounded_with_precision_variants
    return rescue.main()


if __name__ == "__main__":
    raise SystemExit(main())
