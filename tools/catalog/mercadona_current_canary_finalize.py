from __future__ import annotations

"""Attach current-image identity metadata and fail closed on unsafe OCR canary output."""

import argparse
from collections import Counter
import glob
import json
from pathlib import Path
from typing import Any

CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
P9_IDENTITY_RULE = "EXACT_CURRENT_UNIQUE_P9"
ALT_IDENTITY_RULE = "EXACT_CURRENT_ONLY_NON_P9_ZOOM_WITHOUT_UNIQUE_P9"
ALLOWED_IMAGE_IDENTITY_RULES = {P9_IDENTITY_RULE, ALT_IDENTITY_RULE}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _identity_rule(meta: dict[str, Any]) -> str:
    # Backward compatibility for existing exact/changed-P9 canaries created before the
    # explicit rule field existed. Missing rule remains fail-closed to P9 only.
    return str(meta.get("image_identity_rule") or P9_IDENTITY_RULE)


def _perspective_allowed(identity_rule: str, perspective: Any) -> bool:
    value = str(perspective or "").strip()
    if identity_rule == P9_IDENTITY_RULE:
        return value == "9"
    if identity_rule == ALT_IDENTITY_RULE:
        return bool(value) and value != "9"
    return False


def finalize(root: Path) -> dict[str, Any]:
    source_products = {
        str(row.get("product_id") or ""): row for row in _load_jsonl(root / "products.jsonl")
    }
    rows: list[dict[str, Any]] = []
    for result_name in glob.glob(str(root / "ocr" / "results-*.jsonl")):
        result_path = Path(result_name)
        patched: list[dict[str, Any]] = []
        for row in _load_jsonl(result_path):
            pid = str(row.get("product_id") or "")
            source_product = source_products.get(pid)
            if source_product is None:
                raise SystemExit(f"unexpected result product {pid}")
            meta = source_product["_exact_current_image_meta"]
            identity_rule = _identity_rule(meta)
            if identity_rule not in ALLOWED_IMAGE_IDENTITY_RULES:
                raise SystemExit(f"unknown image identity rule for {pid}: {identity_rule}")
            if not _perspective_allowed(identity_rule, meta.get("current_photo_perspective")):
                raise SystemExit(f"image identity rule/perspective mismatch for {pid}")
            if str(row.get("image_url") or "") != str(meta["image_url"]):
                raise SystemExit(f"unexpected result routing for {pid}")
            row.update({
                "image_index": meta.get("current_photo_index"),
                "perspective": meta.get("current_photo_perspective"),
                "image_identity_rule": identity_rule,
                "image_selection_basis": meta.get("image_selection_basis"),
                "identity_basis": meta.get("identity_basis"),
                "canonical_ean": meta.get("canonical_ean"),
                "current_ean": meta.get("current_ean"),
                "live_detail_source_url": meta.get("live_detail_source_url"),
                "live_detail_observed_at": meta.get("live_detail_observed_at"),
                "previous_latest_raw_run_id": meta.get("previous_latest_raw_run_id"),
                "historical_missing_core_fields": meta.get("historical_missing_core_fields"),
                "historical_engine_families": meta.get("historical_engine_families"),
                "historical_corroborated_fields": meta.get("historical_corroborated_fields"),
                "cross_run_value_fusion": False,
                "cross_image_value_fusion": False,
                "historical_partial_values_usable": False,
                "current_observation_must_satisfy_declared_contract_independently": True,
                "acceptance_policy_changed": False,
                "missing_values_inferred": False,
                "image_guessing": False,
            })
            patched.append(row)
            rows.append(row)
        result_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in patched),
            encoding="utf-8",
        )

    result_ids = {str(row.get("product_id") or "") for row in rows}
    if len(rows) != len(source_products) or result_ids != set(source_products):
        raise SystemExit(f"expected one result per verified product ({len(source_products)}), got {len(rows)}")

    for row in rows:
        pid = str(row.get("product_id") or "")
        identity_rule = str(row.get("image_identity_rule") or "")
        if (
            row.get("source") != "MERCADONA_FIRST_PARTY"
            or row.get("source_record_kind") != "label image"
            or row.get("evidence_level") != "OCR_DERIVED_FROM_MERCADONA_IMAGE"
            or row.get("redistribution_allowed") is not False
            or not row.get("canonical_ean")
            or row.get("canonical_ean") != row.get("current_ean")
            or identity_rule not in ALLOWED_IMAGE_IDENTITY_RULES
            or not _perspective_allowed(identity_rule, row.get("perspective"))
        ):
            raise SystemExit(f"unsafe provenance/identity for {pid}")
        if row.get("status") != "DECLARED":
            continue
        nutrition = row.get("nutrition") or {}
        if any(nutrition.get(field) is None for field in CORE) or row.get("basis") not in {"100_g", "100_ml"}:
            raise SystemExit(f"DECLARED without 4/4 + explicit basis for {pid}")
        ensembles = [
            attempt.get("ensemble") or {}
            for attempt in row.get("attempts", [])
            if (attempt.get("ensemble") or {}).get("status") == "DECLARED"
        ]
        if not ensembles:
            raise SystemExit(f"DECLARED without declared ensemble for {pid}")
        if max(int(e.get("independent_engine_families") or 0) for e in ensembles) < 2:
            raise SystemExit(f"DECLARED without >=2 independent OCR families for {pid}")
        if max(int(e.get("corroborated_fields") or 0) for e in ensembles) < 4:
            raise SystemExit(f"DECLARED without 4/4 corroboration for {pid}")
        reasons = [str(reason) for e in ensembles for reason in (e.get("reasons") or [])]
        if any(reason.startswith("MULTIPLE_NUTRITION_COLUMNS") for reason in reasons):
            raise SystemExit(f"DECLARED despite multi-column evidence for {pid}")

    rows.sort(key=lambda row: str(row.get("product_id") or ""))
    (root / "results-merged.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    counts = Counter(str(row.get("status") or "UNKNOWN") for row in rows)
    declared_ids = [str(row.get("product_id") or "") for row in rows if row.get("status") == "DECLARED"]
    identity_rules = sorted({str(row.get("image_identity_rule") or "") for row in rows})
    summary = {
        "inventory_products": 4280,
        "processed": len(rows),
        "status_counts": dict(sorted(counts.items())),
        "declared_product_ids": declared_ids,
        "image_identity_rule": identity_rules[0] if len(identity_rules) == 1 else "MIXED",
        "image_identity_rules": identity_rules,
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "source": "MERCADONA_FIRST_PARTY/label image",
        "redistribution_allowed": False,
        "acceptance_policy_changed": False,
        "cross_run_value_fusion": False,
        "cross_image_value_fusion": False,
        "historical_partial_values_usable": False,
        "fresh_observation_must_recover_all_four": True,
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
