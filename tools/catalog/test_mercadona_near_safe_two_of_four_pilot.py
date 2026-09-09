import unittest

from mercadona_near_safe_two_of_four_pilot import should_run_two_of_four_variant_rescue
from mercadona_near_safe_variant_rescue import _bounded_dissenting_family_rescue
from nutrition_label_reader import LabelReadResult, read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


class MercadonaNearSafeTwoOfFourPilotTest(unittest.TestCase):
    def _complete(self):
        parsed = read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
Hidratos de carbono 20 g
Proteínas 2.6 g
""", extraction_confidence=.98)
        self.assertEqual(parsed.status, "DECLARED")
        return parsed

    def _partial(self, nutrition):
        missing = [
            field
            for field in ("calories", "fat_g", "carbohydrate_g", "protein_g")
            if field not in nutrition
        ]
        return LabelReadResult(
            "REVIEW",
            "100_g",
            {key: float(value) for key, value in nutrition.items()},
            .60,
            ("MISSING_CORE:" + ",".join(missing),),
            "explicit partial OCR fixture",
        )

    def _fused(self, second_nutrition):
        return fuse_ocr_readings((
            ParsedOCRReading("paddleocr:visual_region", self._complete(), .98, "paddleocr"),
            ParsedOCRReading(
                "tesseract-psm6:visual_region",
                self._partial(second_nutrition),
                .95,
                "tesseract",
            ),
        ))

    def test_routes_clean_two_of_four_tuple(self):
        ensemble = self._fused({"calories": 150, "fat_g": 6.1})
        self.assertEqual(ensemble.status, "REVIEW")
        self.assertEqual(ensemble.corroborated_fields, 2)
        self.assertEqual(ensemble.independent_engine_families, 2)
        self.assertTrue(should_run_two_of_four_variant_rescue(ensemble))

    def test_does_not_expand_bounded_acceptance_to_two_of_four(self):
        readings = (
            ParsedOCRReading("paddleocr:visual_region", self._complete(), .98, "paddleocr"),
            ParsedOCRReading(
                "tesseract-psm6:visual_region",
                self._partial({"calories": 150, "fat_g": 6.1}),
                .95,
                "tesseract",
            ),
        )
        ensemble = fuse_ocr_readings(readings)
        self.assertEqual(ensemble.corroborated_fields, 2)
        self.assertIsNone(_bounded_dissenting_family_rescue(readings, ensemble))

    def test_does_not_retry_one_of_four(self):
        ensemble = self._fused({"calories": 150})
        self.assertLessEqual(ensemble.corroborated_fields, 1)
        self.assertFalse(should_run_two_of_four_variant_rescue(ensemble))

    def test_does_not_retry_cross_engine_conflict(self):
        ensemble = self._fused({"calories": 150, "fat_g": 20})
        self.assertEqual(ensemble.status, "REVIEW")
        self.assertTrue(any(r.startswith("OCR_FIELD_CONFLICT") for r in ensemble.reasons))
        self.assertFalse(should_run_two_of_four_variant_rescue(ensemble))

    def test_does_not_retry_three_of_four_stable_cohort(self):
        ensemble = self._fused({"calories": 150, "fat_g": 6.1, "carbohydrate_g": 20})
        self.assertEqual(ensemble.corroborated_fields, 3)
        self.assertFalse(should_run_two_of_four_variant_rescue(ensemble))

    def test_two_marker_text_is_not_used_as_a_parser_fixture(self):
        parsed = read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
""", extraction_confidence=.95)
        self.assertEqual(parsed.status, "NOT_NUTRITION_LABEL")
        self.assertIn("INSUFFICIENT_NUTRITION_MARKERS", parsed.reasons)


if __name__ == "__main__":
    unittest.main()
