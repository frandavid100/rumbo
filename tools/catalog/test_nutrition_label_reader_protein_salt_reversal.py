import unittest

from nutrition_label_reader import read_nutrition_label


class NutritionLabelReaderProteinSaltReversalTest(unittest.TestCase):
    def test_value_before_protein_label_wins_when_forward_cell_is_salt(self):
        # Real PP-OCRv6 ordering for Mercadona product 24541. The printed
        # protein value is linearised immediately before `Proteínas`, while the
        # salt value follows that label before the standalone `Sal` row label.
        # The parser must not borrow 0.02 g of salt as protein.
        observed = """100g
Valor
1543 kJ
369 kcal
Energético/Energia
Grasas/Lípidos
1.5 g
de las cuales/dos quais:
- Saturadas/Saturados
1.1 g
Hidratos de Carbono
85g
de los cuales/dos quais:
- Azúcares/Açúcares
69 g
2.1 g
Proteínas
0.02g
Sal
"""
        result = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual((result.nutrition or {}).get("protein_g"), 2.1)
        self.assertNotEqual((result.nutrition or {}).get("protein_g"), 0.02)


if __name__ == "__main__":
    unittest.main()
