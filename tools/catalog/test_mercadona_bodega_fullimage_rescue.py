import unittest
from types import SimpleNamespace

from mercadona_bodega_fullimage_rescue import choose_ensemble, select_current_candidates
from nutrition_label_reader import read_nutrition_label


def observed(parsed, confidence):
    return SimpleNamespace(parsed=parsed, extraction=SimpleNamespace(confidence=confidence))


class MercadonaBodegaFullImageRescueTest(unittest.TestCase):
    def test_revalidation_must_be_complete(self):
        payload = {
            "expected": 2,
            "checks": [
                {"ok": True, "product_id": "1", "live_ean": "111", "live_p9_url": "https://prod-mercadona.imgix.net/a.jpg"},
                {"ok": False, "product_id": "2", "live_ean": "222", "live_p9_url": "https://prod-mercadona.imgix.net/b.jpg"},
            ],
        }
        with self.assertRaises(ValueError):
            select_current_candidates(payload, require_all=True)

    def test_matching_independent_declared_reads_are_usable(self):
        text = """Información nutricional por 100 ml
Valor energético 252 kJ / 60 kcal
Grasas 0 g
Hidratos de carbono 4.5 g
Proteínas 0.5 g
Sal 0.02 g
"""
        paddle = read_nutrition_label(text, extraction_confidence=.98)
        easy = read_nutrition_label(text, extraction_confidence=.95)
        fused = choose_ensemble((
            ("paddleocr", "paddleocr", observed(paddle, .98)),
            ("easyocr", "easyocr", observed(easy, .95)),
        ))
        self.assertEqual(fused.status, "DECLARED", fused)
        self.assertEqual(fused.independent_engine_families, 2)
        self.assertEqual(fused.corroborated_fields, 4)

    def test_conflicting_declared_observation_forces_review(self):
        a = read_nutrition_label("""Información nutricional por 100 ml
Valor energético 252 kJ / 60 kcal
Grasas 0 g
Hidratos de carbono 4.5 g
Proteínas 0.5 g
""", extraction_confidence=.98)
        b = read_nutrition_label("""Información nutricional por 100 ml
Valor energético 300 kJ / 72 kcal
Grasas 0 g
Hidratos de carbono 8 g
Proteínas 0.5 g
""", extraction_confidence=.95)
        fused = choose_ensemble((
            ("paddleocr", "paddleocr", observed(a, .98)),
            ("easyocr", "easyocr", observed(b, .95)),
        ))
        self.assertEqual(fused.status, "REVIEW")
        self.assertTrue(any(reason.startswith("OCR_FIELD_CONFLICT") for reason in fused.reasons), fused)


if __name__ == "__main__":
    unittest.main()
