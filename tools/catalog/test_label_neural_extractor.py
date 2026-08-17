import tempfile
import unittest
from pathlib import Path

from label_neural_extractor import extract_with_paddleocr


class FakeResult:
    def __init__(self, payload):
        self.json = {"res": payload}


class FakePipeline:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def predict(self, path):
        return [FakeResult({
            "rec_texts": ["Proteínas 3,1 g", "Información nutricional por 100 ml", "Grasas 0,9 g", "61 kcal", "Hidratos de carbono 10 g"],
            "rec_scores": [0.94, 0.99, 0.96, 0.97, 0.95],
            "rec_boxes": [[20,120,160,145], [15,10,260,35], [20,70,150,95], [180,40,250,60], [20,95,220,118]],
        })]


class PaddleExtractorTest(unittest.TestCase):
    def test_converts_result_to_common_text_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "label.png"
            path.write_bytes(b"fixture")
            result = extract_with_paddleocr(path, pipeline_factory=FakePipeline)
        self.assertEqual(result.engine, "paddleocr-PP-OCRv6")
        self.assertEqual(result.language, "es")
        self.assertGreater(result.confidence, .94)
        self.assertIn("Información nutricional por 100 ml", result.text)
        self.assertIn("Proteínas 3,1 g", result.text)

    def test_empty_recognition_is_low_confidence_not_invented_text(self):
        class EmptyPipeline:
            def __init__(self, **kwargs): pass
            def predict(self, path): return [FakeResult({"rec_texts": [], "rec_scores": [], "rec_boxes": []})]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "label.png"
            path.write_bytes(b"fixture")
            result = extract_with_paddleocr(path, pipeline_factory=EmptyPipeline)
        self.assertEqual(result.text, "")
        self.assertEqual(result.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
