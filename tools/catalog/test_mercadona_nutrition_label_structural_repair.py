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

    def test_two_reversed_protein_cells_expose_only_unique_energy_coherent_value(self):
        # Real PP-OCRv6 ordering for product 4491. The visual table has per-100-g
        # and whole-pack columns; OCR emitted both protein cells immediately before
        # the row label. 5.9 g is coherent with the already-read 100-g tuple while
        # 21 g is the 350-g pack value and is not. Keep the recovered field REVIEW
        # evidence so a separate OCR family must corroborate it before promotion.
        observed = """100 g
Valor Energético/Energía 686 kJ 165 kcal
Grasas/Lípidos
10g
de las cuales Saturadas
4.4g
Hidratos de Carbono
12g
de los cuales Azúcares
2.8g
Fibra alimentaria/Fibra
1.5g
5.3g
5.9g
21g
Proteínas
Sal
0.8g
2.8g
"""
        result = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition, {
            "calories": 165.0,
            "fat_g": 10.0,
            "carbohydrate_g": 12.0,
            "protein_g": 5.9,
        })
        self.assertIn("SINGLE_REVERSED_MACRO_CANDIDATE:protein_g", result.reasons)
        self.assertIn("MERCADONA_TWO_CELL_VALUE_BEFORE_LABEL_EVIDENCE:protein_g", result.reasons)

    def test_two_reversed_cells_are_not_chosen_when_energy_cannot_disambiguate(self):
        observed = """Información nutricional por 100 g
Valor energético 100 kcal
Grasas 5 g
Hidratos de Carbono 10 g
3 g
4 g
Proteínas
Sal 0.2 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertNotIn("protein_g", result.nutrition or {})
        self.assertIn("MISSING_CORE:protein_g", result.reasons)
        self.assertNotIn("MERCADONA_TWO_CELL_VALUE_BEFORE_LABEL_EVIDENCE:protein_g", result.reasons)

    def test_interleaved_trailing_macro_labels_expose_only_observed_cells_as_review_evidence(self):
        # Product 6063 docTR ordering: the package-text column is emitted first,
        # then the nutrition row label at the end of the same OCR line. Numeric
        # cells remain on their own following lines. Splitting only those three
        # observed row labels must not invent or alter a numeric value; this
        # structural repair stays REVIEW so another OCR family must corroborate it.
        observed = """INFORMACIÓN NUTRICIONAL
Valores medios / médios
Por 100g
Porción / Porção
texto de ingredientes Grasas / Lípidos
179
15g
texto de ingredientes Hidratos de carbono
399
33g
texto de ingredientes Proteínas
3.5g
Sal
0.38g
Valor energético / Energia 1364 kJ / 326 kcal
"""
        result = read_nutrition_label(observed, extraction_confidence=.96)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition, {
            "calories": 326.0,
            "fat_g": 17.0,
            "carbohydrate_g": 39.0,
            "protein_g": 3.5,
        })
        self.assertIn("MERCADONA_TRAILING_INTERLEAVED_MACRO_LABEL_EVIDENCE", result.reasons)

    def test_one_trailing_nutrient_word_in_ingredient_prose_is_not_rewritten(self):
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g
Valor energético 1364 kJ / 326 kcal
Grasas 17 g
Hidratos de carbono 39 g
ingredientes con proteínas
3.5g
Sal 0.38 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.96)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertNotIn("protein_g", result.nutrition or {})
        self.assertNotIn("MERCADONA_TRAILING_INTERLEAVED_MACRO_LABEL_EVIDENCE", result.reasons)

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
