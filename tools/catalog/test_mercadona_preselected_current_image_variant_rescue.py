import unittest

from mercadona_ocr_image_safety import attempts_have_structural_ambiguity


class ImageWideStructuralAmbiguityTest(unittest.TestCase):
    def test_multi_column_attempt_vetoes_other_declared_attempts(self):
        attempts = [
            {
                "target_kind": "crop-right",
                "ensemble": {
                    "status": "DECLARED",
                    "reasons": [],
                    "nutrition": {
                        "calories": 86.0,
                        "fat_g": 3.2,
                        "carbohydrate_g": 11.0,
                        "protein_g": 3.2,
                    },
                },
            },
            {
                "target_kind": "full_back_image",
                "ensemble": {
                    "status": "REVIEW",
                    "reasons": [
                        "MULTIPLE_NUTRITION_COLUMNS",
                        "OCR_AMBIGUOUS_NUTRITION_COLUMNS:paddleocr",
                    ],
                    "nutrition": None,
                },
            },
        ]

        self.assertTrue(attempts_have_structural_ambiguity(attempts))

    def test_unrelated_review_does_not_create_structural_veto(self):
        attempts = [
            {
                "target_kind": "crop-right",
                "ensemble": {
                    "status": "REVIEW",
                    "reasons": ["MISSING_CORE:fat_g"],
                    "nutrition": {"calories": 86.0},
                },
            }
        ]

        self.assertFalse(attempts_have_structural_ambiguity(attempts))


if __name__ == "__main__":
    unittest.main()
