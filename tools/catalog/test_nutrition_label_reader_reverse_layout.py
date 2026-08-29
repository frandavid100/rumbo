import unittest

from nutrition_label_reader import read_nutrition_label


class NutritionLabelReaderReverseLayoutRegressionTest(unittest.TestCase):
    def test_ingredient_prose_is_not_bound_to_additive_number(self):
        observed = """100 g
Valor Energético/Energía 240 kcal
Grasas/Lípidos 15.7 g
Hidratos de Carbono 12.2 g
Ingredientes
proteínas de leite. sais de fusão (E-331. E-452. E-339). sal.
Proteínas
12.4 g
Sal 3.4 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.nutrition, {
            "calories": 240.0, "fat_g": 15.7,
            "carbohydrate_g": 12.2, "protein_g": 12.4,
        })

    def test_coherent_reversed_value_rows_can_complete_two_missing_macros(self):
        # Observed PP-OCRv6 layout on Mercadona product 51198. The table is
        # linearised with carbohydrate/protein values immediately before labels.
        observed = """100 g
Valor Energético/Energía 240 kcal
Grasas/Lípidos
15.7 g
11 g
- Saturadas/Saturados
12.2 g
Hidratos de Carbono
5.3 g
- Azúcares/Açúcares
12.4 g
Proteínas
Sal
3.4 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.nutrition, {
            "calories": 240.0, "fat_g": 15.7,
            "carbohydrate_g": 12.2, "protein_g": 12.4,
        })

    def test_incoherent_reversed_value_rows_are_not_used(self):
        # A normal/garbled reading order can put the previous sub-row value
        # immediately before the next label. Energy coherence must prevent it
        # from becoming usable nutrition.
        observed = """100 g
Valor Energético/Energía 200 kcal
Grasas/Lípidos
15.7 g
11 g
- Saturadas/Saturados
30 g
Hidratos de Carbono
20 g
- Azúcares/Açúcares
40 g
Proteínas
Sal
3.4 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertIsNone(r.nutrition.get("carbohydrate_g") if r.nutrition else None)
        self.assertIsNone(r.nutrition.get("protein_g") if r.nutrition else None)

    def test_single_missing_macro_is_not_backfilled_from_preceding_row(self):
        observed = """100 g
Valor Energético/Energía 240 kcal
Grasas/Lípidos 15.7 g
Hidratos de Carbono 12.2 g
de los cuales azúcares
5.3 g
Proteínas
Sal 3.4 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertIn("MISSING_CORE:protein_g", r.reasons)


if __name__ == "__main__":
    unittest.main()
