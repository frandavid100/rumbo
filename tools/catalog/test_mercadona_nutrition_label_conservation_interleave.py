import unittest

from mercadona_nutrition_label_reader import read_nutrition_label


class MercadonaNutritionLabelConservationInterleaveTest(unittest.TestCase):
    def test_interleaved_conservation_heading_does_not_truncate_reversed_core_rows(self):
        # Reduced from the live PP-OCRv6 reading for Mercadona product 21649.
        # The visual table is single-column, but OCR inserts the packaging
        # CONSERVACIÓN heading after the total-fat row and emits each remaining
        # macro value immediately before its row label. The Mercadona-specific
        # value-before-label rescue is safe only if _nutrition_block keeps the
        # explicit core rows that follow the interleaved packaging heading.
        observed = """100 g
Valor
1004 kJ
Energético/Energia 240 kcal
Abrir a embalagem e consumir.
12 g
Grasas/Lípidos
CONSERVACIÓN/CONSERVAÇÃO
de las cuales/dos quais:
- Saturadas/Saturados 2.6 g
Conservar em local fresco e seco.
26 g
Hidratos de Carbono
500 g
Peso Neto/Líquido
de los cuales/dos quais:
- Azúcares/Açúcares 2.0 g
6.7 g
Proteínas
Sal 1.1 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.978)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.basis, "100_g")
        self.assertEqual(r.nutrition, {
            "calories": 240.0,
            "fat_g": 12.0,
            "carbohydrate_g": 26.0,
            "protein_g": 6.7,
        })
        self.assertIn("VALUE_BEFORE_LABEL_RESCUED", r.reasons)

    def test_interleaved_conservation_does_not_make_two_column_table_usable(self):
        # Reduced from the current Carpaccio de vacuno label (product 2632).
        # Two nutrition columns are visibly interleaved. Keeping text after the
        # packaging heading must not make this ambiguous table automatically usable.
        observed = """100 g
100 g
Valor Energético/Energia
455 kJ
1.671 kJ
108 kcal
402 kcal
Grasas/Lípidos
2.0 g
30 g
de las cuales/dos quais:
- Saturadas/Saturados
1.0 g
20 g
Hidratos de
2.2 g
0 g
CONSERVACIÓN/CONSERVAÇÃO
Carbono
de los cuales/dos quais:
- Azúcares/Açúcares
0.8 g
0 g
Proteínas
20 g
32 g
Sal
2.8 g
1.6 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.91)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertFalse(r.declared_usable)


if __name__ == "__main__":
    unittest.main()
