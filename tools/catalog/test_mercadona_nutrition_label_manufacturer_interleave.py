import unittest

from mercadona_nutrition_label_manufacturer_interleave import read_nutrition_label


class MercadonaNutritionLabelManufacturerInterleaveTest(unittest.TestCase):
    def test_live_21649_manufacturer_line_between_protein_value_and_label(self):
        # Reduced from fresh PP-OCRv6 evidence for Mercadona product 21649.
        # OCR preserves every core value but inserts a bilingual manufacturer
        # line between the printed protein cell and the Proteínas row label.
        observed = """100 g
Valor
1004 kJ
Energético/Energia 240 kcal
12 g
Grasas/Lípidos
de las cuales/dos quais:
- Saturadas/Saturados 2.6 g
26 g
Hidratos de Carbono
500 g
Peso Neto/Líquido
de los cuales/dos quais:
- Azúcares/Açúcares 2.0 g
6.7 g
Fabricado/Producido por: DELICIAS CORUÑA. S.L.
Proteínas
Sal 1.1 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.978)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition, {
            "calories": 240.0,
            "fat_g": 12.0,
            "carbohydrate_g": 26.0,
            "protein_g": 6.7,
        })
        self.assertIn(
            "MERCADONA_MANUFACTURER_INTERLEAVED_VALUE_BEFORE_LABEL_STRUCTURE",
            result.reasons,
        )

    def test_does_not_skip_arbitrary_prose_between_protein_value_and_label(self):
        observed = """100 g
Valor energético 240 kcal
12 g
Grasas
26 g
Hidratos de Carbono
6.7 g
Lote: ABC123
Proteínas
Sal 1.1 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertNotEqual(result.status, "DECLARED", result)
        self.assertFalse(result.declared_usable)
        self.assertNotIn(
            "MERCADONA_MANUFACTURER_INTERLEAVED_VALUE_BEFORE_LABEL_STRUCTURE",
            result.reasons,
        )

    def test_does_not_override_multiple_nutrition_columns(self):
        observed = """100 g
100 g
Valor Energético/Energia
455 kJ
1.671 kJ
108 kcal
402 kcal
2.0 g
Grasas/Lípidos
30 g
2.2 g
Hidratos de Carbono
0 g
20 g
Fabricado/Producido por: EJEMPLO S.L.
Proteínas
32 g
Sal 1.6 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertFalse(result.declared_usable)


if __name__ == "__main__":
    unittest.main()
