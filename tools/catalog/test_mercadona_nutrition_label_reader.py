import unittest

from mercadona_nutrition_label_reader import read_nutrition_label


class MercadonaNutritionLabelReaderSafetyTest(unittest.TestCase):
    def test_bare_100g_and_serving_columns_are_review_without_partial_nutrition(self):
        # Observed PP-OCR layout from a Mercadona back label. The visual table has
        # one column per 100 g and another per 26 g serving, but OCR linearises the
        # column headings and then emits both values row by row. It can also split
        # the energy label around the numeric cells (`Valor ... Energético`). A
        # sequential label->next-number parser must not expose either column as
        # corroborating evidence for an OCR ensemble.
        observed = """100 g
26 g
sugeri
Valor
846 kJ
222 kJ
Pser
Energético/Energia
200 Kcal
53 Kcal
suger
2,6 g
0,7 g
Grasas/Lípidos
de las cuales/dos quais:
- Saturadas/Saturados
0,6 g
0,1 g
37 g
10 g
Hidratos de Carbono
de los cuales/dos quais:
5,6 g
1,5 g
- Azúcares/Açúcares
5,9 g
1,5 g
Fibra alimentaria/Fibra
1,1 g
4,3 g
Proteínas
1,0 g
0,3 g
Sal
"""
        result = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertIn("MULTIPLE_NUTRITION_COLUMNS", result.reasons)
        self.assertIsNone(result.nutrition)

    def test_conventional_bare_two_column_energy_layout_is_also_blocked(self):
        observed = """INFORMACIÓN NUTRICIONAL
100 g
26 g
sugerida
Valor energético
846 kJ
222 kJ
200 kcal
53 kcal
Grasas
2,6 g
0,7 g
Hidratos de carbono
37 g
9,6 g
Proteínas
4,3 g
1,0 g
Sal
1,0 g
0,3 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertIn("MULTIPLE_NUTRITION_COLUMNS", result.reasons)
        self.assertIsNone(result.nutrition)

    def test_single_bare_100g_column_remains_usable(self):
        observed = """INFORMACIÓN NUTRICIONAL
