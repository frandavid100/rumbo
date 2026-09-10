import unittest

from mercadona_nutrition_label_structural_repair import read_nutrition_label


class MercadonaNutritionLabelStructuralRepairTest(unittest.TestCase):
    def test_full_value_before_label_layout_uses_explicit_preceding_protein_cell(self):
        observed = """Información nutricional
por 100 ml
195 kJ (46 kcal)
Valor energético
0g
Grasas
0g
de las cuales Saturadas
11g
Hidratos de Carbono
11g
de los cuales Azúcares
0g
Proteinas
0.1 g
Sal
"""
        result = read_nutrition_label(observed, extraction_confidence=.96)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.basis, "100_ml")
        self.assertEqual(result.nutrition, {
            "calories": 46.0,
            "fat_g": 0.0,
            "carbohydrate_g": 11.0,
            "protein_g": 0.0,
        })
        self.assertIn("FULL_VALUE_BEFORE_LABEL_STRUCTURE", result.reasons)

    def test_observed_easyocr_row_typos_can_supply_partial_zero_protein_evidence(self):
        observed = """Información nutricional
09
Grasas
0g
de las cuales Saturadas
11 9
Hidralos de Carbono
119
de los cuales Azúcares
09
Proleínas
O.1g
Sal
"""
        result = read_nutrition_label(observed, extraction_confidence=.71)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertEqual((result.nutrition or {}).get("protein_g"), 0.0)
        self.assertEqual((result.nutrition or {}).get("fat_g"), 0.0)
        self.assertEqual((result.nutrition or {}).get("carbohydrate_g"), 11.0)
        self.assertIn("FULL_VALUE_BEFORE_LABEL_PARTIAL_EVIDENCE", result.reasons)

    def test_inline_bare_nine_after_proleinas_is_not_promoted_to_protein(self):
        # Exact Tesseract failure mode on product 27905: the printed zero is lost
        # and only a g-like glyph remains. Recognising the typo must not invent 9 g.
        observed = """Información nutricional por 100 ml
Valor energético 195 kJ (46 kcal)
Grasas 0 9
Hidratos de Carbono 11 9
Proleinas 9 S
Sal 0.1 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertNotIn("protein_g", result.nutrition or {})

    def test_normal_forward_rows_are_unchanged(self):
        observed = """Información nutricional por 100 g
Valor energético 711 kJ / 170 kcal
Grasas 10 g
Hidratos de carbono 0.8 g
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
        self.assertNotIn("FULL_VALUE_BEFORE_LABEL_STRUCTURE", result.reasons)


if __name__ == "__main__":
    unittest.main()
