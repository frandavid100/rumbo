import unittest

from mercadona_label_evidence import LabelImageEvidence
from mercadona_nutrition_reader import VisionExtraction, read_evidence, to_candidate
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
        self.assertEqual(c.source, "Mercadona label")
        self.assertEqual(c.identity.gtin, "8480000000000")
        self.assertFalse(c.redistribution_allowed)
        self.assertIn("DECLARED", c.claim)

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
