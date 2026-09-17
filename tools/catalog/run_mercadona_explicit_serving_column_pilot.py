from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from mercadona_first_party_details import _get_json, _now, normalize


CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
TARGET_PRODUCT_ID = "64499"


def _load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _select_anchor(audit_dir: Path) -> dict:
    src = audit_dir / "current-review-failure-modes" / "complete-but-safety-blocked.jsonl"
    rows = _load_jsonl(src)
    matches = [row for row in rows if str(row.get("product_id") or "") == TARGET_PRODUCT_ID]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one strict residual row for {TARGET_PRODUCT_ID}; found {len(matches)}")
    row = matches[0]
    blockers = set(row.get("safety_blockers") or [])
    reasons = set(row.get("reason_prefixes") or [])
    if (
        row.get("canonical_status") != "REVIEW"
        or int(row.get("corroborated_fields") or 0) != 2
        or int(row.get("independent_engine_families") or 0) < 3
        or row.get("basis") not in {"100_g", "100_ml"}
        or blockers != {"HARD_OCR_CONFLICT"}
        or "OCR_FIELD_CONFLICT" not in reasons
        or "ENERGY_MACRO_MISMATCH" in reasons
        or "MULTIPLE_NUTRITION_COLUMNS" in reasons
        or any(reason.startswith("IMPOSSIBLE_") for reason in reasons)
        or not str(row.get("ean") or "").strip()
        or not str(row.get("image_url") or "").strip()
    ):
        raise RuntimeError("Product 64499 no longer satisfies the bounded historical anchor contract")
    return row


