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

    def test_reparse_from_persisted_text_repairs_complete_value_before_label_binding(self):
        # Reparse the persisted OCR text with the current reader rather than
        # trusting the historical parser result. Two independent OCR families
        # expose the same complete single-column value-before-label layout, so
        # the corrected direct OCR tuple can be corroborated normally.
        result = replay_attempt(self._attempt(), reparse_label_text=True)
        self.assertEqual(result["status"], "DECLARED", result)
        self.assertEqual(result["basis"], "100_g")
        self.assertEqual(result["nutrition"], {
            "calories": 354.0,
            "fat_g": 1.2,
            "carbohydrate_g": 79.0,
            "protein_g": 7.0,
        })

    def test_later_coherent_complete_review_replaces_only_incoherent_fallback(self):
        # Observed at product 21594: the first crop produced a complete but
        # energy-incoherent REVIEW tuple (carbohydrate 15 instead of 25.9), while
        # the next independent crop preserved a complete coherent tuple. REVIEW
        # remains REVIEW; this only prevents known-bad conflict evidence from
        # shadowing the safer observation.
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
            "reasons": ["UNCORROBORATED_CORE_FIELDS", "LOW_EXTRACTION_CONFIDENCE"],
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
