import unittest

from mercadona_near_safe_variant_rescue import (
    RESCUE_VARIANT_NAMES,
    _bounded_dissenting_family_rescue,
    _strategy_suffix,
    should_run_variant_rescue,
)
from nutrition_label_reader import LabelReadResult, read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


class MercadonaNearSafeVariantRescueTest(unittest.TestCase):
    def _near_safe(self):
        complete = read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
Hidratos de carbono 20 g
Proteínas 2.6 g
""", extraction_confidence=.98)
        no_protein = read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
Hidratos de carbono 20 g
""", extraction_confidence=.95)
        self.assertEqual(complete.status, "DECLARED")
        ensemble = fuse_ocr_readings((
            ParsedOCRReading("paddleocr:visual_region", complete, .98, "paddleocr"),
            ParsedOCRReading("tesseract-psm6:visual_region", no_protein, .95, "tesseract"),
        ))
        self.assertEqual(ensemble.status, "REVIEW")
        self.assertEqual(ensemble.corroborated_fields, 3)
        self.assertEqual(ensemble.independent_engine_families, 2)
        return ensemble

    def test_routes_only_clean_three_of_four_corroborated_tuple(self):
        self.assertTrue(should_run_variant_rescue(self._near_safe()))

    def test_tries_only_deterministic_existing_fallback_variants(self):
        self.assertEqual(RESCUE_VARIANT_NAMES, (
            "full_autocontrast",
            "crop_center",
            "crop_left",
            "crop_right",
            "crop_top",
            "crop_bottom",
        ))
        self.assertEqual(_strategy_suffix("full_autocontrast"), "autocontrast")
        self.assertEqual(_strategy_suffix("crop_center"), "crop_center")

    def test_does_not_retry_already_declared_tuple(self):
        parsed = read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
Hidratos de carbono 20 g
Proteínas 2.6 g
""", extraction_confidence=.98)
        ensemble = fuse_ocr_readings((
            ParsedOCRReading("paddleocr", parsed, .98, "paddleocr"),
            ParsedOCRReading("tesseract", parsed, .96, "tesseract"),
        ))
        self.assertEqual(ensemble.status, "DECLARED")
        self.assertFalse(should_run_variant_rescue(ensemble))

    def test_does_not_retry_cross_engine_conflict(self):
        a = read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
Hidratos de carbono 20 g
Proteínas 2.6 g
""", extraction_confidence=.98)
        b = read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 20 g
