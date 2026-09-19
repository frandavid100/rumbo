import unittest

from nutrition_label_reader import read_nutrition_label


class NutritionLabelReaderReversedFatNoUnitTest(unittest.TestCase):
    def test_numeric_only_total_fat_before_label_is_used_only_with_saturated_row_structure(self):
        # Real PP-OCRv6 crop ordering observed for Mercadona product 86395:
        # the printed total-fat value loses its `g` glyph and is emitted on the
        # line before `Grasas`, while the saturated-fat value is emitted after
        # `Grasas` and immediately before the OCR-corrupted `Baturadas` label.
        # The parser must preserve the observed 8.9 rather than silently treating
        # 3.20 as total fat. The resulting tuple is deliberately still REVIEW:
        # 182 kcal is not coherent with 8.9 g fat + 0 g carbs + 18 g protein, so
        # the safety gate must continue to reject it rather than relax tolerance.
        observed = """100 g
Valor energético 635 kJ / 182 kcal
8.9
Grasas
3.20
- Baturadas
Hidratos de carbono 0 g
Proteínas 18 g
Sal 0.15 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition, {
            "calories": 182.0,
            "fat_g": 8.9,
            "carbohydrate_g": 0.0,
            "protein_g": 18.0,
        })
        self.assertTrue(
            any(reason.startswith("ENERGY_MACRO_MISMATCH:") for reason in result.reasons),
            result,
        )

    def test_bare_value_before_fat_label_does_not_override_without_saturated_row_proof(self):
        observed = """100 g
Valor energético 635 kJ / 182 kcal
8.9
Grasas 8.8 g
Hidratos de carbono 0 g
Proteínas 18 g
Sal 0.15 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual((result.nutrition or {}).get("fat_g"), 8.8)
        self.assertNotEqual((result.nutrition or {}).get("fat_g"), 8.9)


if __name__ == "__main__":
    unittest.main()
