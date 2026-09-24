import unittest

from mercadona_nutrition_label_manufacturer_interleave import read_nutrition_label


class MercadonaShiftedSubrowGuardTest(unittest.TestCase):
    def test_shifted_saturated_fat_and_salt_cells_are_not_exposed_as_core_macros(self):
        # Observed PP-OCRv6 reading for first-party product 3680. Visual column
        # order puts the true total-fat/protein cells immediately before their
        # row labels, while the following 2.2 g and 0.20 g cells belong to the
        # saturated-fat and salt rows. The safety guard must withhold the falsely
        # attached values rather than invent/rescue replacements.
        observed = """Información Nutricional por 100g.
de producto:
562 KJ
Valor Energético:
134 kcal
6 g
Grasas:
2.2 g
de las cuales saturadas:
<0.1 g
Hidratos de carbono:
<0.1 g
de los cuales azúcares:
19 g
Proteinas:
0.20 g
Sal:
Fabricado por:
HIJOS DE JUAN PUJANTE S.A.
"""
        result = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(result.status, "REVIEW")
        self.assertEqual(result.basis, "100_g")
        self.assertEqual((result.nutrition or {}).get("calories"), 134.0)
        self.assertNotIn("fat_g", result.nutrition or {})
        self.assertNotIn("protein_g", result.nutrition or {})
        self.assertTrue(any(reason == "MERCADONA_SHIFTED_SUBROW_VALUE_WITHHELD:fat_g" for reason in result.reasons), result)
        self.assertTrue(any(reason == "MERCADONA_SHIFTED_SUBROW_VALUE_WITHHELD:protein_g" for reason in result.reasons), result)

    def test_conventional_rows_remain_declared(self):
        observed = """Información nutricional por 100 g
Valor energético 711 kJ / 170 kcal
Grasas 10 g
de las cuales saturadas 2 g
Hidratos de carbono 0.8 g
de los cuales azúcares 0.5 g
Proteínas 19 g
Sal 0.3 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.nutrition, {
            "calories": 170.0,
            "fat_g": 10.0,
            "carbohydrate_g": 0.8,
            "protein_g": 19.0,
        })


if __name__ == "__main__":
    unittest.main()