Hidratos de carbono 20 g
Proteínas 2.6 g
""", extraction_confidence=.95)
        ensemble = fuse_ocr_readings((
            ParsedOCRReading("paddleocr", a, .98, "paddleocr"),
            ParsedOCRReading("tesseract", b, .95, "tesseract"),
        ))
        self.assertEqual(ensemble.status, "REVIEW")
        self.assertTrue(any(r.startswith("OCR_FIELD_CONFLICT") for r in ensemble.reasons))
        self.assertFalse(should_run_variant_rescue(ensemble))

    def test_same_engine_variants_never_count_as_independent_families(self):
        parsed = read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
Hidratos de carbono 20 g
Proteínas 2.6 g
""", extraction_confidence=.98)
        ensemble = fuse_ocr_readings((
            ParsedOCRReading("paddleocr:original", parsed, .98, "paddleocr"),
            ParsedOCRReading("paddleocr:autocontrast", parsed, .97, "paddleocr"),
        ))
        self.assertEqual(ensemble.independent_engine_families, 1)
        self.assertEqual(ensemble.status, "REVIEW")
        self.assertIn("INSUFFICIENT_INDEPENDENT_OCR_ENGINES", ensemble.reasons)

    def test_two_clean_families_can_ignore_one_non_declared_field_outlier(self):
        paddle = read_nutrition_label("""Información nutricional por 100 g
Valor energético 289 kcal
Grasas 25 g
Hidratos de carbono 2.4 g
Proteínas 13 g
""", extraction_confidence=.98)
        tesseract = read_nutrition_label("""Información nutricional por 100 g
Valor energético 289 kcal
Grasas 25 g
Hidratos de carbono 2.4 g
""", extraction_confidence=.82)
        easy = read_nutrition_label("""Información nutricional por 100 g
Valor energético 289 kcal
Grasas 25 g
Hidratos de carbono 24 g
Proteínas 13 g
""", extraction_confidence=.76)
        self.assertEqual(paddle.status, "DECLARED")
        self.assertEqual(easy.status, "REVIEW")
        readings = (
            ParsedOCRReading("paddleocr", paddle, .98, "paddleocr"),
            ParsedOCRReading("tesseract-psm11", tesseract, .82, "tesseract"),
            ParsedOCRReading("easyocr", easy, .76, "easyocr"),
        )
        fused = fuse_ocr_readings(readings)
        self.assertEqual(fused.status, "REVIEW", fused)
        self.assertEqual(fused.corroborated_fields, 3)
        self.assertIn("OCR_FIELD_CONFLICT:carbohydrate_g", fused.reasons)

        rescued = _bounded_dissenting_family_rescue(readings, fused)
        self.assertIsNotNone(rescued)
        self.assertEqual(rescued.status, "DECLARED", rescued)
        self.assertEqual(rescued.nutrition["carbohydrate_g"], 2.4)
        self.assertIn(
            "IGNORED_DISSENTING_ENGINE_FAMILY:carbohydrate_g:easyocr",
            rescued.reasons,
        )

    def test_complete_declared_dissenting_family_is_never_ignored(self):
        good = LabelReadResult(
            "DECLARED", "100_g",
            {"calories": 289.0, "fat_g": 25.0, "carbohydrate_g": 2.4, "protein_g": 13.0},
            .98, tuple(), "fixture",
        )
        partial = LabelReadResult(
            "REVIEW", "100_g",
            {"calories": 289.0, "fat_g": 25.0, "carbohydrate_g": 2.4},
            .82, ("MISSING_CORE:protein_g",), "fixture",
        )
        dissent = LabelReadResult(
            "DECLARED", "100_g",
            {"calories": 289.0, "fat_g": 25.0, "carbohydrate_g": 24.0, "protein_g": 13.0},
            .96, tuple(), "fixture",
        )
        readings = (
            ParsedOCRReading("paddleocr", good, .98, "paddleocr"),
            ParsedOCRReading("tesseract-psm11", partial, .82, "tesseract"),
            ParsedOCRReading("easyocr", dissent, .96, "easyocr"),
        )
        fused = fuse_ocr_readings(readings)
        self.assertEqual(fused.status, "REVIEW")
        self.assertEqual(fused.corroborated_fields, 3)
        self.assertIsNone(_bounded_dissenting_family_rescue(readings, fused))

    def test_no_unique_two_family_value_consensus_remains_review(self):
        paddle = LabelReadResult(
            "DECLARED", "100_g",
            {"calories": 289.0, "fat_g": 25.0, "carbohydrate_g": 2.4, "protein_g": 13.0},
            .98, tuple(), "fixture",
        )
        tesseract = LabelReadResult(
            "REVIEW", "100_g",
            {"calories": 289.0, "fat_g": 25.0, "carbohydrate_g": 3.5},
            .82, ("MISSING_CORE:protein_g",), "fixture",
        )
        easy = LabelReadResult(
            "REVIEW", "100_g",
            {"calories": 289.0, "fat_g": 25.0, "carbohydrate_g": 24.0, "protein_g": 13.0},
            .76, ("ENERGY_MACRO_MISMATCH:373.0",), "fixture",
        )
        readings = (
            ParsedOCRReading("paddleocr", paddle, .98, "paddleocr"),
            ParsedOCRReading("tesseract-psm11", tesseract, .82, "tesseract"),
            ParsedOCRReading("easyocr", easy, .76, "easyocr"),
        )
        fused = fuse_ocr_readings(readings)
        self.assertEqual(fused.status, "REVIEW")
        self.assertIsNone(_bounded_dissenting_family_rescue(readings, fused))


if __name__ == "__main__":
    unittest.main()
