import unittest

from nutrition_label_reader import read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


SINGLE_REVERSED_PROTEIN = """Información nutricional por 100 g
Valor energético 1339 kJ / 320 kcal
Grasas 1.2 g
Hidratos de carbono 48.1 g
24.5 g
Proteínas
Sal 0.05 g
"""

INCOHERENT_PRECEDING_VALUE = """Información nutricional por 100 g
Valor energético 1339 kJ / 320 kcal
Grasas 1.2 g
Hidratos de carbono 48.1 g
9.6 g
Proteínas
Sal 0.05 g
"""


class SingleReversedMacroCandidateTest(unittest.TestCase):
    def test_single_reversed_macro_is_exposed_only_as_review_evidence(self):
        r = read_nutrition_label(SINGLE_REVERSED_PROTEIN, extraction_confidence=.97)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertEqual((r.nutrition or {}).get("protein_g"), 24.5)
        self.assertIn("SINGLE_REVERSED_MACRO_CANDIDATE:protein_g", r.reasons)
        self.assertNotIn("MISSING_CORE:protein_g", r.reasons)

    def test_incoherent_single_reversed_value_is_not_exposed(self):
        r = read_nutrition_label(INCOHERENT_PRECEDING_VALUE, extraction_confidence=.97)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertIsNone((r.nutrition or {}).get("protein_g"))
        self.assertIn("MISSING_CORE:protein_g", r.reasons)
        self.assertFalse(any(x.startswith("SINGLE_REVERSED_MACRO_CANDIDATE") for x in r.reasons))

    def test_two_independent_review_observations_may_corroborate_the_candidate(self):
        a = read_nutrition_label(SINGLE_REVERSED_PROTEIN, extraction_confidence=.97)
        b = read_nutrition_label(SINGLE_REVERSED_PROTEIN, extraction_confidence=.94)
        self.assertEqual(a.status, "REVIEW")
        self.assertEqual(b.status, "REVIEW")
        ensemble = fuse_ocr_readings((
            ParsedOCRReading("paddle", a, extraction_confidence=.97, engine_family="paddleocr"),
            ParsedOCRReading("tesseract-psm11", b, extraction_confidence=.94, engine_family="tesseract"),
        ))
        self.assertEqual(ensemble.status, "DECLARED", ensemble)
        self.assertEqual(ensemble.corroborated_fields, 4)
        self.assertEqual(ensemble.nutrition["protein_g"], 24.5)


if __name__ == "__main__":
    unittest.main()
