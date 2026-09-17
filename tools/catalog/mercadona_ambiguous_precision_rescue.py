from __future__ import annotations

"""Precision-raster retry for one already-bounded ambiguous Mercadona label.

This wrapper swaps only the temporary primary-column raster variants used by the
existing ambiguity rescue. Parser, energy/macro coherence, provenance and
independent-family acceptance remain unchanged. Values are never copied from a
historical run or fused across crops.

When MERCADONA_PRECISION_DIAGNOSTICS is set, each suppressed crop observation is
also written as diagnostic JSON. Diagnostics may additionally probe docTR and
EasyOCR on that same single crop and may add a slightly wider temporary crop.
Those probe readings are observability only: they are never appended to the
production extraction result and are never fed back into production fusion.
"""

import json
import os
from pathlib import Path

import mercadona_ambiguous_primary_column_rescue as rescue
import mercadona_bounded_doctr_rescue as bounded
import mercadona_neural_ocr_wave as base
from mercadona_primary_precision_variants import build_precision_primary_column_variants


_CROP_DIAGNOSTICS: list[dict] = []
DIAGNOSTIC_PRIMARY_COLUMN_WIDTH_RATIOS = (0.42, 0.50, 0.56)


def _diagnostics_enabled() -> bool:
    return bool(str(os.environ.get("MERCADONA_PRECISION_DIAGNOSTICS") or "").strip())


def _diagnostic_probe_extractors():
    """Load heavyweight OCR families only inside the explicit diagnostic path."""
    from label_doctr_extractor import extract_with_doctr
    from label_easyocr_extractor import extract_with_easyocr

    return (
        ("diagnostic-doctr", "doctr", extract_with_doctr),
        ("diagnostic-easyocr", "easyocr", extract_with_easyocr),
    )


def _probe_ensemble_payload(readings, target_kind: str) -> dict:
    ensemble = base.fuse_ocr_readings(base._as_parsed_readings(readings, target_kind))
    return base._ensemble_payload(ensemble)


def _diagnostic_independent_probe(evidence, region_path: Path, target_kind: str, readings) -> dict:
    """Probe independent families on one crop without changing extraction output.

    Only one Paddle observation from the same crop is combined with fresh direct
    docTR/EasyOCR observations from that crop. No baseline-region values, other
    crops, historical values, or Tesseract observations are included. The probe
    can therefore reveal whether a later narrowly scoped production route is
    justified without relaxing or bypassing the ordinary ensemble contract.
    """
    paddle = next(
        ((strategy, family, reading) for strategy, family, reading in readings if family == "paddleocr"),
        None,
    )
    payload: dict = {
        "diagnostic_only": True,
        "same_crop_only": True,
        "cross_crop_value_fusion": False,
        "readings": {},
        "ensembles": {},
    }
    if paddle is None:
        payload["error"] = "NO_PADDLE_READING_ON_SAME_CROP"
        return payload

    extras = []
    for strategy, family, extractor in _diagnostic_probe_extractors():
        try:
            extracted = extractor(region_path)
            reading = base._reading(evidence, extracted)
        except Exception as exc:
            payload["readings"][strategy] = {"error": f"{type(exc).__name__}:{exc}"}
            continue
        extras.append((strategy, family, reading))
        payload["readings"][strategy] = base._reading_payload(reading)
        payload["ensembles"][f"paddleocr+{family}"] = _probe_ensemble_payload(
            [paddle, (strategy, family, reading)],
            target_kind,
        )

    if len(extras) == 2:
        payload["ensembles"]["paddleocr+doctr+easyocr"] = _probe_ensemble_payload(
            [paddle, *extras],
            target_kind,
        )
    return payload


def _trace_extract_region(original, sink: list[dict], evidence, region_path: Path, target_kind: str):
    readings, engine_errors, ensemble = original(evidence, region_path, target_kind)
    engines = {
        strategy: base._reading_payload(reading)
        for strategy, _family, reading in readings
    }
    observation = {
        "variant": Path(region_path).name,
        "target_kind": target_kind,
        "engines": engines,
        "engine_errors": dict(engine_errors),
        "ensemble": base._ensemble_payload(ensemble),
    }
    if _diagnostics_enabled() and Path(region_path).name.startswith("primary-precision-left-"):
        observation["independent_same_crop_probe"] = _diagnostic_independent_probe(
            evidence,
            region_path,
            target_kind,
            readings,
        )
    sink.append(observation)
    return readings, engine_errors, ensemble


def _precision_variant_builder(image_path, output_dir):
    ratios = DIAGNOSTIC_PRIMARY_COLUMN_WIDTH_RATIOS if _diagnostics_enabled() else None
    return build_precision_primary_column_variants(
        image_path,
        output_dir,
        width_ratios=ratios,
    )


def _bounded_with_precision_variants():
    bounded.build_bounded_primary_column_variants = _precision_variant_builder
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
            "diagnostic_width_ratios": list(DIAGNOSTIC_PRIMARY_COLUMN_WIDTH_RATIOS),
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
