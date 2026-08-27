import unittest

from mercadona_label_evidence import LabelImageEvidence
from mercadona_nutrition_reader import (
    OCR_EVIDENCE_LEVEL,
    VisionExtraction,
    read_evidence,
    to_candidate,
)
from nutrition_label_reader import read_nutrition_label


GOOD = """Información nutricional. Valores medios por 100 g
Valor energético 1540 kJ / 368 kcal
Grasas 4,2 g
de las cuales saturadas 0,8 g
Hidratos de carbono 67,0 g
de los cuales azúcares 12,0 g
Proteínas 12,5 g
Sal 0,35 g
"""

GOOD_ML = """Información nutricional por 100 ml
Energía 176 kJ / 42 kcal
Grasas 0 g
Hidratos de carbono 10,4 g
Proteínas 0 g
Sal 0,01 g
"""


class NutritionLabelReaderTest(unittest.TestCase):
    def test_reads_valid_100g_label(self):
        r = read_nutrition_label(GOOD, extraction_confidence=.96)
        self.assertEqual(r.status, "DECLARED")
        self.assertEqual(r.basis, "100_g")
        self.assertEqual(r.nutrition, {
            "calories": 368.0, "fat_g": 4.2,
            "carbohydrate_g": 67.0, "protein_g": 12.5,
        })

    def test_reads_valid_100ml_label(self):
        r = read_nutrition_label(GOOD_ML, extraction_confidence=.97)
        self.assertEqual(r.status, "DECLARED")
        self.assertEqual(r.basis, "100_ml")
        self.assertEqual(r.nutrition["carbohydrate_g"], 10.4)

    def test_nutrition_heading_prevents_ingredient_percentages_from_becoming_macros(self):
        observed = """BATIDO SABOR CHOCOLATE UHT.
INGREDIENTES
Leche parcialmente desnatada (0,7% de grasa), cacao desgrasado (1%), azúcar.
INFORMACIÓN NUTRICIONAL
VALORES MEDIOS
por 100ml
VALOR ENERGÉTICO
252 kJ/60 kcal
GRASAS
0,6g
de las cuales saturadas 0,4g
HIDRATOS DE CARBONO
11g
de los cuales azúcares 10g
PROTEÍNAS
2,1g
SAL
0,21g
PREPARACIÓN
Agitar antes de servir.
"""
        r = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.nutrition, {
            "calories": 60.0, "fat_g": 0.6,
            "carbohydrate_g": 11.0, "protein_g": 2.1,
        })

    def test_parallel_per_100g_columns_are_review_not_mixed(self):
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g de peso neto
Por 100 g de peso escurrido
Valor Energético 333 kJ / 79 kcal 417 kJ / 98 kcal
Grasas 0,6 g 1,2 g
De las cuales saturadas 0,2 g 0,4 g
Hidratos de Carbono <0,5 g 0,9 g
De los cuales azúcares <0,5 g <0,5 g
Proteínas 18 g 21 g
Sal 1,1 g 1,1 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(r.status, "REVIEW")
        self.assertIn("MULTIPLE_NUTRITION_COLUMNS", r.reasons)
        self.assertIsNone(r.nutrition)

    def test_multiline_cells_and_terminal_g_read_as_9(self):
        noisy = """1009
Valor Energético/Energía 427 kcal
Grasas/Lípidos
9.29
de las cuales
Hidratos de Carbono
769
de los cuales
Proteínas
7.4
Sal 0.92
"""
        r = read_nutrition_label(noisy, extraction_confidence=.90)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.basis, "100_g")
        self.assertAlmostEqual(r.nutrition["fat_g"], 9.29)
        self.assertEqual(r.nutrition["carbohydrate_g"], 76.0)
        self.assertEqual(r.nutrition["protein_g"], 7.4)

    def test_ocr_g_as_y_and_large_terminal_9_values(self):
        noisy = """100 y
Energético/Energía 568 kcal
Grasas/Lípidos
429
de las cuales
Hidratos de Carbono
329
de los cuales
Proteínas 10g
Sal 0.03
"""
        r = read_nutrition_label(noisy, extraction_confidence=.90)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.nutrition["fat_g"], 42.0)
        self.assertEqual(r.nutrition["carbohydrate_g"], 32.0)

    def test_bad_terminal_9_repair_is_still_blocked_by_energy(self):
        noisy = """100 g
Energético 132 kcal
Grasas 0 g
Hidratos de Carbono 6.39 g
Proteínas 909
Sal 1 g
"""
        r = read_nutrition_label(noisy, extraction_confidence=.95)
        self.assertEqual(r.status, "REVIEW")
        self.assertTrue(any(x.startswith("ENERGY_MACRO_MISMATCH") for x in r.reasons))

    def test_front_pack_is_not_nutrition(self):
        r = read_nutrition_label("Hacendado Galletas tostadas. Peso neto 800 g. Conservar en lugar fresco.")
        self.assertEqual(r.status, "NOT_NUTRITION_LABEL")
        self.assertIsNone(r.nutrition)

    def test_missing_basis_goes_to_review(self):
        r = read_nutrition_label(GOOD.replace("Valores medios por 100 g", "Valores medios"), extraction_confidence=.98)
        self.assertEqual(r.status, "REVIEW")
        self.assertIn("MISSING_100G_100ML_BASIS", r.reasons)

    def test_low_vision_confidence_goes_to_review(self):
        r = read_nutrition_label(GOOD, extraction_confidence=.70)
        self.assertEqual(r.status, "REVIEW")
        self.assertIn("LOW_EXTRACTION_CONFIDENCE", r.reasons)

    def test_energy_macro_mismatch_goes_to_review(self):
        bad = GOOD.replace("368 kcal", "120 kcal")
        r = read_nutrition_label(bad, extraction_confidence=.99)
        self.assertEqual(r.status, "REVIEW")
        self.assertTrue(any(x.startswith("ENERGY_MACRO_MISMATCH") for x in r.reasons))

    def test_bridge_preserves_image_non_redistribution(self):
        evidence = LabelImageEvidence(
            retailer="Mercadona", retailer_sku="1234", product_name="Producto Hacendado",
            image_url="https://example.invalid/label.jpg", image_index=2,
            observed_at="2026-08-17T14:00:00Z", source_page="https://tienda.mercadona.es/product/1234",
            redistribution_allowed=False, purpose="PACK_LABEL_CANDIDATE",
        )
        reading = read_evidence(evidence, VisionExtraction(GOOD, .98, "fixture-vision", "1"))
        c = to_candidate(reading, gtin="8480000000000", brand="Hacendado")
        self.assertIsNotNone(c)
        self.assertEqual(c.source, "Mercadona label image OCR")
        self.assertEqual(c.identity.gtin, "8480000000000")
        self.assertFalse(c.redistribution_allowed)
        self.assertEqual(c.evidence_level, OCR_EVIDENCE_LEVEL)
        self.assertIn(OCR_EVIDENCE_LEVEL, c.claim)
        self.assertNotEqual(c.evidence_level, "DECLARED")

    def test_review_is_not_converted_to_candidate(self):
        evidence = LabelImageEvidence(
            retailer="Mercadona", retailer_sku="1234", product_name="Producto",
            image_url="https://example.invalid/front.jpg", image_index=0,
            observed_at="2026-08-17T14:00:00Z", source_page=None,
            redistribution_allowed=False, purpose="PACK_LABEL_CANDIDATE",
        )
        reading = read_evidence(evidence, VisionExtraction("Envase frontal", .99, "fixture-vision"))
        self.assertIsNone(to_candidate(reading))


if __name__ == "__main__":
    unittest.main()