def _live_product(anchor: dict) -> tuple[dict, dict]:
    pid = str(anchor["product_id"])
    anchor_ean = str(anchor.get("ean") or "").strip()
    anchor_url = str(anchor.get("image_url") or "").strip()
    observed_at = _now()
    payload, source_url = _get_json(pid, timeout=20.0)
    current = normalize(payload, source_url=source_url, observed_at=observed_at)
    current_ean = str(current.get("ean") or "").strip()
    if current_ean != anchor_ean:
        raise RuntimeError(f"Current EAN mismatch: current={current_ean!r} anchor={anchor_ean!r}")
    photos = current.get("photos") if isinstance(current.get("photos"), list) else []
    matches = [
        (index, photo)
        for index, photo in enumerate(photos)
        if isinstance(photo, dict)
        and str(photo.get("perspective") or "") == "9"
        and str(photo.get("zoom") or "") == anchor_url
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Canonical perspective=9 image is not uniquely current: {len(matches)} matches")
    image_index, photo = matches[0]
    routed = dict(photo)
    routed["perspective"] = 9
    current["photos"] = [routed]
    meta = {
        "canonical_ean": anchor_ean,
        "image_url": anchor_url,
        "image_index": image_index,
        "canonical_latest_raw_run_id": anchor.get("latest_raw_run_id"),
        "canonical_corroborated_fields": int(anchor.get("corroborated_fields") or 0),
        "canonical_engine_families": int(anchor.get("independent_engine_families") or 0),
        "canonical_safety_blockers": list(anchor.get("safety_blockers") or []),
        "live_detail_source_url": source_url,
        "live_detail_observed_at": observed_at,
    }
    return current, meta


def _run_ocr(product: dict, work: Path) -> dict:
    product_path = work / "product.jsonl"
    raw = work / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    product_path.write_text(json.dumps(product, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    mode = "priority" if product.get("ingredients") else "p9-no-ingredients-all"
    script = Path(__file__).with_name("mercadona_serving_column_rescue_wave.py")
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--products", str(product_path),
            "--out", str(raw),
            "--shard-index", "0",
            "--shard-count", "1",
            "--limit", "0",
            "--eligibility-mode", mode,
        ],
        check=False,
    )
    if proc.returncode not in {0, 2}:
        raise RuntimeError(f"Serving-column OCR wave failed with exit code {proc.returncode}")
    rows = []
    for path in sorted(raw.glob("results-*.jsonl")):
        rows.extend(_load_jsonl(path))
    if len(rows) != 1 or str(rows[0].get("product_id") or "") != TARGET_PRODUCT_ID:
        raise RuntimeError(f"Unexpected rescue coverage: {[(row.get('product_id'), row.get('status')) for row in rows]}")
    return rows[0]


def _validate(row: dict, anchor: dict, meta: dict) -> dict:
    if str(row.get("ean") or "") != str(meta["canonical_ean"]):
        raise RuntimeError("OCR result EAN does not match canonical/live anchor")
    if str(row.get("image_url") or "") != str(meta["image_url"]):
        raise RuntimeError("OCR used an unexpected image")

    row["image_index"] = meta["image_index"]
    row["perspective"] = 9
    row["live_detail_source_url"] = meta["live_detail_source_url"]
    row["live_detail_observed_at"] = meta["live_detail_observed_at"]
    row["pilot_canonical_latest_raw_run_id"] = meta["canonical_latest_raw_run_id"]
    row["pilot_canonical_corroborated_fields"] = meta["canonical_corroborated_fields"]
    row["pilot_canonical_engine_families"] = meta["canonical_engine_families"]
    row["pilot_canonical_safety_blockers"] = meta["canonical_safety_blockers"]
    row["historical_values_promotion_allowed"] = False
    row["cross_run_value_fusion"] = False
    row["cross_region_value_fusion"] = False
    row["current_observation_must_satisfy_declared_contract_independently"] = True
    row["acceptance_policy_changed"] = False
    row["missing_values_inferred"] = False
    row["classified"] = 0
    row["menu_eligible"] = 0
    row["serving_column_projection_policy"] = (
        "EXACT TWO EXPLICIT HEADERS BEFORE CORE ROWS; FIRST 100 G/ML; SECOND SMALLER SAME-UNIT SERVING; "
        "ALL FOUR CORE ROWS HAVE TWO OBSERVED CELLS; EVERY PAIR SCALES TO PRINTED SERVING FRACTION; "
        "EXISTING ENERGY/MACRO COHERENCE; >=2 INDEPENDENT OCR FAMILIES FOR DECLARED"
    )

    if (
        row.get("source") != "MERCADONA_FIRST_PARTY"
        or row.get("source_record_kind") != "label image"
        or row.get("evidence_level") != "OCR_DERIVED_FROM_MERCADONA_IMAGE"
        or row.get("redistribution_allowed") is not False
        or row.get("perspective") != 9
        or int(row.get("pilot_canonical_corroborated_fields") or 0) != 2
        or int(row.get("pilot_canonical_engine_families") or 0) < 3
        or set(row.get("pilot_canonical_safety_blockers") or []) != {"HARD_OCR_CONFLICT"}
        or not str(row.get("live_detail_source_url") or "").startswith("https://tienda.mercadona.es/api/v1_1/products/")
    ):
        raise RuntimeError("Provenance or historical-anchor contract failed")

    if row.get("status") == "DECLARED":
        nutrition = row.get("nutrition") or {}
        if any(nutrition.get(field) is None for field in CORE):
            raise RuntimeError("DECLARED row is missing a core field")
        declared_attempts = [
            attempt for attempt in row.get("attempts", [])
            if (attempt.get("ensemble") or {}).get("status") == "DECLARED"
        ]
        if len(declared_attempts) != 1:
            raise RuntimeError("Expected exactly one independently DECLARED fresh attempt")
        attempt = declared_attempts[0]
        ensemble = attempt.get("ensemble") or {}
        unsafe_prefixes = (
            "OCR_FIELD_CONFLICT", "OCR_SAME_ENGINE_CONFLICT", "OCR_BASIS_CONFLICT",
            "ENERGY_MACRO_MISMATCH", "MULTIPLE_NUTRITION_COLUMNS", "IMPOSSIBLE_",
            "UNCORROBORATED_CORE_FIELDS", "UNCORROBORATED_BASIS",
        )
        unsafe_reasons = [
            str(reason) for reason in ensemble.get("reasons") or []
            if str(reason).startswith(unsafe_prefixes)
        ]
        if (
            ensemble.get("basis") not in {"100_g", "100_ml"}
            or int(ensemble.get("independent_engine_families") or 0) < 2
            or int(ensemble.get("corroborated_fields") or 0) != 4
            or unsafe_reasons
        ):
            raise RuntimeError("Fresh attempt does not meet the unchanged DECLARED contract")
        engine_payloads = attempt.get("engines") or {}
        projected = [
            strategy for strategy, payload in engine_payloads.items()
            if any(
                str(reason).startswith("EXPLICIT_SERVING_COLUMN_PROJECTION")
                for reason in (payload.get("reasons") or [])
            )
        ]
        if not projected:
            raise RuntimeError("DECLARED rescue lacks an explicit serving-column audit marker")
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--canonical-audit-run-id", type=int, required=True)
    args = ap.parse_args()

    audit_dir = Path(args.audit_dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    anchor = _select_anchor(audit_dir)
    current, meta = _live_product(anchor)
    with tempfile.TemporaryDirectory(prefix="rumbo-mercadona-serving-pilot-") as td:
        row = _run_ocr(current, Path(td))
    row = _validate(row, anchor, meta)

    (out / "results-merged.jsonl").write_text(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = {
        "inventory_products": 4280,
        "canonical_audit_run_id": args.canonical_audit_run_id,
        "processed": 1,
        "product_id": str(anchor["product_id"]),
        "product_name": anchor.get("name"),
        "status": row.get("status"),
        "nutrition": row.get("nutrition") if row.get("status") == "DECLARED" else None,
        "historical_corroborated_fields": int(anchor.get("corroborated_fields") or 0),
        "historical_engine_families": int(anchor.get("independent_engine_families") or 0),
        "historical_safety_blockers": list(anchor.get("safety_blockers") or []),
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "redistribution_allowed": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "cross_run_value_fusion": False,
        "cross_region_value_fusion": False,
        "historical_values_promotion_allowed": False,
        "acceptance_policy_changed": False,
        "classified": 0,
        "menu_eligible": 0,
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
