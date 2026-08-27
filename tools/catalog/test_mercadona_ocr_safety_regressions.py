import unittest

from nutrition_label_reader import read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


class MercadonaOCRSafetyRegressionsTest(unittest.TestCase):
    def test_impossible_partial_calories_do_not_enter_ensemble_evidence(self):
        # Observed Tesseract failure on a real Mercadona back label: the printed
        # `442 kJ / 106 kcal` was linearised as `442/4106`, while other rows
        # remained incomplete. Partial parses must reject the impossible 4106
        # before the value can contaminate an otherwise valid ensemble.
        observed = """Información nutricional por 100 g
Valor energético 442 kJ / 4106 kcal
Grasas 1.8 g
Hidratos de carbono
Proteínas 22 g
Sal 0.16 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(result.status, "REVIEW")
        self.assertNotIn("calories", result.nutrition or {})
        self.assertIn("IMPOSSIBLE_CALORIES", result.reasons)

    def test_impossible_partial_macro_does_not_enter_ensemble_evidence(self):
        observed = """Información nutricional por 100 g
Valor energético 442 kJ / 106 kcal
Grasas 1.8 g
Hidratos de carbono
Proteínas 222 g
Sal 0.16 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(result.status, "REVIEW")
        self.assertNotIn("protein_g", result.nutrition or {})
        self.assertIn("IMPOSSIBLE_PROTEIN_G", result.reasons)

    def test_one_explicit_basis_is_enough_when_all_core_fields_are_independently_corroborated(self):
        # Observed on Mercadona product 2689: Paddle reads the explicit `100 g`
        # basis and all four macros, while Tesseract independently reads the same
        # four values but loses only the basis glyph. There is no competing basis.
        with_basis = read_nutrition_label("""Información nutricional por 100 g
Valor energético 711 kJ / 170 kcal
Grasas 10 g
Hidratos de carbono 0.8 g
Proteínas 19 g
Sal 0.3 g
""", extraction_confidence=.98)
        without_basis = read_nutrition_label("""Información nutricional
Valor energético 711 kJ / 170 kcal
Grasas 10 g
Hidratos de carbono 0.8 g
Proteínas 19 g
Sal 0.3 g
""", extraction_confidence=.96)
        self.assertEqual(with_basis.status, "DECLARED")
        self.assertEqual(without_basis.status, "REVIEW")

        fused = fuse_ocr_readings((
            ParsedOCRReading("paddleocr:visual-region", with_basis, .98, "paddleocr"),
            ParsedOCRReading("tesseract-psm11:visual-region", without_basis, .96, "tesseract"),
        ))
        self.assertEqual(fused.status, "DECLARED", fused)
        self.assertEqual(fused.basis, "100_g")
        self.assertEqual(fused.corroborated_fields, 4)
        self.assertEqual(fused.independent_engine_families, 2)

    def test_conflicting_explicit_bases_still_force_review(self):
        per_100g = read_nutrition_label("""Información nutricional por 100 g
Valor energético 711 kJ / 170 kcal
Grasas 10 g
Hidratos de carbono 0.8 g
Proteínas 19 g
Sal 0.3 g
""", extraction_confidence=.98)
        per_100ml = read_nutrition_label("""Información nutricional por 100 ml
Valor energético 711 kJ / 170 kcal
Grasas 10 g
Hidratos de carbono 0.8 g
Proteínas 19 g
Sal 0.3 g
""", extraction_confidence=.98)
        fused = fuse_ocr_readings((
            ParsedOCRReading("paddleocr", per_100g, .98, "paddleocr"),
            ParsedOCRReading("tesseract", per_100ml, .98, "tesseract"),
        ))
        self.assertEqual(fused.status, "REVIEW")
        self.assertIn("OCR_BASIS_CONFLICT", fused.reasons)


if __name__ == "__main__":
    unittest.main()
