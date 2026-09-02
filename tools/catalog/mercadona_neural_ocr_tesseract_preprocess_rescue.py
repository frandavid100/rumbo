from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

import cv2

import mercadona_neural_ocr_wave as base

RESCUE_POLICY_VERSION = "1.1.0"
CORE_FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")
MAX_PREPROCESS_SIDE = 3200
TESSERACT_TIMEOUT_SECONDS = 90


def _hard_conflict(ensemble) -> bool:
    return any(
        str(reason).startswith("OCR_FIELD_CONFLICT")
        or str(reason).startswith("OCR_SAME_ENGINE_CONFLICT")
        or str(reason) == "OCR_BASIS_CONFLICT"
        for reason in (ensemble.reasons or ())
    )


def _energy_mismatch(ensemble) -> bool:
    return any(str(reason).startswith("ENERGY_MACRO_MISMATCH") for reason in (ensemble.reasons or ()))


def _should_run_preprocess_rescue(ensemble) -> bool:
    """Only spend extra Tesseract passes on one-field-short, otherwise safe rows."""
    nutrition = ensemble.nutrition or {}
    return bool(
        not ensemble.declared_usable
        and ensemble.basis in {"100_g", "100_ml"}
        and ensemble.independent_engine_families >= 2
        and ensemble.corroborated_fields == 3
        and all(field in nutrition for field in CORE_FIELDS)
        and not _hard_conflict(ensemble)
        and not _energy_mismatch(ensemble)
    )


def _bounded_tesseract_runner(args: list[str], input_path: str) -> tuple[str, str]:
    """Run a Tesseract observation with a hard per-pass runtime ceiling.

    A timed-out OCR observation is simply absent evidence and is recorded by the
    caller as an engine error. It can never promote a REVIEW row to DECLARED.
    """
    completed = subprocess.run(
        args,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=TESSERACT_TIMEOUT_SECONDS,
    )
    return completed.stdout, completed.stderr


def _extract_tesseract(path: Path, *, psm: int):
    return base.extract_with_tesseract(
        path,
        language="spa",
        psm=psm,
        runner=_bounded_tesseract_runner,
    )


def _preprocess_variants(image_path: Path, out_dir: Path) -> list[tuple[str, Path]]:
    """Create bounded temporary variants that can recover faint/small table glyphs.

    These are correlated Tesseract observations and never count as independent
    engine families. Files live under the caller's TemporaryDirectory only. The
    long side is capped so thresholding cannot create pathological, multi-minute
    Tesseract passes on very large official label crops.
    """
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError(f"cannot decode image: {image_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    height, width = gray.shape[:2]
    scale = min(1.75, MAX_PREPROCESS_SIDE / float(max(height, width)))
    scaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(scaled)
    blurred = cv2.GaussianBlur(clahe, (3, 3), 0)
    _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adaptive = cv2.adaptiveThreshold(
        clahe,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )

    variants = (("clahe", clahe), ("otsu", otsu), ("adaptive", adaptive))
    outputs: list[tuple[str, Path]] = []
    for name, image in variants:
        path = out_dir / f"{name}.png"
        if not cv2.imwrite(str(path), image):
            raise ValueError(f"cannot write preprocessed image: {path}")
        outputs.append((name, path))
    return outputs


def _run_easyocr_if_useful(evidence, target_path: Path, target_kind: str, readings, engine_errors, ensemble):
    """Keep the already validated bounded EasyOCR policy after Tesseract rescue."""
    if ensemble.declared_usable:
        return ensemble
    if not (
        any(reading.parsed.status == "DECLARED" for _strategy, _family, reading in readings)
        or (
            ensemble.independent_engine_families >= 2
            and len(ensemble.nutrition or {}) >= 3
            and not _hard_conflict(ensemble)
        )
    ):
        return ensemble
    try:
        extracted = base.extract_with_easyocr(target_path)
        reading = base._reading(evidence, extracted)
        readings.append(("easyocr", "easyocr", reading))
    except Exception as exc:
        engine_errors["easyocr"] = f"{type(exc).__name__}:{exc}"
        return ensemble

    raw = base.fuse_ocr_readings(base._as_parsed_readings(readings, target_kind))
    if raw.declared_usable:
        return raw
    strict = base._fuse_declared_only_readings(
        (
            (strategy, family, reading.parsed, reading.extraction.confidence)
            for strategy, family, reading in readings
        ),
        target_kind,
    )
    return strict if strict.declared_usable else raw


def _extract_region(evidence, region_path: Path, target_kind: str):
    readings = []
    engine_errors: dict[str, str] = {}
    extractor_specs = (
        ("paddleocr", "paddleocr", base.extract_with_paddleocr),
        ("tesseract-psm4", "tesseract", lambda path: _extract_tesseract(path, psm=4)),
        ("tesseract-psm6", "tesseract", lambda path: _extract_tesseract(path, psm=6)),
        ("tesseract-psm11", "tesseract", lambda path: _extract_tesseract(path, psm=11)),
    )
    for strategy, family, extractor in extractor_specs:
        try:
            extracted = extractor(region_path)
            readings.append((strategy, family, base._reading(evidence, extracted)))
        except Exception as exc:
            engine_errors[strategy] = f"{type(exc).__name__}:{exc}"

    ensemble = base.fuse_ocr_readings(base._as_parsed_readings(readings, target_kind))
    if _should_run_preprocess_rescue(ensemble):
        try:
            with tempfile.TemporaryDirectory(prefix="rumbo-tesseract-preprocess-") as td:
                variants = _preprocess_variants(region_path, Path(td))
                for variant_name, variant_path in variants:
                    for psm in (4, 6, 11):
                        strategy = f"tesseract-{variant_name}-psm{psm}"
                        try:
                            extracted = _extract_tesseract(variant_path, psm=psm)
                            readings.append((strategy, "tesseract", base._reading(evidence, extracted)))
                        except Exception as exc:
                            engine_errors[strategy] = f"{type(exc).__name__}:{exc}"
        except Exception as exc:
            engine_errors["tesseract-preprocess"] = f"{type(exc).__name__}:{exc}"
        ensemble = base.fuse_ocr_readings(base._as_parsed_readings(readings, target_kind))

    ensemble = _run_easyocr_if_useful(
        evidence, region_path, target_kind, readings, engine_errors, ensemble
    )
    return readings, engine_errors, ensemble


def _rewrite_summary() -> None:
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--out", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    args, _ = parser.parse_known_args(sys.argv[1:])
    path = Path(args.out) / f"summary-{args.shard_index:02d}.json"
    if not path.is_file():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["mode"] = "PADDLEOCR_TESSERACT_WITH_ONE_FIELD_SHORT_TESSERACT_PREPROCESS_RESCUE"
    payload["rescue_policy_version"] = RESCUE_POLICY_VERSION
    payload["preprocess_variants"] = ["clahe", "otsu", "adaptive"]
    payload["preprocess_tesseract_psm"] = [4, 6, 11]
    payload["preprocess_max_side"] = MAX_PREPROCESS_SIDE
    payload["tesseract_pass_timeout_seconds"] = TESSERACT_TIMEOUT_SECONDS
    payload["preprocess_variants_are_independent_families"] = False
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    base._extract_region = _extract_region
    result = base.main()
    _rewrite_summary()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
