import unittest

from mercadona_near_safe_two_of_four_pilot import should_run_two_of_four_variant_rescue
from mercadona_near_safe_variant_rescue import _bounded_dissenting_family_rescue
from nutrition_label_reader import read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


class MercadonaNearSafeTwoOfFourPilotTest(unittest.TestCase):
    def _fused(self, second_text):
        complete = read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
Hidratos de carbono 20 g
Proteínas 2.6 g
""", extraction_confidence=.98)
        second = read_nutrition_label(second_text, extraction_confidence=.95)
        return fuse_ocr_readings((
            ParsedOCRReading("paddleocr:visual_region", complete, .98, "paddleocr"),
            ParsedOCRReading("tesseract-psm6:visual_region", second, .95, "tesseract"),
        ))

    def test_routes_clean_two_of_four_tuple(self):
        ensemble = self._fused("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
""")
        self.assertEqual(ensemble.status, "REVIEW")
        self.assertEqual(ensemble.corroborated_fields, 2)
        self.assertEqual(ensemble.independent_engine_families, 2)
        self.assertTrue(should_run_two_of_four_variant_rescue(ensemble))

    def test_does_not_expand_bounded_acceptance_to_two_of_four(self):
        ensemble = self._fused("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
""")
        readings = (
            ParsedOCRReading(
                "paddleocr:visual_region",
                read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
Hidratos de carbono 20 g
Proteínas 2.6 g
""", extraction_confidence=.98),
                .98,
                "paddleocr",
            ),
            ParsedOCRReading(
                "tesseract-psm6:visual_region",
                read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
""", extraction_confidence=.95),
                .95,
                "tesseract",
            ),
        )
        self.assertEqual(ensemble.corroborated_fields, 2)
        self.assertIsNone(_bounded_dissenting_family_rescue(readings, ensemble))

    def test_does_not_retry_one_of_four(self):
        ensemble = self._fused("""Información nutricional por 100 g
Valor energético 150 kcal
""")
        self.assertLessEqual(ensemble.corroborated_fields, 1)
        self.assertFalse(should_run_two_of_four_variant_rescue(ensemble))

    def test_does_not_retry_cross_engine_conflict(self):
        ensemble = self._fused("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 20 g
""")
        self.assertEqual(ensemble.status, "REVIEW")
        self.assertTrue(any(r.startswith("OCR_FIELD_CONFLICT") for r in ensemble.reasons))
        self.assertFalse(should_run_two_of_four_variant_rescue(ensemble))

    def test_does_not_retry_three_of_four_stable_cohort(self):
        ensemble = self._fused("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
Hidratos de carbono 20 g
""")
        self.assertEqual(ensemble.corroborated_fields, 3)
        self.assertFalse(should_run_two_of_four_variant_rescue(ensemble))


if __name__ == "__main__":
    unittest.main()
