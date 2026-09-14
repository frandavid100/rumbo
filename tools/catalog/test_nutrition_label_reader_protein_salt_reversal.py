import unittest

from nutrition_label_reader import read_nutrition_label


class NutritionLabelReaderProteinSaltReversalTest(unittest.TestCase):
    def test_value_before_protein_label_is_review_evidence_when_forward_cell_is_salt(self):
        # Real PP-OCRv6 ordering for Mercadona product 24541. The printed
        # protein value is linearised immediately before `Proteínas`, while the
        # salt value follows that label before the standalone `Sal` row label.
        # Never borrow 0.02 g of salt as protein. The reversed protein value may
        # be retained only as REVIEW evidence for independent corroboration.
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
        self.assertEqual(result.status, "REVIEW")
        self.assertEqual(result.basis, "100_g")
        self.assertEqual((result.nutrition or {}).get("protein_g"), 2.1)
        self.assertNotEqual((result.nutrition or {}).get("protein_g"), 0.02)
        self.assertIn("SINGLE_REVERSED_MACRO_CANDIDATE:protein_g", result.reasons)

    def test_normal_sugar_protein_salt_order_remains_declared(self):
        # A single sugar value immediately before the protein row is ordinary
        # table ordering and must not be mistaken for the two-value reversal.
        observed = """Información nutricional por 100 g
Valor energético 1543 kJ / 369 kcal
Grasas 1.5 g
de las cuales saturadas 1.1 g
Hidratos de carbono 85 g
de los cuales azúcares
69 g
Proteínas
2.1 g
Sal
0.02 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.nutrition["protein_g"], 2.1)


if __name__ == "__main__":
    unittest.main()
