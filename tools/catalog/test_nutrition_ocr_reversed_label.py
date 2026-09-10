from __future__ import annotations

import unittest

from nutrition_ocr_reversed_label import reversed_carbohydrate_value


class ReversedCarbohydrateValueTests(unittest.TestCase):
    def test_extracts_literal_value_from_exact_reversed_row_label(self):
        text = """100g
61 kJ
15 kcal
Valor
Energético
0.1g
Grasas
1.6g
Carbono
de
Hidratos
1.3g
Proteínas
"""
        self.assertEqual(reversed_carbohydrate_value(text), 1.6)

    def test_accepts_observed_ocr_glyph_substitution(self):
        text = """1009
1,6 9
Carbono
de
Hidratos
"""
        self.assertEqual(reversed_carbohydrate_value(text), 1.6)

    def test_rejects_inequality(self):
        text = """< 1.6 g
Carbono
de
Hidratos
"""
        self.assertIsNone(reversed_carbohydrate_value(text))

    def test_rejects_missing_unit(self):
        text = """1.6
Carbono
de
Hidratos
"""
        self.assertIsNone(reversed_carbohydrate_value(text))

    def test_does_not_match_normal_row_order(self):
        text = """Hidratos
de
Carbono
1.6 g
"""
        self.assertIsNone(reversed_carbohydrate_value(text))

    def test_does_not_borrow_value_across_intervening_prose(self):
        text = """1.6 g
valor orientativo
Carbono
de
Hidratos
"""
        self.assertIsNone(reversed_carbohydrate_value(text))


if __name__ == "__main__":
    unittest.main()
