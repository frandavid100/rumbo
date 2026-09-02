from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import mercadona_neural_ocr_tesseract_preprocess_rescue as rescue

TWO_FIELD_RESCUE_POLICY_VERSION = "1.0.0"
CORE_FIELDS = rescue.CORE_FIELDS


def _should_run_two_field_preprocess_rescue(ensemble) -> bool:
    """Spend bounded correlated Tesseract passes on safe two/three-field-short rows.

    This broadens only the *observation* trigger. It does not relax the final
    ensemble acceptance contract: DECLARED still requires the existing parser,
    explicit 100 g/100 ml basis, independent OCR-family corroboration and all
    four core fields to pass the normal conservative gates.
    """
    nutrition = ensemble.nutrition or {}
    return bool(
        not ensemble.declared_usable
        and ensemble.basis in {"100_g", "100_ml"}
        and ensemble.independent_engine_families >= 2
        and ensemble.corroborated_fields in {2, 3}
        and all(field in nutrition for field in CORE_FIELDS)
        and not rescue._hard_conflict(ensemble)
        and not rescue._energy_mismatch(ensemble)
    )


def _rewrite_summary_two_field() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--out", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    args, _ = parser.parse_known_args(sys.argv[1:])
    path = Path(args.out) / f"summary-{args.shard_index:02d}.json"
    if not path.is_file():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["mode"] = "PADDLEOCR_TESSERACT_WITH_SAFE_TWO_OR_THREE_FIELD_TESSERACT_PREPROCESS_RESCUE"
    payload["rescue_policy_version"] = TWO_FIELD_RESCUE_POLICY_VERSION
    payload["preprocess_trigger_corroborated_fields"] = [2, 3]
    payload["preprocess_variants"] = ["clahe", "otsu", "adaptive"]
    payload["preprocess_tesseract_psm"] = [4, 6, 11]
    payload["preprocess_max_side"] = rescue.MAX_PREPROCESS_SIDE
    payload["tesseract_pass_timeout_seconds"] = rescue.TESSERACT_TIMEOUT_SECONDS
    payload["preprocess_variants_are_independent_families"] = False
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    rescue._should_run_preprocess_rescue = _should_run_two_field_preprocess_rescue
    rescue._rewrite_summary = _rewrite_summary_two_field
    return rescue.main()


if __name__ == "__main__":
    raise SystemExit(main())
