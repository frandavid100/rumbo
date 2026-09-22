from __future__ import annotations

"""Finalize fixed-cut Mercadona OCR rereads for products no longer online.

The preparer already proves a historical-cut identity/image anchor and verifies that
current product detail is HTTP 404.  This finalizer attaches that audit metadata to
the fresh OCR rows and applies the same conservative DECLARED contract used by the
current-image canaries.  It never promotes partial/bounded evidence or combines
values across runs/images.
"""

import argparse
from collections import Counter
import glob
import json
import math
from pathlib import Path
from typing import Any

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"
SOURCE = "MERCADONA_FIRST_PARTY"
SOURCE_RECORD_KIND = "label image"
IDENTITY_RULE = "FIXED_CUT_EXACT_FIRST_PARTY_IMAGE_URL_REREAD_AFTER_LIVE_404"
IMAGE_PREFIX = "https://prod-mercadona.imgix.net/images/"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object row: {path}")
        out.append(value)
    return out


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _declared_ensemble_ok(row: dict[str, Any]) -> bool:
    for attempt in row.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        ensemble = attempt.get("ensemble")
        if not isinstance(ensemble, dict) or ensemble.get("status") != "DECLARED":
            continue
        if int(ensemble.get("independent_engine_families") or 0) < 2:
            continue
        if int(ensemble.get("corroborated_fields") or 0) < 4:
            continue
        reasons = [str(reason) for reason in (ensemble.get("reasons") or [])]
        if any(reason.startswith("MULTIPLE_NUTRITION_COLUMNS") for reason in reasons):
            continue
        return True
    return False


def finalize(root: Path) -> dict[str, Any]:
    selection = _load_json(root / "selection-summary.json")
    if selection.get("identity_rule") != IDENTITY_RULE:
        raise SystemExit("unexpected selection identity rule")
    if selection.get("historical_nutrition_values_consumed") is not False:
        raise SystemExit("historical nutrition must not be consumed")
    if selection.get("historical_ocr_text_consumed") is not False:
        raise SystemExit("historical OCR text must not be consumed")

    selected_rows = selection.get("selected") or []
    selected: dict[str, dict[str, Any]] = {}
    for item in selected_rows:
        if not isinstance(item, dict):
            raise SystemExit("invalid selected metadata row")
        pid = str(item.get("product_id") or "")
        if not pid or pid in selected:
            raise SystemExit("duplicate or empty selected product id")
        selected[pid] = item
    if not selected:
        raise SystemExit("no selected products")

    rows: list[dict[str, Any]] = []
    for name in sorted(glob.glob(str(root / "ocr" / "results-*.jsonl"))):
        rows.extend(_load_jsonl(Path(name)))

    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        pid = str(row.get("product_id") or "")
        if not pid or pid in by_id:
            raise SystemExit(f"duplicate or empty OCR result product id: {pid!r}")
        by_id[pid] = row
    if set(by_id) != set(selected):
        raise SystemExit(f"OCR result product set mismatch: selected={sorted(selected)} results={sorted(by_id)}")

    patched: list[dict[str, Any]] = []
    for pid in sorted(selected):
        meta = selected[pid]
        row = by_id[pid]
        expected_ean = str(meta.get("ean") or "").strip()
        expected_url = str(meta.get("image_url") or "").strip()
        expected_perspective = str(meta.get("perspective") or "").strip()
        if not expected_ean or not expected_url.startswith(IMAGE_PREFIX) or not expected_perspective:
            raise SystemExit(f"incomplete fixed-cut anchor for {pid}")
        if str(row.get("ean") or "").strip() != expected_ean:
            raise SystemExit(f"EAN mismatch for {pid}")
        if str(row.get("image_url") or "").strip() != expected_url:
            raise SystemExit(f"image URL mismatch for {pid}")
        if str(row.get("perspective") or "").strip() != expected_perspective:
            raise SystemExit(f"perspective mismatch for {pid}")
        if (
            row.get("evidence_level") != EVIDENCE
            or row.get("source") != SOURCE
            or row.get("source_record_kind") != SOURCE_RECORD_KIND
            or row.get("redistribution_allowed") is not False
        ):
            raise SystemExit(f"unsafe raw provenance for {pid}")
        if meta.get("current_detail_status") != "HTTP_404":
            raise SystemExit(f"current detail not proven removed for {pid}")

        row.update({
            "image_identity_rule": IDENTITY_RULE,
            "identity_basis": "EARLIER_PERSISTED_RAW_LIVE_EXACT_EAN_PLUS_EXACT_MERCADONA_FIRST_PARTY_IMAGE_URL",
            "canonical_ean": expected_ean,
            "historical_source_run_id": meta.get("historical_source_run_id"),
            "historical_source_artifact_id": meta.get("historical_source_artifact_id"),
            "live_detail_status_at_reread": "HTTP_404",
            "cross_run_value_fusion": False,
            "cross_image_value_fusion": False,
            "historical_partial_values_usable": False,
            "historical_ocr_text_usable": False,
            "current_observation_must_satisfy_declared_contract_independently": True,
            "acceptance_policy_changed": False,
            "missing_values_inferred": False,
            "image_guessing": False,
        })

        if row.get("status") == "DECLARED":
            nutrition = row.get("nutrition")
            if row.get("basis") not in {"100_g", "100_ml"}:
                raise SystemExit(f"DECLARED without explicit basis for {pid}")
            if not isinstance(nutrition, dict) or any(not _finite_number(nutrition.get(field)) for field in CORE):
                raise SystemExit(f"DECLARED without finite 4/4 nutrition for {pid}")
            if not _declared_ensemble_ok(row):
                raise SystemExit(f"DECLARED without independent 4/4 corroboration for {pid}")

        patched.append(row)

    (root / "results-merged.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in patched),
        encoding="utf-8",
    )
    counts = Counter(str(row.get("status") or "UNKNOWN") for row in patched)
    declared_ids = [str(row["product_id"]) for row in patched if row.get("status") == "DECLARED"]
    summary = {
        "inventory_products": 4280,
        "processed": len(patched),
        "status_counts": dict(sorted(counts.items())),
        "declared_product_ids": declared_ids,
        "image_identity_rule": IDENTITY_RULE,
        "identity_anchor": "EARLIER_PERSISTED_RAW_LIVE_EAN_AND_EXACT_FIRST_PARTY_IMAGE_URL",
        "current_detail_requirement": "HTTP_404",
        "evidence_level": EVIDENCE,
        "source": f"{SOURCE}/{SOURCE_RECORD_KIND}",
        "redistribution_allowed": False,
        "acceptance_policy_changed": False,
        "cross_run_value_fusion": False,
        "cross_image_value_fusion": False,
        "historical_partial_values_usable": False,
        "historical_ocr_text_usable": False,
        "fresh_observation_must_recover_all_four": True,
        "fresh_declared_requires_independent_engine_families": 2,
        "fresh_declared_requires_corroborated_fields": 4,
        "images_persisted": False,
        "missing_values_inferred": False,
        "image_guessing": False,
        "classified": 0,
        "menu_eligible": 0,
    }
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    args = ap.parse_args()
    summary = finalize(Path(args.root))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
