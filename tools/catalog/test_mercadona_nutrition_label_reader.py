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

    def test_complete_single_column_value_before_label_layout_is_rescued(self):
        # Observed PP-OCR layout for Mercadona product 29130 (Harina de arroz).
        # All three core macro values are explicit standalone gram rows immediately
        # before their labels. The sequential parse binds salt (0.01 g) to protein,
        # while the complete reversed tuple is 354 kcal / 1.2 / 79 / 7 and is
        # near-exactly energy coherent. This is direct OCR evidence, not inference.
        observed = """100 g
1500 kJ
Valor
354 kcal
Energético
1.2 g
Grasas
de las cuales:
0.2g
-Saturadas
79 g
Hidratos de Carbono
de los cuales:
0.5g
-Azúcares
1g
Fibra alimentaria
7g
Proteínas
0.01g
Sal
500
g
Peso Neto:
"""
        result = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition, {
            "calories": 354.0,
            "fat_g": 1.2,
            "carbohydrate_g": 79.0,
            "protein_g": 7.0,
        })
        self.assertIn("VALUE_BEFORE_LABEL_RESCUED", result.reasons)

    def test_value_before_label_layout_is_not_rescued_without_energy_coherence(self):
        observed = """100 g
1500 kJ
Valor
354 kcal
Energético
1.2 g
Grasas
de las cuales:
0.2g
-Saturadas
40 g
Hidratos de Carbono
de los cuales:
0.5g
-Azúcares
1g
Fibra alimentaria
7g
Proteínas
0.01g
Sal
"""
        result = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertNotEqual(result.status, "DECLARED", result)
        self.assertNotIn("VALUE_BEFORE_LABEL_RESCUED", result.reasons)


if __name__ == "__main__":
    unittest.main()
