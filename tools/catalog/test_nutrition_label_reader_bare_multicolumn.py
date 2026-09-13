import unittest

from nutrition_label_reader import read_nutrition_label


class BarePer100MultiColumnRegressionTest(unittest.TestCase):
    def test_repeated_standalone_100g_headings_block_parallel_columns(self):
        # Real Mercadona OCR shape observed for product 2632. The printed label
        # has two nutrition columns (Carpaccio and Queso), but docTR linearises
        # the column headings as two standalone `100 g` rows rather than
        # `Por 100 g`. A row-oriented parser must fail closed instead of mixing
        # values from the two products.
        observed = """INFORMACIÓN NUTRICIONAL
Carpaccio
Queso / Queijo
100 g
100 g
Valor energético / Energia
455 kJ
1.671 kJ
108 kcal 402 kcal
Grasas / Lípidos
2.0 g
30 g
De las cuales saturadas
1.0 g
20 g
Hidratos de carbono
2.2 g
0 g
Proteínas
20 g
32 g
Sal
2.8 g
1.6 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertIn("MULTIPLE_NUTRITION_COLUMNS", result.reasons)
        self.assertIsNone(result.nutrition)

    def test_single_standalone_100g_heading_remains_eligible(self):
        observed = """INFORMACIÓN NUTRICIONAL
100 g
Valor energético 767 kJ / 184 kcal
Grasas 12 g
Hidratos de carbono 2 g
Proteínas 17 g
Sal 0.42 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition, {
            "calories": 184.0,
            "fat_g": 12.0,
            "carbohydrate_g": 2.0,
            "protein_g": 17.0,
        })


if __name__ == "__main__":
    unittest.main()
