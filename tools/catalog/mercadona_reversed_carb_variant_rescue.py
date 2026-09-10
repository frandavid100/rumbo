from __future__ import annotations

from dataclasses import replace

import mercadona_near_safe_variant_rescue as rescue
import mercadona_neural_ocr_wave as base
from nutrition_ocr_ensemble import fuse_ocr_readings
from nutrition_ocr_reversed_label import reversed_carbohydrate_value


RESCUE_NOTE = "REVERSED_CARBOHYDRATE_LABEL_DIAGNOSTIC_RESCUE"
_ORIGINAL_BEST_FUSION = rescue._best_fusion


def _augment_easyocr_reversed_carbohydrate(parsed_readings):
    """Expose one literal EasyOCR carb cell without changing parser acceptance.

    The observed reading-order failure is exactly `1.6g / Carbono / de /
    Hidratos`. The helper requires that literal adjacent structure and an explicit
    gram-like OCR unit. We keep the source reading in REVIEW; only the ordinary
    ensemble can make the tuple usable after independent-family corroboration,
    explicit basis and energy/macro coherence all pass.
    """
    out = []
    changed = False
    for reading in parsed_readings:
        result = reading.result
        nutrition = dict(result.nutrition or {})
        if (
            reading.family == "easyocr"
            and result.status == "REVIEW"
            and result.basis in {"100_g", "100_ml"}
            and "carbohydrate_g" not in nutrition
            and all(name in nutrition for name in ("calories", "fat_g", "protein_g"))
        ):
            value = reversed_carbohydrate_value(result.normalized_text)
            if value is not None:
                nutrition["carbohydrate_g"] = value
                result = replace(
                    result,
                    nutrition=nutrition,
                    reasons=tuple(dict.fromkeys((*result.reasons, RESCUE_NOTE))),
                )
                changed = True
        out.append(replace(reading, result=result))
    return tuple(out), changed


def _best_fusion(readings, target_kind: str):
    parsed = base._as_parsed_readings(readings, target_kind)
    augmented, changed = _augment_easyocr_reversed_carbohydrate(parsed)
    if changed:
        candidate = fuse_ocr_readings(augmented)
        if candidate.declared_usable:
            return replace(
                candidate,
                reasons=tuple(dict.fromkeys((*candidate.reasons, RESCUE_NOTE))),
            )
    return _ORIGINAL_BEST_FUSION(readings, target_kind)


def main() -> int:
    # Preserve the existing bounded variant-rescue extraction and output schema;
    # substitute only the fusion observation above. Image bytes remain temporary.
    rescue._best_fusion = _best_fusion
    base._ORIGINAL_EXTRACT_REGION = base._extract_region
    base._extract_region = rescue._extract_region
    return rescue.main()


if __name__ == "__main__":
    raise SystemExit(main())
