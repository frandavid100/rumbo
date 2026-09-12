import unittest

from nutrition_label_reader import read_nutrition_label


class SplitCarbohydrateLabelRegressionTest(unittest.TestCase):
    def test_doctr_split_hidratos_de_carbono_row_is_parsed(self):
        # Real docTR-style reading order observed for Mercadona product 35649:
        # the printed row label is split across lines, then followed by its
        # numeric cell. Whitespace inside the label must not make the value
        # disappear from ensemble evidence.
        observed = """INFORMACIÓN NUTRICIONAL
Valores medios por 100 g
Valor Energético
1679 kJ
Energia
395 kcal
Grasas/Lípidos
0 g
Hidratos de
Carbono
98 g
Proteínas
0 g
Sal
0 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition, {
            "calories": 395.0,
            "fat_g": 0.0,
            "carbohydrate_g": 98.0,
            "protein_g": 0.0,
        })

    def test_split_label_does_not_skip_arbitrary_prose(self):
        observed = """INFORMACIÓN NUTRICIONAL
Valores medios por 100 g
Valor Energético 1679 kJ / 395 kcal
Grasas 0 g
Hidratos de
NOTA DEL ENVASE
Carbono
98 g
Proteínas 0 g
Sal 0 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertIn("MISSING_CORE:carbohydrate_g", result.reasons)


if __name__ == "__main__":
    unittest.main()
