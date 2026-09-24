from __future__ import annotations

"""Diagnostic-only Tesseract rescue over deterministic first-party image variants.

This module is intentionally outside the canonical Mercadona OCR reconciliation
path. It downloads one already-validated first-party label URL into a temporary
directory, builds deterministic autocontrast/crop variants, runs Tesseract, and
persists only OCR text plus parser results. It never persists or redistributes the
source image and never infers missing nutrition values.

For a small predefined subset of variants it also persists Tesseract word geometry.
That geometry is diagnostic evidence only: it may show whether an explicit ``100 g``
header defines a unique column, but it is never used here to choose nutritional
values or to make a record canonically usable.
"""

import argparse
import json
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen

from label_image_preprocess import PREPROCESS_VERSION, build_fallback_variants
from label_table_geometry import (
    GEOMETRY_VERSION,
    find_explicit_basis_headers,
    geometry_lines,
    run_tesseract_tsv,
    unique_basis_header,
)
from label_text_extractor import EXTRACTOR_VERSION, ExtractionError, extract_with_tesseract
from mercadona_nutrition_label_manufacturer_interleave import read_nutrition_label
from mercadona_nutrition_reader import ADAPTER_VERSION, OCR_EVIDENCE_LEVEL
from nutrition_label_reader import READER_VERSION as GENERIC_PARSER_VERSION
from nutrition_unit_glyph_repair import repair_observed_trailing_g_as_eight

PSMS = (4, 6, 11)
CORE_FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")
# Fixed before OCR is run.  The diagnostic must not choose the transform with the
# most plausible output after seeing nutritional values.
GEOMETRY_VARIANTS = ("full_autocontrast", "crop_top", "crop_center")
GEOMETRY_PSM = 6


def _download_first_party_image(url: str, destination: Path) -> None:
    request = Request(
        url,
        headers={
            "User-Agent": "RumboCatalogAudit/1.0 (+first-party-label-diagnostic)",
            "Accept": "image/*",
        },
    )
    with urlopen(request, timeout=30) as response, destination.open("wb") as handle:
        content_type = str(response.headers.get("Content-Type") or "").lower()
        if content_type and not content_type.startswith("image/"):
            raise RuntimeError(f"expected image content, got {content_type!r}")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    if not destination.is_file() or destination.stat().st_size <= 0:
        raise RuntimeError("first-party image download produced an empty file")


def _parse_extraction(text: str, confidence: float) -> dict[str, object]:
    parser_text = repair_observed_trailing_g_as_eight(text)
    parsed = read_nutrition_label(parser_text, extraction_confidence=confidence)
    nutrition = dict(parsed.nutrition or {})
    return {
        "status": parsed.status,
        "basis": parsed.basis,
        "nutrition": nutrition,
        "parser_confidence": parsed.confidence,
        "reasons": list(parsed.reasons),
        "normalized_text": parsed.normalized_text,
        "unit_glyph_repair_changed_text": parser_text != text,
    }


def _profile_key(parsed: dict[str, object]) -> tuple[float, float, float, float, str] | None:
    if parsed.get("status") != "DECLARED":
        return None
    nutrition = parsed.get("nutrition")
    if not isinstance(nutrition, dict):
        return None
    try:
        values = tuple(float(nutrition[field]) for field in CORE_FIELDS)
    except (KeyError, TypeError, ValueError):
        return None
    basis = str(parsed.get("basis") or "")
    if basis not in {"100_g", "100_ml"}:
        return None
    return values + (basis,)


def _header_dict(header) -> dict[str, object]:
    return {
        "basis": header.basis,
        "text": header.text,
        "left": header.left,
        "right": header.right,
        "top": header.top,
        "bottom": header.bottom,
        "center_x": header.center_x,
        "line_key": list(header.line_key),
    }


