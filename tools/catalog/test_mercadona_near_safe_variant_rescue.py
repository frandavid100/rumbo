import unittest

from mercadona_near_safe_variant_rescue import should_run_variant_rescue
from nutrition_label_reader import read_nutrition_label
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


if __name__ == "__main__":
    unittest.main()
