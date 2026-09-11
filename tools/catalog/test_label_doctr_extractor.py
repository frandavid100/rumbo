from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from label_doctr_extractor import DocTRExtractionError, extract_with_doctr


class LabelDocTRExtractorTest(unittest.TestCase):
    def test_extracts_lines_and_mean_word_confidence(self):
        words1 = [
            SimpleNamespace(value="Valor", confidence=.90),
            SimpleNamespace(value="energético", confidence=.80),
        ]
        words2 = [SimpleNamespace(value="150 kcal", confidence=1.0)]
        result = SimpleNamespace(pages=[SimpleNamespace(blocks=[SimpleNamespace(lines=[
            SimpleNamespace(words=words1),
            SimpleNamespace(words=words2),
        ])])])

        class Predictor:
            def __call__(self, document):
                self.document = document
                return result

        predictor = Predictor()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "label.jpg"
            path.write_bytes(b"fixture")
            extracted = extract_with_doctr(
                path,
                predictor_factory=lambda: (predictor, "1.1.0"),
                document_loader=lambda p: [str(p)],
            )

        self.assertEqual(extracted.text, "Valor energético\n150 kcal")
        self.assertAlmostEqual(extracted.confidence, .90)
        self.assertEqual(extracted.engine_version, "1.1.0")
        self.assertTrue(extracted.engine.startswith("doctr-"))

    def test_missing_image_fails_closed(self):
        with self.assertRaises(DocTRExtractionError):
            extract_with_doctr("/definitely/missing.jpg")


if __name__ == "__main__":
    unittest.main()