100 g
Valor energético
846 kJ
200 kcal
Grasas
2,6 g
Hidratos de carbono
37 g
Proteínas
4,3 g
Sal
1,0 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition, {
            "calories": 200.0,
            "fat_g": 2.6,
            "carbohydrate_g": 37.0,
            "protein_g": 4.3,
        })

    def test_material_energy_macro_mismatch_is_review_without_numeric_evidence(self):
        # Observed Mercadona product 35197. All OCR families read the same tuple,
        # but 35*9 + 4*4 + 13*4 = 383 kcal while the label reads 349 kcal. The
        # Mercadona wrapper must suppress this tuple so cross-engine agreement
        # cannot promote an internally inconsistent observation.
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g
Valor energético 1445 kJ / 349 kcal
Grasas 35 g
Hidratos de carbono 4 g
Proteínas 13 g
Sal 2 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertIsNone(result.nutrition)
        self.assertIn("ENERGY_MACRO_MISMATCH_STRICT:383.0", result.reasons)

    def test_material_energy_macro_mismatch_in_review_also_hides_numeric_evidence(self):
        # REVIEW rows are still consumed as ensemble evidence. Low extraction
        # confidence must therefore not allow the same inconsistent complete
        # tuple to survive numerically just because it was already REVIEW.
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g
Valor energético 1445 kJ / 349 kcal
Grasas 35 g
Hidratos de carbono 4 g
Proteínas 13 g
Sal 2 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.80)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertIsNone(result.nutrition)
        self.assertIn("LOW_EXTRACTION_CONFIDENCE", result.reasons)
        self.assertIn("ENERGY_MACRO_MISMATCH_STRICT:383.0", result.reasons)

    def test_explicit_fibre_reconciles_real_eu_energy_without_relaxing_guard(self):
        # Observed Mercadona product 29134. Core Atwater gives 306 kcal, while
        # the label declares 328 kcal and explicitly declares 11 g fibre. Adding
        # the EU fibre contribution (2 kcal/g) reconciles it exactly.
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g
Valor energético 1384 kJ / 328 kcal
Grasas 2 g
Hidratos de carbono 60 g
Fibra alimentaria 11 g
Proteínas 12 g
Sal 0,03 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.nutrition, {
            "calories": 328.0,
            "fat_g": 2.0,
            "carbohydrate_g": 60.0,
            "protein_g": 12.0,
        })

    def test_explicit_polyols_and_fibre_reconcile_energy_without_inference(self):
        # Observed nutrient pattern from Mercadona product 12946, represented as
        # a single-column label so this unit test isolates energy accounting from
        # that product's separate multi-column ambiguity. Carbohydrate includes
        # polyols: 503 core kcal - 1.6*35 + 2*9 = 465 kcal.
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g
Valor energético 1926 kJ / 465 kcal
Grasas 31 g
Hidratos de carbono 47 g
Polialcoholes 35 g
Fibra alimentaria 9 g
Proteínas 9 g
Sal 0,3 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.nutrition, {
            "calories": 465.0,
            "fat_g": 31.0,
            "carbohydrate_g": 47.0,
            "protein_g": 9.0,
        })

    def test_inexact_polyol_ocr_cannot_rescue_inconsistent_energy(self):
        # The auxiliary reconciliation is intentionally much tighter than the
        # ordinary guard. A plausible-looking but wrong 30 g OCR read must not
        # rescue the 465 kcal tuple (it would estimate 473 kcal).
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g
Valor energético 1926 kJ / 465 kcal
Grasas 31 g
Hidratos de carbono 47 g
Polialcoholes 30 g
Fibra alimentaria 9 g
Proteínas 9 g
Sal 0,3 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertIsNone(result.nutrition)
        self.assertIn("ENERGY_MACRO_MISMATCH_STRICT:503.0", result.reasons)

    def test_complete_single_column_value_before_label_layout_is_rescued(self):
        # Observed PP-OCR layout for Mercadona product 29130 (Harina de arroz).
        # All three core macro values are explicit standalone gram rows immediately
        # before their labels. The sequential parse binds salt (0.01 g) to protein,
        # while the complete reversed tuple is 354 kcal / 1.2 / 79 / 7 and is
        # near-exactly energy coherent. This is direct OCR evidence, not inference.
        observed = """100 g
1500 kJ
Valor
354 kcal
Energético
1.2 g
Grasas
de las cuales:
0.2g
-Saturadas
79 g
Hidratos de Carbono
de los cuales:
0.5g
-Azúcares
1g
Fibra alimentaria
7g
Proteínas
0.01g
Sal
500
g
Peso Neto:
"""
        result = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition, {
            "calories": 354.0,
            "fat_g": 1.2,
            "carbohydrate_g": 79.0,
            "protein_g": 7.0,
        })
        self.assertIn("VALUE_BEFORE_LABEL_RESCUED", result.reasons)

    def test_complete_value_before_label_rescue_stays_review_below_confidence_floor(self):
        observed = """100 g
1500 kJ
Valor
354 kcal
Energético
1.2 g
Grasas
de las cuales:
0.2g
-Saturadas
79 g
Hidratos de Carbono
de los cuales:
0.5g
-Azúcares
1g
Fibra alimentaria
7g
Proteínas
0.01g
Sal
"""
        result = read_nutrition_label(observed, extraction_confidence=.80)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertNotIn("VALUE_BEFORE_LABEL_RESCUED", result.reasons)

    def test_value_before_label_layout_is_not_rescued_without_energy_coherence(self):
        observed = """100 g
1500 kJ
Valor
354 kcal
Energético
1.2 g
Grasas
de las cuales:
0.2g
-Saturadas
40 g
Hidratos de Carbono
de los cuales:
0.5g
-Azúcares
1g
Fibra alimentaria
7g
Proteínas
0.01g
Sal
"""
        result = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertNotEqual(result.status, "DECLARED", result)
        self.assertNotIn("VALUE_BEFORE_LABEL_RESCUED", result.reasons)


if __name__ == "__main__":
    unittest.main()
