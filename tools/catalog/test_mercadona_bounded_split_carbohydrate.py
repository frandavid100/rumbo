import unittest

from nutrition_label_reader import read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


BOUNDED_SPLIT = """Información nutricional por 100 g
Valor energético 669 kJ / 160 kcal
Grasas 9.8 g
Hidratos de
<0.5 g
Carbono
Proteínas 17.9 g
Sal 0.2 g
"""

EXACT_SPLIT = BOUNDED_SPLIT.replace("<0.5 g", "0.5 g")


class MercadonaBoundedSplitCarbohydrateTest(unittest.TestCase):
    def test_split_label_bound_vetoes_two_exact_ocr_misreads(self):
        """Regression for Mercadona product 25184.

        A credible OCR family preserving `Hidratos de / <0.5 g / Carbono`
        must keep carbohydrate non-exact even if two other independent OCR
        families lose the inequality glyph and agree on 0.5 g. No bound is
        converted into an exact macro and the ensemble must stay REVIEW.
        """
        bounded = read_nutrition_label(BOUNDED_SPLIT, extraction_confidence=.98)
        paddle = read_nutrition_label(EXACT_SPLIT, extraction_confidence=.97)
        tesseract = read_nutrition_label(EXACT_SPLIT, extraction_confidence=.94)

        fused = fuse_ocr_readings((
            ParsedOCRReading("easyocr", bounded, .98, "easyocr"),
            ParsedOCRReading("paddleocr", paddle, .97, "paddleocr"),
            ParsedOCRReading("tesseract-psm11", tesseract, .94, "tesseract"),
        ))

        self.assertEqual(fused.status, "REVIEW", fused)
        self.assertIsNone((fused.nutrition or {}).get("carbohydrate_g"), fused)
        self.assertTrue(
            any(
                reason.startswith("OCR_BOUNDED_CORE_VALUE:carbohydrate_g")
                for reason in fused.reasons
            ),
            fused.reasons,
        )


if __name__ == "__main__":
    unittest.main()
