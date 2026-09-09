from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Iterable

import mercadona_near_safe_variant_rescue as rescue
import mercadona_neural_ocr_wave as base


CORE = ("calories", "fat_g", "carbohydrate_g", "protein_g")
DEFAULT_LIMIT = 16

# This pilot broadens only the *observation retry* gate from the exhausted 3/4
# cohort to a clean 2/4-corroborated cohort. Acceptance remains the existing
# conservative ensemble policy. In particular, the bounded dissenting-family
# rescue in mercadona_near_safe_variant_rescue still requires exactly 3/4 fields
# and therefore cannot promote a 2/4 tuple by itself.
#
# Cohort selection is intentionally rebuilt from the latest canonical residual
# on every workflow run. Persisted cut files are also consulted so a product
# which remains 2/4 after an exact-image retry is not needlessly selected again
# in the next bounded wave.
def should_run_two_of_four_variant_rescue(ensemble) -> bool:
    if ensemble.status != "REVIEW" or ensemble.declared_usable:
        return False
    if ensemble.basis not in {"100_g", "100_ml"}:
        return False
    if not ensemble.nutrition or any(
        field not in ensemble.nutrition for field in base.CORE_NUTRITION_FIELDS
    ):
        return False
    if ensemble.independent_engine_families < 2:
        return False
    if ensemble.corroborated_fields != 2:
        return False
    if "UNCORROBORATED_CORE_FIELDS" not in ensemble.reasons:
        return False
    return not any(
        str(reason).startswith(prefix)
        for reason in ensemble.reasons
        for prefix in rescue.HARD_BLOCKING_PREFIXES
    )


