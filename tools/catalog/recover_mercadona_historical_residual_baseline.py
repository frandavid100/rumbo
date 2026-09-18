from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_INVENTORY = 4280
EXPECTED_BASELINE_PROCESSED = 2969
EXPECTED_BASELINE_P9 = 1298
EXPECTED_BASELINE_NO_P9 = 13
TRUSTED_SOURCE_RUN = 33046950149
TRUSTED_SOURCE_ARTIFACT_SHA256 = "5a8c89661afe09fe1c05d1f67e8ed608edf25b8363530db42959ec8413fef648"
TRUSTED_RECOVERY_RUN = 34430788357
TRUSTED_RECOVERY_ARTIFACT_SHA256 = "ac4ef2b916fd41003675aa94c806574e6ed7c827a49c82da0d97e315b68d34db"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected object at {path}:{line_number}")
        rows.append(value)
    return rows


def product_ids(rows: list[dict[str, Any]], *, label: str) -> set[str]:
    ids = [str(row.get("product_id") or "") for row in rows]
    if any(not product_id for product_id in ids):
        raise ValueError(f"{label} contains a missing product_id")
    if len(set(ids)) != len(ids):
        raise ValueError(f"{label} contains duplicate product_ids")
    return set(ids)


def validate_recovery_baseline(
    summary: dict[str, Any],
    canonical_rows: list[dict[str, Any]],
    p9_rows: list[dict[str, Any]],
    no_p9_rows: list[dict[str, Any]],
    *,
    expected_inventory: int = EXPECTED_INVENTORY,
    expected_processed: int = EXPECTED_BASELINE_PROCESSED,
    expected_p9: int = EXPECTED_BASELINE_P9,
    expected_no_p9: int = EXPECTED_BASELINE_NO_P9,
) -> tuple[set[str], set[str]]:
    expected_residual = expected_p9 + expected_no_p9
    required_summary = {
        "inventory_products": expected_inventory,
        "processed_reconstructed": expected_processed,
        "residual_total": expected_residual,
        "p9_residual_total": expected_p9,
        "no_p9_residual_total": expected_no_p9,
    }
    for key, expected in required_summary.items():
        if int(summary.get(key, -1)) != expected:
            raise ValueError(f"baseline summary {key}={summary.get(key)!r}; expected {expected}")

    if len(canonical_rows) != expected_processed:
        raise ValueError(f"baseline canonical rows={len(canonical_rows)}; expected {expected_processed}")
    if len(p9_rows) != expected_p9:
        raise ValueError(f"baseline p9 rows={len(p9_rows)}; expected {expected_p9}")
    if len(no_p9_rows) != expected_no_p9:
        raise ValueError(f"baseline no-p9 rows={len(no_p9_rows)}; expected {expected_no_p9}")

    canonical_ids = product_ids(canonical_rows, label="baseline canonical")
    p9_ids = product_ids(p9_rows, label="baseline p9")
    no_p9_ids = product_ids(no_p9_rows, label="baseline no-p9")
    residual_ids = p9_ids | no_p9_ids
    if p9_ids & no_p9_ids:
        raise ValueError("baseline p9 and no-p9 partitions overlap")
    if canonical_ids & residual_ids:
        raise ValueError("baseline processed and residual partitions overlap")
    if len(canonical_ids | residual_ids) != expected_inventory:
        raise ValueError("baseline partitions do not reconstruct the exact historical inventory membership")

    residual_eans = [str(row.get("ean") or "") for row in p9_rows + no_p9_rows]
    if any(not ean for ean in residual_eans):
        raise ValueError("baseline residual contains a missing EAN")
    if len(set(residual_eans)) != len(residual_eans):
        raise ValueError("baseline residual contains duplicate EANs")

    return canonical_ids, residual_ids


