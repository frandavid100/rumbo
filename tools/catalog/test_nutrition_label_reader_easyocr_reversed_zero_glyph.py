import unittest

from nutrition_label_reader import read_nutrition_label


class NutritionLabelReaderEasyOCRReversedZeroGlyphTest(unittest.TestCase):
    def test_zero_glyph_immediately_before_fat_row_with_saturates_subrow_is_total_fat_zero(self):
        observed = """INFORMACIÓN NUTRICIONAL
100 g
Valor
42 kJ
Energético
10 kcal
09
Grasas
delas cuales:
09
Saturadas
Hidratos de Carbono
1.1g
Proteínas
0.7g
Sal
0.88g
"""
        result = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition, {
            "calories": 10.0,
            "fat_g": 0.0,
            "carbohydrate_g": 1.1,
            "protein_g": 0.7,
        })

    def test_preceding_zero_glyph_without_saturates_structure_is_not_borrowed_as_fat(self):
        observed = """INFORMACIÓN NUTRICIONAL
100 g
Valor energético 10 kcal
09
Grasas
Hidratos de Carbono 1.1g
Proteínas 0.7g
Sal 0.88g
"""
        result = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertNotIn("fat_g", result.nutrition or {}, result)

    def test_bare_preceding_nine_is_not_repaired_to_zero(self):
        observed = """INFORMACIÓN NUTRICIONAL
100 g
Valor energético 91 kcal
9
Grasas
delas cuales:
0g
Saturadas
Hidratos de Carbono 10g
Proteínas 8g
Sal 0.2g
"""
        result = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertNotEqual((result.nutrition or {}).get("fat_g"), 0.0, result)


if __name__ == "__main__":
    unittest.main()
