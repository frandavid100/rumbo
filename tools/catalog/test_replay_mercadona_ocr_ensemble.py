import unittest

from replay_mercadona_ocr_ensemble import replay_attempt


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
            "basis": "PER_100G",
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
        self.assertIn("NO_DECLARED_OCR_READ", result["reasons"])


if __name__ == "__main__":
    unittest.main()
