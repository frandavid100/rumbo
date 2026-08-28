import tempfile
import unittest
from pathlib import Path

from label_easyocr_extractor import EasyOCRExtractionError, extract_with_easyocr


class _FakeReader:
    def readtext(self, _path, *, detail, paragraph):
        self.args = (detail, paragraph)
        return [
            ([[100, 50], [300, 50], [300, 80], [100, 80]], "Valor energético 420 kcal", 0.96),
            ([[100, 90], [260, 90], [260, 120], [100, 120]], "Grasas 10 g", 0.94),
            ([[320, 90], [520, 90], [520, 120], [320, 120]], "Proteínas 20 g", 0.92),
        ]


class EasyOCRExtractorTest(unittest.TestCase):
    def test_extracts_ordered_text_and_confidence_with_injected_reader(self):
        reader = _FakeReader()
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "label.jpg"
            image.write_bytes(b"fixture")
            result = extract_with_easyocr(
                image,
                reader_factory=lambda languages: (reader, "fixture-1"),
            )
        self.assertEqual(reader.args, (1, False))
        self.assertEqual(
            result.text.splitlines(),
            ["Valor energético 420 kcal", "Grasas 10 g", "Proteínas 20 g"],
        )
        self.assertAlmostEqual(result.confidence, 0.94, places=6)
        self.assertEqual(result.engine, "easyocr")
        self.assertEqual(result.engine_version, "fixture-1")
        self.assertEqual(result.language, "es+en")

    def test_requires_existing_image(self):
        with self.assertRaises(EasyOCRExtractionError):
            extract_with_easyocr("/definitely/missing/label.jpg", reader_factory=lambda _languages: (_FakeReader(), "fixture"))


if __name__ == "__main__":
    unittest.main()