def diagnose(
    *,
    image_url: str,
    product_id: str,
    ean: str,
    output_path: Path,
) -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    geometry_attempts: list[dict[str, object]] = []
    profile_support: dict[tuple[float, float, float, float, str], list[dict[str, object]]] = {}

    with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-tesseract-") as td:
        temporary_root = Path(td)
        source_image = temporary_root / "source-image"
        _download_first_party_image(image_url, source_image)
        variants = build_fallback_variants(source_image, temporary_root / "variants")

        for variant in variants:
            if variant.name in GEOMETRY_VARIANTS:
                geometry_attempt: dict[str, object] = {
                    "variant": variant.name,
                    "psm": GEOMETRY_PSM,
                    "engine": "tesseract_tsv",
                    "selection_policy": "predefined_variant_and_explicit_100_basis_header_only",
                    "nutrition_values_selected": False,
                }
                try:
                    tokens = run_tesseract_tsv(variant.path, language="spa", psm=GEOMETRY_PSM)
                except RuntimeError as exc:
                    geometry_attempt["error"] = str(exc)
                else:
                    status, unique_header = unique_basis_header(tokens)
                    headers = find_explicit_basis_headers(tokens)
                    geometry_attempt.update({
                        "token_count": len(tokens),
                        "basis_header_status": status,
                        "basis_headers": [_header_dict(header) for header in headers],
                        "unique_basis_header": _header_dict(unique_header) if unique_header else None,
                        "lines": geometry_lines(tokens),
                    })
                geometry_attempts.append(geometry_attempt)

            for psm in PSMS:
                attempt: dict[str, object] = {
                    "variant": variant.name,
                    "psm": psm,
                    "engine": "tesseract",
                }
                try:
                    extraction = extract_with_tesseract(variant.path, language="spa", psm=psm)
                except ExtractionError as exc:
                    attempt["error"] = str(exc)
                    attempts.append(attempt)
                    continue

                parsed = _parse_extraction(extraction.text, extraction.confidence)
                attempt.update({
                    "engine_version": extraction.engine_version,
                    "ocr_confidence": extraction.confidence,
                    "ocr_text": extraction.text,
                    "parsed": parsed,
                })
                attempts.append(attempt)

                key = _profile_key(parsed)
                if key is not None:
                    profile_support.setdefault(key, []).append({
                        "variant": variant.name,
                        "psm": psm,
                        "ocr_confidence": extraction.confidence,
                    })

    complete_declared_profiles = [
        {
            "nutrition": {
                "calories": key[0],
                "fat_g": key[1],
                "carbohydrate_g": key[2],
                "protein_g": key[3],
            },
            "basis": key[4],
            "support": support,
            # Multiple variants/PSMs remain one OCR family. This diagnostic alone
            # can never satisfy the independent-family production requirement.
            "independent_engine_families": 1,
        }
        for key, support in sorted(profile_support.items())
    ]

    report: dict[str, object] = {
        "diagnostic_only": True,
        "canonical_reconciliation_allowed": False,
        "product_id": str(product_id),
        "ean": str(ean),
        "image_url": image_url,
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": OCR_EVIDENCE_LEVEL,
        "redistribution_allowed": False,
        "source_image_persisted": False,
        "missing_values_inferred": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
        "generic_parser_version": GENERIC_PARSER_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "preprocess_version": PREPROCESS_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "geometry_version": GEOMETRY_VERSION,
        "psms": list(PSMS),
        "geometry_variants": list(GEOMETRY_VARIANTS),
        "geometry_psm": GEOMETRY_PSM,
        "attempts": attempts,
        "geometry_attempts": geometry_attempts,
        "complete_declared_profiles": complete_declared_profiles,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", required=True)
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--ean", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    report = diagnose(
        image_url=args.image_url,
        product_id=args.product_id,
        ean=args.ean,
        output_path=args.out,
    )
    print(json.dumps({
        "product_id": report["product_id"],
        "complete_declared_profiles": report["complete_declared_profiles"],
        "attempt_count": len(report["attempts"]),
        "geometry": [
            {
                "variant": attempt.get("variant"),
                "basis_header_status": attempt.get("basis_header_status"),
                "basis_headers": attempt.get("basis_headers"),
            }
            for attempt in report["geometry_attempts"]
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
