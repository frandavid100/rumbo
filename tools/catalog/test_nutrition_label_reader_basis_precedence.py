import unittest

from mercadona_nutrition_label_manufacturer_interleave import _mercadona_basis


class NutritionLabelBasisPrecedenceTest(unittest.TestCase):
    def test_explicit_per_100ml_wins_over_unrelated_1009_malta_ocr(self):
        observed = """CERVEZA
1009 MALTA
INFORMACION NUTRICIONAL
por 100 ml
Valor energetico 167 kJ / 40 kcal
Grasas 0 g
Hidratos de carbono 3.0 g
Proteinas 0 g
"""
        self.assertEqual(_mercadona_basis(observed), "100_ml")

    def test_unrelated_inline_1009_malta_is_not_a_100g_basis(self):
        self.assertIsNone(_mercadona_basis("Ingredientes: agua, cebada. 1009 MALTA"))

    def test_explicit_and_standalone_100g_ocr_forms_remain_supported(self):
        self.assertEqual(_mercadona_basis("Valores medios por 1009"), "100_g")
        self.assertEqual(_mercadona_basis("Informacion nutricional\n1009\nValor energetico"), "100_g")

    def test_explicit_and_standalone_100ml_forms_remain_supported(self):
        self.assertEqual(_mercadona_basis("Valores medios por 100 ml"), "100_ml")
        self.assertEqual(_mercadona_basis("Informacion nutricional\n100 ml\nValor energetico"), "100_ml")


if __name__ == "__main__":
    unittest.main()