def _collect_selected_product_ids(value, selected: set[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "selected_product_ids" and isinstance(nested, list):
                selected.update(str(item) for item in nested if str(item))
            else:
                _collect_selected_product_ids(nested, selected)
    elif isinstance(value, list):
        for nested in value:
            _collect_selected_product_ids(nested, selected)


def load_previously_attempted_product_ids(paths: Iterable[str | Path]) -> set[str]:
    """Return product IDs already selected by persisted 2/4 cut manifests.

    Cut schemas evolved during the pilot, so selection metadata may be top-level
    or nested under a summary object. Only explicit ``selected_product_ids``
    fields are consumed; DECLARED/REVIEW diagnostics are deliberately ignored.
    Invalid/non-object JSON fails closed by raising instead of silently replaying
    a possibly incomplete history.
    """
    selected: set[str] = set()
    for path_like in paths:
        path = Path(path_like)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"2-of-4 cut must be a JSON object: {path}")
        _collect_selected_product_ids(payload, selected)
    return selected


def build_deduplicated_two_of_four_candidates(
    diagnostic_path: str | Path,
    product_path: str | Path,
    attempted_ids: set[str],
    *,
    limit: int = DEFAULT_LIMIT,
) -> tuple[list[dict], dict]:
    """Rebuild the bounded exact-image cohort while excluding prior attempts."""
    targets: dict[str, dict] = {}
    for line in Path(diagnostic_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        pid = str(row.get("product_id") or "")
        values = row.get("diagnostic_candidate_values") or {}
        if (
            row.get("canonical_status") == "REVIEW"
            and row.get("corroborated_fields") == 2
            and int(row.get("independent_engine_families") or 0) >= 2
            and row.get("basis") in {"100_g", "100_ml"}
            and all(field in values for field in CORE)
            and not (row.get("safety_blockers") or [])
            and pid
            and row.get("image_url")
        ):
            targets[pid] = row

    candidates: list[dict] = []
    unmatched_current_photo: list[str] = []
    excluded_previously_attempted: list[str] = []
    for line in Path(product_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        pid = str(row.get("product_id") or "")
        diagnostic = targets.get(pid)
        if diagnostic is None:
            continue
        if pid in attempted_ids:
            excluded_previously_attempted.append(pid)
            continue
        image_url = str(diagnostic["image_url"])
        photos = row.get("photos") if isinstance(row.get("photos"), list) else []
        match = next(
            (
                (index, photo)
                for index, photo in enumerate(photos)
                if isinstance(photo, dict) and str(photo.get("zoom") or "") == image_url
            ),
            None,
        )
        if match is None:
            unmatched_current_photo.append(pid)
            continue

        image_index, photo = match
        actual_perspective = photo.get("perspective")
        routed_photo = dict(photo)
        routed_photo["perspective"] = 9
        candidate = dict(row)
        candidate["photos"] = [routed_photo]
        candidate["_near_safe_image_meta"] = {
            "image_url": image_url,
            "image_index": image_index,
            "perspective": actual_perspective,
            "canonical_latest_raw_run_id": diagnostic.get("latest_raw_run_id"),
            "canonical_corroborated_fields": diagnostic.get("corroborated_fields"),
            "canonical_engine_families": diagnostic.get("independent_engine_families"),
            "canonical_confidence": diagnostic.get("confidence"),
        }
        candidates.append(candidate)

    candidates.sort(
        key=lambda row: (
            0 if row.get("ingredients") else 1,
            -int((row.get("_near_safe_image_meta") or {}).get("canonical_engine_families") or 0),
            -float((row.get("_near_safe_image_meta") or {}).get("canonical_confidence") or 0.0),
            str(row.get("product_id") or ""),
        )
    )
    selected = candidates[:limit]
    summary = {
        "pilot_limit": limit,
        "canonical_two_of_four_targets": len(targets),
        "previously_attempted_ids_loaded": len(attempted_ids),
        "excluded_previously_attempted_current_two_of_four": sorted(excluded_previously_attempted),
        "current_exact_first_party_image_unattempted_targets": len(candidates),
        "selected": len(selected),
        "selected_with_structured_ingredients": sum(bool(row.get("ingredients")) for row in selected),
        "selected_without_structured_ingredients": sum(not bool(row.get("ingredients")) for row in selected),
        "selected_three_engine_family_targets": sum(
            int((row.get("_near_safe_image_meta") or {}).get("canonical_engine_families") or 0) >= 3
            for row in selected
        ),
        "selected_product_ids": [str(row.get("product_id")) for row in selected],
        "unmatched_current_first_party_photo": sorted(unmatched_current_photo),
        "selection_policy": "CLEAN_CANONICAL_2_OF_4_REVIEW_EXACT_CURRENT_FIRST_PARTY_IMAGE; EXCLUDE_PERSISTED_2_OF_4_ATTEMPTS; PRIORITIZE_STRUCTURED_INGREDIENTS_THEN_ENGINE_FAMILIES_THEN_CONFIDENCE",
        "acceptance_policy_changed": False,
    }
    return selected, summary


def refresh_workflow_cohort_if_available() -> dict | None:
    """Replace the workflow's provisional cohort with the next untried wave.

    The workflow historically built its 16 rows inline. Keeping this refresh in
    the tested Python entry point lets new waves advance without changing OCR or
    parser acceptance and without replaying products that remain canonical 2/4.
    """
    diagnostic_path = Path(
        "mercadona-current-ocr-residual-audit/current-review-failure-modes/near-safe-complete-review.jsonl"
    )
    product_path = Path("mercadona-first-party-final/products.jsonl")
    if not diagnostic_path.exists() or not product_path.exists():
        return None

    cut_paths = sorted(glob.glob("mercadona-near-safe-two-of-four*-cut-*.json"))
    attempted = load_previously_attempted_product_ids(cut_paths)
    selected, summary = build_deduplicated_two_of_four_candidates(
        diagnostic_path,
        product_path,
        attempted,
    )
    if not selected:
        raise SystemExit("No unattempted actionable clean 2-of-4 exact first-party images found")

    with_ingredients = [row for row in selected if row.get("ingredients")]
    without_ingredients = [row for row in selected if not row.get("ingredients")]

    def write_jsonl(path: str, rows: list[dict]) -> None:
        Path(path).write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

    write_jsonl("two-of-four-with-ingredients.jsonl", with_ingredients)
    write_jsonl("two-of-four-without-ingredients.jsonl", without_ingredients)
    Path("two-of-four-selection-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    # Reuse the already-tested deterministic crop/layout observation machinery,
    # changing only its retry predicate for this bounded pilot. The normal
    # fusion, basis checks, macro-energy coherence checks and DECLARED threshold
    # are untouched.
    refresh_workflow_cohort_if_available()
    base._ORIGINAL_EXTRACT_REGION = base._extract_region
    rescue.should_run_variant_rescue = should_run_two_of_four_variant_rescue
    base._extract_region = rescue._extract_region
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
