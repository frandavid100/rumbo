import unittest

from nutrition_label_reader import read_nutrition_label


class NutritionLabelReaderLowKcalPairTest(unittest.TestCase):
    def test_coherent_kj_pair_allows_single_digit_decimal_kcal(self):
        observed = """Información nutricional por 100 ml
Valor energético 12 kJ / 2.9 kcal
Grasas 0 g
Hidratos de carbono 0.1 g
Proteínas 0 g
Sal 0.01 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.basis, "100_ml")
        self.assertEqual(r.nutrition, {
            "calories": 2.9,
            "fat_g": 0.0,
            "carbohydrate_g": 0.1,
            "protein_g": 0.0,
        })

    def test_incoherent_single_digit_kj_kcal_pair_is_not_accepted_even_if_macros_fit_kcal(self):
        observed = """Información nutricional por 100 ml
Valor energético 127.8 kJ / 3.08 kcal
Grasas 0 g
Hidratos de carbono 0.77 g
Proteínas 0 g
Sal 0.01 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertIsNone((r.nutrition or {}).get("calories"), r)
        self.assertIn("MISSING_CORE:calories", r.reasons)

    def test_standalone_single_digit_decimal_kcal_remains_fail_closed(self):
        observed = """Información nutricional por 100 ml
Valor energético 2.9 kcal
Grasas 0 g
Hidratos de carbono 0.1 g
Proteínas 0 g
Sal 0.01 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertIsNone((r.nutrition or {}).get("calories"), r)
        self.assertIn("MISSING_CORE:calories", r.reasons)

    def test_parallel_per_100_and_serving_energy_columns_are_explicitly_blocked(self):
        observed = """Información nutricional
250 ml
100 ml
Valor
30 kJ
12 kJ
Energético
7.2 kcal
2.9 kcal
Grasas
0.0 g
0.0 g
Hidratos de Carbono
0.2 g
0.1 g
Proteínas
0.0 g
0.0 g
Sal
0.23 g
0.09 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertEqual(r.basis, "100_ml")
        self.assertIsNone(r.nutrition)
        self.assertIn("MULTIPLE_NUTRITION_COLUMNS", r.reasons)

    def test_post_table_package_quantity_does_not_create_parallel_column(self):
        observed = """Información nutricional por 100 ml
Valor energético 12 kJ / 2.9 kcal
Grasas 0 g
Hidratos de carbono 0.1 g
Proteínas 0 g
Sal 0.01 g
250 ml
"""
        r = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertNotIn("MULTIPLE_NUTRITION_COLUMNS", r.reasons)


if __name__ == "__main__":
    unittest.main()
