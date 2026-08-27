import tempfile
import unittest
from pathlib import Path

from label_text_extractor import TextExtraction
from mercadona_label_evidence import LabelImageEvidence
from mercadona_nutrition_importer import import_from_label_file
from nutrition_visual_table_detector import VisualTableRegion


GOOD = """INFORMACIÓN NUTRICIONAL
VALORES MEDIOS por 100 ml
VALOR ENERGÉTICO 252 kJ / 60 kcal
GRASAS 0,6 g
HIDRATOS DE CARBONO 11 g
PROTEÍNAS 2,1 g
SAL 0,21 g
"""


class NutritionImporterTest(unittest.TestCase):
    def evidence(self):
        return LabelImageEvidence(
            retailer="Mercadona", retailer_sku="23049", product_name="Batido de chocolate Hacendado",
            image_url="https://example.invalid/back.jpg", image_index=1, observed_at="2026-08-17T15:00:00Z",
            source_page=None, redistribution_allowed=False, purpose="PACK_LABEL_CANDIDATE", perspective=9,
        )

    def region_fixture(self, root):
        source = root / "back.jpg"; source.write_bytes(b"x")
        region_path = root / "region.png"; region_path.write_bytes(b"x")
        return source, VisualTableRegion("visual_table_0", (0,0,100,100), .9, 5, 2, .04, region_path)

    def test_neural_without_independent_confirmation_stays_review(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, region = self.region_fixture(root)
            calls = []
            def detector(path, out): return [region]
            def empty(path):
                calls.append("tesseract")
                return TextExtraction("", 0.0, "tesseract", "1", "spa")
            def neural(path):
                calls.append("neural")
                return TextExtraction(GOOD, .97, "paddleocr-PP-OCRv6", "3.7", "es")
            result = import_from_label_file(
                self.evidence(), source, gtin="8480000230499", brand="Hacendado",
                tesseract_strategies=(("cheap", empty),), neural_extractor=neural,
                region_detector=detector, work_dir=root,
            )
        self.assertEqual(result.status, "REVIEW")
        self.assertIsNone(result.candidate)
        self.assertEqual([a.stage for a in result.attempts], [
            "TESSERACT_ORIGINAL", "INDEPENDENT_OCR_VISUAL_REGION"
        ])
        self.assertEqual(calls, ["tesseract", "tesseract", "neural"])

    def test_tesseract_and_neural_can_confirm_same_detected_region(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, region = self.region_fixture(root)
            calls = []
            def detector(path, out): return [region]
            def tesseract(path):
                calls.append("tesseract")
                return TextExtraction(GOOD, .95, "tesseract", "5", "spa")
            def neural(path):
                calls.append("neural")
                return TextExtraction(GOOD, .97, "paddleocr-PP-OCRv6", "3.7", "es")
            result = import_from_label_file(
                self.evidence(), source, gtin="8480000230499", brand="Hacendado",
                tesseract_strategies=(("psm6", tesseract),), neural_extractor=neural,
                region_detector=detector, work_dir=root,
            )
        self.assertEqual(result.status, "DECLARED")
        self.assertIsNotNone(result.candidate)
        self.assertEqual(result.candidate.nutrition["fat_g"], .6)
        self.assertEqual([a.stage for a in result.attempts], [
            "TESSERACT_ORIGINAL", "INDEPENDENT_OCR_VISUAL_REGION"
        ])
        self.assertEqual(calls, ["tesseract", "tesseract", "neural"])


if __name__ == "__main__":
    unittest.main()
