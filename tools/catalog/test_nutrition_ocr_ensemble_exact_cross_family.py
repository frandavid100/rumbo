import unittest

from nutrition_label_reader import LabelReadResult
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


def reading(status, basis, nutrition, confidence, text="fixture", *reasons):
    return LabelReadResult(status, basis, nutrition, confidence, tuple(reasons), text)


class ExactCrossFamilyConsensusTest(unittest.TestCase):
    def test_nearby_cross_family_values_do_not_become_exact_consensus(self):
        common = {
            "calories": 86.0,
            "carbohydrate_g": 11.0,
            "protein_g": 3.2,
        }
        easy = reading(
            "REVIEW", "100_g", {**common, "fat_g": 3.29}, .84,
            "Información nutricional por 100 g\nGrasas 3.29",
        )
        tesseract = reading(
            "REVIEW", "100_g", {**common, "fat_g": 3.29}, .85,
            "Información nutricional por 100 g\nGrasas 3.29",
        )
        paddle = reading(
            "DECLARED", "100_g", {**common, "fat_g": 3.2}, .98,
            "Información nutricional por 100 g\nGrasas 3.2 g",
        )

        result = fuse_ocr_readings([
            ParsedOCRReading("easyocr-crop-right", easy, engine_family="easyocr"),
            ParsedOCRReading("tesseract-psm11", tesseract, engine_family="tesseract"),
            ParsedOCRReading("paddleocr-crop-right", paddle, engine_family="paddleocr"),
        ])

        self.assertEqual(result.status, "REVIEW", result)
        self.assertIn("OCR_FIELD_CONFLICT:fat_g", result.reasons)
        self.assertNotIn("fat_g", result.nutrition or {})

    def test_any_credible_multi_column_observation_vetoes_single_column_fusion(self):
        # Real Mercadona product 22799 has parallel 100 g and 125 g nutrition
        # columns. Some crops linearise only the 100 g values, while a credible
        # full-table OCR correctly sees both columns. The ensemble must preserve
        # that structural ambiguity instead of allowing clean-looking crops to
        # manufacture usable exact nutrition from one column.
        full_table = reading(
            "REVIEW", "100_g", None, .97,
            "100 g 125 g\nValor energético 86 kcal 108 kcal\nGrasas 3.2 g 4.0 g",
            "MULTIPLE_NUTRITION_COLUMNS",
        )
        clean_a = reading(
            "DECLARED", "100_g",
            {"calories": 86.0, "fat_g": 3.2, "carbohydrate_g": 11.0, "protein_g": 3.2},
            .96,
        )
        clean_b = reading(
            "DECLARED", "100_g",
            {"calories": 86.0, "fat_g": 3.2, "carbohydrate_g": 11.0, "protein_g": 3.2},
            .94,
        )

        result = fuse_ocr_readings([
            ParsedOCRReading("paddleocr-full", full_table, engine_family="paddleocr"),
            ParsedOCRReading("easyocr-crop-right", clean_a, engine_family="easyocr"),
            ParsedOCRReading("tesseract-crop-right", clean_b, engine_family="tesseract"),
        ])

        self.assertEqual(result.status, "REVIEW", result)
        self.assertIn("MULTIPLE_NUTRITION_COLUMNS", result.reasons)
        self.assertIsNone(result.nutrition)

    def test_exact_token_seen_in_every_clean_family_can_beat_nearby_layout(self):
        doctr = reading(
            "DECLARED", "100_ml",
            {"calories": 50.0, "fat_g": 0.0, "carbohydrate_g": 11.3, "protein_g": 0.5},
            .88,
        )
        tess_nearby = reading(
            "REVIEW", "100_ml",
            {"calories": 50.0, "fat_g": 0.0, "carbohydrate_g": 11.39, "protein_g": 0.5},
            .95,
        )
        tess_exact = reading(
            "DECLARED", "100_ml",
            {"calories": 50.0, "fat_g": 0.0, "carbohydrate_g": 11.3, "protein_g": 0.5},
            .90,
        )

        result = fuse_ocr_readings([
            ParsedOCRReading("doctr-crop-left", doctr, engine_family="doctr"),
            ParsedOCRReading("tesseract-psm11", tess_nearby, engine_family="tesseract"),
            ParsedOCRReading("tesseract-psm4", tess_exact, engine_family="tesseract"),
        ])

        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.nutrition["carbohydrate_g"], 11.3)


if __name__ == "__main__":
    unittest.main()
