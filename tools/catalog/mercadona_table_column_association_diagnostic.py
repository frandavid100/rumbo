from __future__ import annotations

"""Diagnostic-only Mercadona nutrition-table column association.

The source image is downloaded to a temporary directory, deterministic variants are
built, and Tesseract TSV geometry is inspected. Only OCR text/boxes and association
metadata are persisted. No nutrition value is parsed or made canonically usable.
"""

import argparse
import json
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen

from label_image_preprocess import PREPROCESS_VERSION, build_fallback_variants
from label_table_column_association import ASSOCIATION_VERSION, associate_explicit_basis_column
from label_table_geometry import GEOMETRY_VERSION, geometry_lines, run_tesseract_tsv
from mercadona_nutrition_reader import OCR_EVIDENCE_LEVEL

GEOMETRY_VARIANTS = ("full_autocontrast", "crop_top", "crop_center")
GEOMETRY_PSMS = (4, 6, 11)


def _download_first_party_image(url: str, destination: Path) -> None:
    request = Request(
        url,
        headers={
            "User-Agent": "RumboCatalogAudit/1.0 (+first-party-table-column-diagnostic)",
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


def diagnose(*, image_url: str, product_id: str, ean: str, output_path: Path) -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-table-column-") as td:
        temporary_root = Path(td)
        source_image = temporary_root / "source-image"
        _download_first_party_image(image_url, source_image)
        variants = build_fallback_variants(source_image, temporary_root / "variants")
        for variant in variants:
            if variant.name not in GEOMETRY_VARIANTS:
                continue
            for psm in GEOMETRY_PSMS:
                attempt: dict[str, object] = {
                    "variant": variant.name,
                    "psm": psm,
                    "engine": "tesseract_tsv",
                    "diagnostic_only": True,
                    "nutrition_values_selected": False,
                    "numeric_values_parsed": False,
                }
                try:
                    tokens = run_tesseract_tsv(variant.path, language="spa", psm=psm)
                except RuntimeError as exc:
                    attempt["error"] = str(exc)
                else:
                    association = associate_explicit_basis_column(tokens)
                    attempt.update({
                        "token_count": len(tokens),
                        "association": association,
                        "lines": geometry_lines(tokens),
                    })
                attempts.append(attempt)

    status_counts: dict[str, int] = {}
    for attempt in attempts:
        association = attempt.get("association")
        if not isinstance(association, dict):
            continue
        status = str(association.get("status") or "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1

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
        "nutrition_values_selected": False,
        "numeric_values_parsed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
        "preprocess_version": PREPROCESS_VERSION,
        "geometry_version": GEOMETRY_VERSION,
        "association_version": ASSOCIATION_VERSION,
        "geometry_variants": list(GEOMETRY_VARIANTS),
        "geometry_psms": list(GEOMETRY_PSMS),
        "attempt_count": len(attempts),
        "association_status_counts": status_counts,
        "attempts": attempts,
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
    compact_attempts = []
    for attempt in report["attempts"]:
        association = attempt.get("association") or {}
        rows = association.get("rows") or {}
        compact_attempts.append({
            "variant": attempt.get("variant"),
            "psm": attempt.get("psm"),
            "status": association.get("status"),
            "associated_core_field_count": association.get("associated_core_field_count"),
            "associated_cells": {
                field: row.get("associated_cell", {}).get("text")
                for field, row in rows.items()
                if isinstance(row, dict) and isinstance(row.get("associated_cell"), dict)
            },
        })
    print(json.dumps({
        "product_id": report["product_id"],
        "association_status_counts": report["association_status_counts"],
        "attempts": compact_attempts,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
