import unittest

from nutrition_label_reader import normalize_text, read_nutrition_label


class NutritionLabelReaderEasyOCRZeroGlyphTest(unittest.TestCase):
    def test_table_border_prefix_and_terminal_9_unit_keep_zero_macros(self):
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 ml
Valor energético 00 kcal
[Grasas:
09
[Hidratos de carbono:
09
[Proteínas:
09
Sal 0 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.basis, "100_ml")
        self.assertEqual(r.nutrition, {
            "calories": 0.0,
            "fat_g": 0.0,
            "carbohydrate_g": 0.0,
            "protein_g": 0.0,
        })

    def test_easyocr_coca_cola_crasas_row_keeps_zero_total_fat(self):
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 ml
Valor energético 180 kJ / 42 kcal
Crasas;
09
Hidratos de carbono:
10.6 g
Proteínas:
0 g
Sal 0 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.basis, "100_ml")
        self.assertEqual(r.nutrition, {
            "calories": 42.0,
            "fat_g": 0.0,
            "carbohydrate_g": 10.6,
            "protein_g": 0.0,
        })

    def test_crasas_repair_is_standalone_only(self):
        self.assertEqual(normalize_text("Crasas;"), "Grasas;")
        self.assertEqual(normalize_text("Crasas:"), "Grasas:")
        self.assertEqual(normalize_text("Crasas"), "Grasas")
        self.assertEqual(normalize_text("Crasas a la brasa"), "Crasas a la brasa")

    def test_crasas_in_prose_cannot_supply_missing_fat(self):
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g
Valor energético 420 kJ / 100 kcal
Crasas a la brasa
Hidratos de carbono 20 g
Proteínas 5 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertIn("MISSING_CORE:fat_g", r.reasons)

    def test_bare_nine_without_unit_glyph_is_not_repaired_to_zero(self):
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g
Valor energético 153 kcal
Grasas 9
Hidratos de carbono 10 g
Proteínas 8 g
Sal 0 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual((r.nutrition or {}).get("fat_g"), 9.0, r)


if __name__ == "__main__":
    unittest.main()
