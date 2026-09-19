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

    def test_incoherent_kj_kcal_pair_is_not_accepted_even_if_macros_fit_kcal(self):
        observed = """Información nutricional por 100 ml
Valor energético 1278 kJ / 30.8 kcal
Grasas 0 g
Hidratos de carbono 7.7 g
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


if __name__ == "__main__":
    unittest.main()
