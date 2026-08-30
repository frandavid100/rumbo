import unittest
from unittest.mock import patch

from replay_mercadona_ocr_ensemble import replay_attempt, replay_product


RICE_FLOUR_TEXT = """100 g
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
Peso Neto:"""


class ReplayMercadonaOCRTest(unittest.TestCase):
    def _attempt(self):
        wrong = {
            "status": "DECLARED",
            "basis": "100_g",
            "nutrition": {
                "calories": 354.0,
                "fat_g": 1.2,
                "carbohydrate_g": 79.0,
                "protein_g": 0.01,
            },
            "confidence": 0.99,
            "reasons": [],
            "normalized_ocr_text": RICE_FLOUR_TEXT,
        }
        return {
            "target_kind": "full",
            "engines": {
                "paddle": {**wrong, "engine": "PP-OCRv6"},
                "easyocr": {**wrong, "engine": "EasyOCR"},
            },
        }

    def test_stored_parser_results_reproduce_old_false_acceptance(self):
        result = replay_attempt(self._attempt(), reparse_label_text=False)
        self.assertEqual(result["status"], "DECLARED")
        self.assertEqual(result["nutrition"]["protein_g"], 0.01)

    def test_reparse_from_persisted_text_applies_current_safety_guard(self):
        result = replay_attempt(self._attempt(), reparse_label_text=True)
        self.assertEqual(result["status"], "REVIEW")
        self.assertIn("MISSING_CORE:calories,fat_g,carbohydrate_g,protein_g", result["reasons"])

    def test_review_fallback_does_not_prefer_energy_incoherent_complete_attempt(self):
        """Regression for Mercadona 21594: mozzarella 15% must not poison p9 REVIEW evidence."""
        bad = {
            "status": "REVIEW",
            "basis": "100_g",
            "nutrition": {
                "calories": 242.0,
                "fat_g": 10.2,
                "carbohydrate_g": 15.0,
                "protein_g": 10.9,
            },
            "confidence": 0.84,
            "reasons": ["UNCORROBORATED_CORE_FIELDS", "ENERGY_MACRO_MISMATCH:195.4"],
        }
        coherent = {
            "status": "REVIEW",
            "basis": "100_g",
            "nutrition": {
                "calories": 242.0,
                "fat_g": 10.2,
                "carbohydrate_g": 25.9,
                "protein_g": 10.9,
            },
            "confidence": 0.78,
            "reasons": [
                "UNCORROBORATED_BASIS",
                "UNCORROBORATED_CORE_FIELDS",
                "LOW_EXTRACTION_CONFIDENCE",
            ],
        }
        row = {"status": "REVIEW", "attempts": [{}, {}]}
        with patch(
            "replay_mercadona_ocr_ensemble.replay_attempt",
            side_effect=[bad, coherent],
        ):
            status, nutrition, basis, replayed = replay_product(row)

        self.assertEqual(status, "REVIEW")
        self.assertEqual(basis, "100_g")
        self.assertEqual(nutrition, coherent["nutrition"])
        self.assertEqual(replayed, [bad, coherent])


if __name__ == "__main__":
    unittest.main()
