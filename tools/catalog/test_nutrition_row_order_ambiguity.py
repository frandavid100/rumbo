import unittest

from mercadona_nutrition_label_reader import read_nutrition_label


class NutritionRowOrderAmbiguityTest(unittest.TestCase):
    def test_value_before_label_competing_with_following_row_is_review_without_usable_values(self):
        # Observed PP-OCRv6 output for Mercadona product 29130 (harina de arroz).
        # The numeric column was linearised before its labels near the bottom of
        # the table: 7 g belongs to Proteinas and 0.01 g belongs to Sal. A naive
        # label->next-number parser instead binds protein=0.01 and can still pass
        # a broad energy tolerance on a carbohydrate-heavy product.
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
        self.assertEqual(r.status, "REVIEW", r)
        self.assertIn("AMBIGUOUS_VALUE_BEFORE_LABEL:protein_g", r.reasons)
        # Ambiguous row ordering is not allowed to corroborate another OCR
        # engine's values in the ensemble. Keep the text/reason for audit, but
        # expose no nutrition tuple as usable evidence.
        self.assertIsNone(r.nutrition)

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
