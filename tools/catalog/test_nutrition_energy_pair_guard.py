import unittest

from nutrition_label_reader import read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


INCOHERENT = """100 g
Valor
635 kJ
Energético
182 kcal
Grasas 8.9 g
Hidratos de carbono 0 g
Proteínas 18 g
Sal 0.15 g
"""

OCR_182_NO_KJ = """100 g
Valor energético 182 kcal
Grasas 8.9 g
Hidratos de carbono 0 g
Proteínas 18 g
Sal 0.15 g
"""

COHERENT = """Información nutricional por 100 g
Valor energético 635 kJ / 152 kcal
Grasas 8.9 g
Hidratos de carbono 0 g
Proteínas 18 g
Sal 0.15 g
"""


class NutritionEnergyPairGuardTest(unittest.TestCase):
    def test_single_reader_preserves_existing_energy_macro_diagnostic(self):
        result = read_nutrition_label(INCOHERENT, extraction_confidence=.98)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertEqual((result.nutrition or {}).get("calories"), 182.0)
        self.assertTrue(
            any(reason.startswith("ENERGY_MACRO_MISMATCH") for reason in result.reasons),
            result.reasons,
        )

    def test_coherent_explicit_pair_remains_usable_without_conversion(self):
        result = read_nutrition_label(COHERENT, extraction_confidence=.98)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.nutrition["calories"], 152.0)
        self.assertEqual(result.nutrition["protein_g"], 18.0)

    def test_one_incoherent_family_vetoes_repeated_suspect_kcal(self):
        paddle = read_nutrition_label(INCOHERENT, extraction_confidence=.98)
        easy = read_nutrition_label(OCR_182_NO_KJ, extraction_confidence=.96)
        tess = read_nutrition_label(OCR_182_NO_KJ, extraction_confidence=.94)
        fused = fuse_ocr_readings((
            ParsedOCRReading("paddleocr", paddle, .98, "paddleocr"),
            ParsedOCRReading("easyocr", easy, .96, "easyocr"),
            ParsedOCRReading("tesseract-psm11", tess, .94, "tesseract"),
        ))
        self.assertEqual(fused.status, "REVIEW", fused)
        self.assertNotIn("calories", fused.nutrition or {})
        self.assertTrue(
            any(reason.startswith("OCR_ENERGY_UNIT_MISMATCH:paddleocr") for reason in fused.reasons),
            fused.reasons,
        )


if __name__ == "__main__":
    unittest.main()
