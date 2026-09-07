import unittest

from nutrition_label_reader import read_nutrition_label


class NutritionLabelReaderEasyOCRZeroGlyphTest(unittest.TestCase):
    def test_table_border_prefix_and_terminal_9_unit_keep_zero_macros(self):
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 ml
Valor energético 00 kcal
[Grasas:
09
[Hidratos de carbono:
09
[Proteínas:
09
Sal 0 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.basis, "100_ml")
        self.assertEqual(r.nutrition, {
            "calories": 0.0,
            "fat_g": 0.0,
            "carbohydrate_g": 0.0,
            "protein_g": 0.0,
        })

    def test_bare_nine_without_unit_glyph_is_not_repaired_to_zero(self):
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g
Valor energético 153 kcal
Grasas 9
Hidratos de carbono 10 g
Proteínas 8 g
Sal 0 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual((r.nutrition or {}).get("fat_g"), 9.0, r)


if __name__ == "__main__":
    unittest.main()
