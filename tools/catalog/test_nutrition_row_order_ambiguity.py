import unittest

from mercadona_nutrition_label_reader import read_nutrition_label


class NutritionRowOrderAmbiguityTest(unittest.TestCase):
    def test_complete_value_before_label_pattern_is_rescued_without_borrowing_following_row(self):
        # Observed PP-OCRv6 output for Mercadona product 29130 (harina de arroz).
        # The entire core macro column is linearised before its labels: 1.2 g ->
        # Grasas, 79 g -> Hidratos and 7 g -> Proteínas. The following 0.01 g is
        # salt. Because all three main rows expose the same explicit standalone
        # value-before-label layout and the resulting tuple is near-exactly energy
        # coherent, the parser can bind the direct OCR values without inference.
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
Peso Neto:"""
        r = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.nutrition, {
            "calories": 354.0,
            "fat_g": 1.2,
            "carbohydrate_g": 79.0,
            "protein_g": 7.0,
        })
        self.assertIn("VALUE_BEFORE_LABEL_RESCUED", r.reasons)

    def test_normal_label_then_value_layout_remains_declared(self):
        observed = """100 g
Valor Energético 354 kcal
Grasas 1.2 g
de las cuales saturadas 0.2 g
Hidratos de Carbono 79 g
de los cuales azúcares 0.5 g
Fibra alimentaria 1 g
Proteínas 7 g
Sal 0.01 g"""
        r = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.nutrition, {
            "calories": 354.0,
            "fat_g": 1.2,
            "carbohydrate_g": 79.0,
            "protein_g": 7.0,
        })


if __name__ == "__main__":
    unittest.main()
