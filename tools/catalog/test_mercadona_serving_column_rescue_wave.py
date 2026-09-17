import unittest

from mercadona_nutrition_label_percentage_guard import read_nutrition_label
from mercadona_nutrition_reader import MercadonaLabelReading, VisionExtraction
from mercadona_explicit_serving_column_rescue import project_explicit_serving_column
from mercadona_serving_column_rescue_wave import _project_if_safe
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings
from test_mercadona_explicit_serving_column_rescue import CANDIDATE_64499


class MercadonaServingColumnRescueWaveTest(unittest.TestCase):
    def _reading(self, confidence: float):
        parsed = read_nutrition_label(CANDIDATE_64499, extraction_confidence=confidence)
        return MercadonaLabelReading(
            evidence=None,
            extraction=VisionExtraction(
                text=CANDIDATE_64499,
                confidence=confidence,
                engine="easyocr",
                engine_version="test",
            ),
            parsed=parsed,
        )

    def test_structurally_complete_low_confidence_projection_stays_review(self):
        rescued = _project_if_safe(self._reading(0.79425))
        self.assertEqual(rescued.parsed.status, "REVIEW")
        self.assertEqual(rescued.parsed.confidence, 0.79425)
        self.assertEqual(rescued.parsed.basis, "100_g")
        self.assertEqual(rescued.parsed.nutrition, {
            "calories": 403.0,
            "fat_g": 27.1,
            "carbohydrate_g": 35.3,
            "protein_g": 4.1,
        })
        self.assertIn("LOW_EXTRACTION_CONFIDENCE", rescued.parsed.reasons)
        self.assertIn("STRUCTURAL_PROJECTION_RETAINED_AS_REVIEW", rescued.parsed.reasons)
        self.assertTrue(any(
            reason.startswith("EXPLICIT_SERVING_COLUMN_PROJECTION")
            for reason in rescued.parsed.reasons
        ))

    def test_parser_normalized_nonnumeric_label_repair_can_feed_projection(self):
        # The ordinary Mercadona reader already permits a narrowly observed,
        # nonnumeric standalone row-label repair (Crasas -> Grasas). The serving
        # projector must be allowed to consume that audited normalized OCR text
        # when the unnormalized extraction cannot identify the row. No numeric
        # token is changed and low-confidence evidence still remains REVIEW.
        raw = CANDIDATE_64499.replace("Grasas/Lípidos", "Crasas;", 1)
        parsed = read_nutrition_label(raw, extraction_confidence=0.79425)
        self.assertIn("Grasas", parsed.normalized_text)
        self.assertNotIn("Crasas", parsed.normalized_text)
        reading = MercadonaLabelReading(
            evidence=None,
            extraction=VisionExtraction(
                text=raw,
                confidence=0.79425,
                engine="easyocr",
                engine_version="test",
            ),
            parsed=parsed,
        )

        rescued = _project_if_safe(reading)
        self.assertEqual(rescued.parsed.status, "REVIEW")
        self.assertEqual(rescued.parsed.basis, "100_g")
        self.assertEqual(rescued.parsed.nutrition, {
            "calories": 403.0,
            "fat_g": 27.1,
            "carbohydrate_g": 35.3,
            "protein_g": 4.1,
        })
        self.assertIn("NORMALIZED_OCR_TEXT_PROJECTION", rescued.parsed.reasons)
        self.assertIn("STRUCTURAL_PROJECTION_RETAINED_AS_REVIEW", rescued.parsed.reasons)

    def test_review_projection_can_only_promote_through_independent_ensemble_corroboration(self):
        paddle = project_explicit_serving_column(CANDIDATE_64499, extraction_confidence=.98)
        self.assertIsNotNone(paddle)
        self.assertEqual(paddle.result.status, "DECLARED")
        easy = _project_if_safe(self._reading(0.79425))
        self.assertEqual(easy.parsed.status, "REVIEW")

        ensemble = fuse_ocr_readings((
            ParsedOCRReading("paddleocr:visual_region", paddle.result, .98, "paddleocr"),
            ParsedOCRReading("easyocr:visual_region", easy.parsed, .79425, "easyocr"),
        ))
        self.assertEqual(ensemble.status, "DECLARED", ensemble)
        self.assertEqual(ensemble.independent_engine_families, 2)
        self.assertEqual(ensemble.corroborated_fields, 4)
        self.assertEqual(ensemble.nutrition, paddle.result.nutrition)

    def test_below_existing_ensemble_evidence_floor_is_not_projected(self):
        reading = self._reading(0.69)
        rescued = _project_if_safe(reading)
        self.assertIs(rescued, reading)
        self.assertIsNone(rescued.parsed.nutrition)
        self.assertIn("MULTIPLE_NUTRITION_COLUMNS", rescued.parsed.reasons)


if __name__ == "__main__":
    unittest.main()
