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