def recover_current_residual(
    summary: dict[str, Any],
    baseline_canonical_rows: list[dict[str, Any]],
    baseline_p9_rows: list[dict[str, Any]],
    baseline_no_p9_rows: list[dict[str, Any]],
    current_canonical_rows: list[dict[str, Any]],
    current_union_summary: dict[str, Any],
    *,
    expected_inventory: int = EXPECTED_INVENTORY,
    expected_processed: int = EXPECTED_BASELINE_PROCESSED,
    expected_p9: int = EXPECTED_BASELINE_P9,
    expected_no_p9: int = EXPECTED_BASELINE_NO_P9,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    baseline_processed_ids, baseline_residual_ids = validate_recovery_baseline(
        summary,
        baseline_canonical_rows,
        baseline_p9_rows,
        baseline_no_p9_rows,
        expected_inventory=expected_inventory,
        expected_processed=expected_processed,
        expected_p9=expected_p9,
        expected_no_p9=expected_no_p9,
    )
    historical_ids = baseline_processed_ids | baseline_residual_ids
    current_ids = product_ids(current_canonical_rows, label="current canonical")

    missing_baseline_processed = sorted(baseline_processed_ids - current_ids)
    if missing_baseline_processed:
        raise ValueError(
            "current canonical union lost products already processed in the trusted pre-expiry baseline: "
            f"{missing_baseline_processed[:10]}"
        )
    post_cut_ids = sorted(current_ids - historical_ids)
    if post_cut_ids:
        raise ValueError(
            "current historical-cut canonical union contains product_ids absent from the trusted 4,280-product membership: "
            f"{post_cut_ids[:10]}"
        )
    if int(current_union_summary.get("final_distinct_union", -1)) != len(current_ids):
        raise ValueError("current canonical row count disagrees with current run-union final_distinct_union")

    identity = current_union_summary.get("identity_reconciliation")
    if not isinstance(identity, dict):
        raise ValueError("current run-union summary lacks identity_reconciliation")
    for key in ("identity_conflict_products", "identity_unverified_products", "identity_unresolved_products"):
        if int(identity.get(key, -1)) != 0:
            raise ValueError(f"current identity reconciliation is not clean: {key}={identity.get(key)!r}")
    if int(identity.get("identity_anchored_products", -1)) != len(current_ids):
        raise ValueError("not every current historical-cut canonical product has an anchored EAN identity")

    remaining_p9 = [row for row in baseline_p9_rows if str(row["product_id"]) not in current_ids]
    remaining_no_p9 = [row for row in baseline_no_p9_rows if str(row["product_id"]) not in current_ids]
    remaining = remaining_p9 + remaining_no_p9
    scope_counts = Counter(str(row.get("ocr_scope_profile") or "UNKNOWN") for row in remaining)
    profile_counts = Counter(str(row.get("profile") or "NO_P9") for row in remaining)
    actionable = [row for row in remaining if str(row.get("ocr_scope_profile") or "").startswith("ACTIONABLE_P9_")]
    blocked_no_p9 = [row for row in remaining if row.get("ocr_scope_profile") == "BLOCKED_NO_P9_FOOD_ROUTE"]
    deferred_bodega = [row for row in remaining if row.get("ocr_scope_profile") == "DEFERRED_BODEGA"]
    out_of_scope = [
        row
        for row in remaining
        if row.get("ocr_scope_profile") in {"OUT_OF_SCOPE_NON_FOOD_SUBCATEGORY", "OUT_OF_SCOPE_NON_FOOD_OR_MIXED"}
    ]

    recovered_summary: dict[str, Any] = {
        "audit_policy_version": "historical-baseline-recovery-1.0.0",
        "status": "EXACT_HISTORICAL_RESIDUAL_RECOVERED",
        "source": "MERCADONA_FIRST_PARTY/label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "inventory_products": expected_inventory,
        "processed_reconstructed": len(current_ids),
        "processed_pct": round(len(current_ids) * 100 / expected_inventory, 4),
        "residual_total": len(remaining),
        "residual_profiles": dict(sorted(profile_counts.items())),
        "ocr_scope_profile_counts": dict(sorted(scope_counts.items())),
        "ocr_actionable_p9_total": len(actionable),
        "ocr_actionable_p9_product_ids": sorted(str(row["product_id"]) for row in actionable),
        "ocr_blocked_no_p9_food_route_total": len(blocked_no_p9),
        "ocr_blocked_no_p9_food_route_product_ids": sorted(str(row["product_id"]) for row in blocked_no_p9),
        "ocr_deferred_bodega_total": len(deferred_bodega),
        "ocr_deferred_bodega_product_ids": sorted(str(row["product_id"]) for row in deferred_bodega),
        "ocr_out_of_scope_total": len(out_of_scope),
        "p9_residual_total": len(remaining_p9),
        "p9_residual_product_ids": [str(row["product_id"]) for row in remaining_p9],
        "no_p9_residual_total": len(remaining_no_p9),
        "no_p9_residual_product_ids": [str(row["product_id"]) for row in remaining_no_p9],
        "historical_membership_recovered": True,
        "historical_membership_products": len(historical_ids),
        "historical_membership_parity_verifiable": True,
        "historical_residual_ean_parity_verifiable": True,
        "historical_processed_ean_anchors_complete": True,
        "historical_full_identity_map_materialized": False,
        "historical_full_detail_snapshot_recovered": False,
        "baseline_processed_products": len(baseline_processed_ids),
        "baseline_residual_products": len(baseline_residual_ids),
        "baseline_run_id": TRUSTED_RECOVERY_RUN,
        "baseline_artifact_sha256": TRUSTED_RECOVERY_ARTIFACT_SHA256,
        "original_first_party_run_id": TRUSTED_SOURCE_RUN,
        "original_first_party_artifact_sha256": TRUSTED_SOURCE_ARTIFACT_SHA256,
        "identity_anchor_mode": identity.get("mode"),
        "identity_anchored_products": identity.get("identity_anchored_products"),
        "images_downloaded": False,
        "images_persisted": False,
        "missing_values_inferred": False,
        "structured_api_macros_claimed": False,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
        "policy": (
            "The original 2026-08-27 first-party artifact expired, so this census is recovered only from a trusted pre-expiry "
            "residual audit that successfully downloaded and verified that exact artifact before expiration. That audit partitions "
            "the 4,280 historical product_ids into 2,969 already-processed products plus 1,311 exact residual products. The current "
            "strict OCR union must contain every baseline processed product and no product outside that historical membership; every "
            "current product must also have a clean earliest-raw-live EAN identity anchor. No later live inventory is substituted. "
            "The original full-detail snapshot is not reconstructed, only the exact historical membership/residual routing metadata "
            "needed for OCR coverage."
        ),
    }
    return remaining_p9, remaining_no_p9, recovered_summary


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-dir", required=True)
    parser.add_argument("--current-canonical", required=True)
    parser.add_argument("--current-union-summary", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    baseline = Path(args.baseline_dir)
    current_canonical_rows = load_jsonl(Path(args.current_canonical))
    current_union_summary = load_json(Path(args.current_union_summary))
    p9_rows, no_p9_rows, recovered_summary = recover_current_residual(
        load_json(baseline / "summary.json"),
        load_jsonl(baseline / "canonical-ocr.jsonl"),
        load_jsonl(baseline / "residual-p9.jsonl"),
        load_jsonl(baseline / "residual-no-p9.jsonl"),
        current_canonical_rows,
        current_union_summary,
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "residual-p9.jsonl", p9_rows)
    write_jsonl(out / "residual-no-p9.jsonl", no_p9_rows)
    (out / "summary.json").write_text(
        json.dumps(recovered_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(recovered_summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
