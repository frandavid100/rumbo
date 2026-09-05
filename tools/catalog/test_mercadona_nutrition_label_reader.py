import unittest

from mercadona_nutrition_label_reader import read_nutrition_label


class MercadonaNutritionLabelReaderSafetyTest(unittest.TestCase):
    def test_bare_100g_and_serving_columns_are_review_without_partial_nutrition(self):
        # Observed PP-OCR layout from a Mercadona back label. The visual table has
        # one column per 100 g and another per 26 g serving, but OCR linearises the
        # column headings and then emits both values row by row. It can also split
        # the energy label around the numeric cells (`Valor ... Energético`). A
        # sequential label->next-number parser must not expose either column as
        # corroborating evidence for an OCR ensemble.
        observed = """100 g
26 g
sugeri
Valor
846 kJ
222 kJ
Pser
Energético/Energia
200 Kcal
53 Kcal
suger
2,6 g
0,7 g
Grasas/Lípidos
de las cuales/dos quais:
- Saturadas/Saturados
0,6 g
0,1 g
37 g
10 g
Hidratos de Carbono
de los cuales/dos quais:
5,6 g
1,5 g
- Azúcares/Açúcares
5,9 g
1,5 g
Fibra alimentaria/Fibra
1,1 g
4,3 g
Proteínas
1,0 g
0,3 g
Sal
"""
        result = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertIn("MULTIPLE_NUTRITION_COLUMNS", result.reasons)
        self.assertIsNone(result.nutrition)

    def test_conventional_bare_two_column_energy_layout_is_also_blocked(self):
        observed = """INFORMACIÓN NUTRICIONAL
100 g
26 g
sugerida
Valor energético
846 kJ
222 kJ
200 kcal
53 kcal
Grasas
2,6 g
0,7 g
Hidratos de carbono
37 g
9,6 g
Proteínas
4,3 g
1,0 g
Sal
1,0 g
0,3 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertIn("MULTIPLE_NUTRITION_COLUMNS", result.reasons)
        self.assertIsNone(result.nutrition)

    def test_single_bare_100g_column_remains_usable(self):
        observed = """INFORMACIÓN NUTRICIONAL
100 g
Valor energético
846 kJ
200 kcal
Grasas
2,6 g
Hidratos de carbono
37 g
Proteínas
4,3 g
Sal
1,0 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition, {
            "calories": 200.0,
            "fat_g": 2.6,
            "carbohydrate_g": 37.0,
            "protein_g": 4.3,
        })


if __name__ == "__main__":
    unittest.main()
