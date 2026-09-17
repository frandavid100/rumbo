from __future__ import annotations

"""Precision-raster retry for one already-bounded ambiguous Mercadona label.

This wrapper swaps only the temporary primary-column raster variants used by the
existing ambiguity rescue. Parser, energy/macro coherence, provenance and
independent-family acceptance remain unchanged. Values are never copied from a
historical run or fused across crops.

When MERCADONA_PRECISION_DIAGNOSTICS is set, each suppressed crop observation is
also written as diagnostic JSON. This is observability only: the exact extraction
return value is preserved and the diagnostics are never fed back into fusion.
"""

import json
import os
from pathlib import Path

import mercadona_ambiguous_primary_column_rescue as rescue
import mercadona_bounded_doctr_rescue as bounded
import mercadona_neural_ocr_wave as base
from mercadona_primary_precision_variants import build_precision_primary_column_variants


_CROP_DIAGNOSTICS: list[dict] = []


def _trace_extract_region(original, sink: list[dict], evidence, region_path: Path, target_kind: str):
    readings, engine_errors, ensemble = original(evidence, region_path, target_kind)
    engines = {
        strategy: base._reading_payload(reading)
        for strategy, _family, reading in readings
    }
    sink.append({
        "variant": Path(region_path).name,
        "target_kind": target_kind,
        "engines": engines,
        "engine_errors": dict(engine_errors),
        "ensemble": base._ensemble_payload(ensemble),
    })
    return readings, engine_errors, ensemble


def _bounded_with_precision_variants():
    bounded.build_bounded_primary_column_variants = build_precision_primary_column_variants
    current = bounded._DOCTR_EXTRACT_REGION
    if not getattr(current, "_mercadona_precision_traced", False):
        original = current

        def traced(evidence, region_path: Path, target_kind: str):
            return _trace_extract_region(
                original, _CROP_DIAGNOSTICS, evidence, region_path, target_kind
            )

        traced._mercadona_precision_traced = True
        bounded._DOCTR_EXTRACT_REGION = traced
    return bounded


def _write_diagnostics_if_requested() -> None:
    output = str(os.environ.get("MERCADONA_PRECISION_DIAGNOSTICS") or "").strip()
    if not output:
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "diagnostic_only": True,
            "cross_crop_value_fusion": False,
            "acceptance_policy_changed": False,
            "crop_observations": _CROP_DIAGNOSTICS,
        }, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    rescue._bounded_module = _bounded_with_precision_variants
    try:
        return rescue.main()
    finally:
        _write_diagnostics_if_requested()


if __name__ == "__main__":
    raise SystemExit(main())
