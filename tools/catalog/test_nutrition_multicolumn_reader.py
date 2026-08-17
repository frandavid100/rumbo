import unittest

from nutrition_multicolumn_reader import read_two_column_nutrition, select_column


TUNA = """INFORMACION NUTRICIONAL
Por 100 g de peso neto
Por 100 g de peso escurrido
Valor Energético 333 kJ / 79 kcal 417 kJ / 98 kcal
Grasas 0,6 g 1,2 g
De las cuales saturadas 0,2 g 0,4 g
Hidratos de Carbono <0,5 g 0,9 g
De los cuales azúcares <0,5 g <0,5 g
Proteínas 18 g 21 g
Sal 1,1 g 1,1 g
"""


class MultiColumnNutritionTest(unittest.TestCase):
    def test_returns_both_columns_without_implicit_choice(self):
        columns = read_two_column_nutrition(TUNA)
        self.assertIsNotNone(columns)
        net, drained = columns
        self.assertEqual(net.key, "NET_WEIGHT")
        self.assertEqual(net.nutrition["calories"], 79)
        self.assertEqual(net.nutrition["protein_g"], 18)
        self.assertEqual(drained.key, "DRAINED_WEIGHT")
        self.assertEqual(drained.nutrition["calories"], 98)
        self.assertEqual(drained.nutrition["protein_g"], 21)
        self.assertIsNone(select_column(columns, policy=None))

    def test_explicit_policy_selects_one_column(self):
        columns = read_two_column_nutrition(TUNA)
        selected = select_column(columns, policy="DRAINED_WEIGHT")
        self.assertEqual(selected.nutrition["fat_g"], 1.2)
        self.assertEqual(selected.nutrition["carbohydrate_g"], 0.9)


if __name__ == "__main__":
    unittest.main()
