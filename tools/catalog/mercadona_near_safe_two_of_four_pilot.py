from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import mercadona_near_safe_variant_rescue as rescue
import mercadona_neural_ocr_wave as base


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


def main() -> int:
    # Reuse the already-tested deterministic crop/layout observation machinery,
    # changing only its retry predicate for this bounded pilot. The normal
    # fusion, basis checks, macro-energy coherence checks and DECLARED threshold
    # are untouched.
    base._ORIGINAL_EXTRACT_REGION = base._extract_region
    rescue.should_run_variant_rescue = should_run_two_of_four_variant_rescue
    base._extract_region = rescue._extract_region
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
