from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from label_doctr_extractor import DocTRExtractionError, extract_with_doctr
from nutrition_label_reader import read_nutrition_label


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

    def test_repairs_bounded_multiline_nutrition_signature_without_inventing_values(self):
        corrupted_lines = [
            "Nutriconal Iformgion/ Declarerso M MIR/AOR Per100g",
            "Valorenergétio/",
            "Energie(d/kral)",
            "130/31",
            "Groses/",
            "0.4",
            "Herntndecarbanolg) 4.0",
            "Proteinos(g)",
            "2.8",
            "Sal 0.10",
        ]
        result = SimpleNamespace(pages=[SimpleNamespace(blocks=[SimpleNamespace(lines=[
            SimpleNamespace(words=[SimpleNamespace(value=line, confidence=.90)])
            for line in corrupted_lines
        ])])])

        class Predictor:
            def __call__(self, document):
                return result

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "label.jpg"
            path.write_bytes(b"fixture")
            extracted = extract_with_doctr(
                path,
                predictor_factory=lambda: (Predictor(), "1.1.0"),
                document_loader=lambda p: [str(p)],
            )

        self.assertIn("Informacion nutricional\nPor 100g", extracted.text)
        self.assertIn("Energia (kJ/kcal)\n130/31", extracted.text)
        self.assertIn("Grasas\n0.4", extracted.text)
        self.assertIn("Hidratos de carbono (g) 4.0", extracted.text)
        self.assertIn("Proteinas (g)\n2.8", extracted.text)
        self.assertNotIn("4.0\n4.0", extracted.text)

        parsed = read_nutrition_label(extracted.text, extraction_confidence=extracted.confidence)
        self.assertEqual(parsed.status, "DECLARED")
        self.assertEqual(parsed.basis, "100_g")
        self.assertEqual(
            parsed.nutrition,
            {"calories": 31.0, "fat_g": 0.4, "carbohydrate_g": 4.0, "protein_g": 2.8},
        )

    def test_does_not_repair_isolated_lookalike_without_complete_signature(self):
        result = SimpleNamespace(pages=[SimpleNamespace(blocks=[SimpleNamespace(lines=[
            SimpleNamespace(words=[SimpleNamespace(value="Groses/", confidence=.90)]),
            SimpleNamespace(words=[SimpleNamespace(value="Proteinos(g)", confidence=.90)]),
        ])])])

        class Predictor:
            def __call__(self, document):
                return result

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "label.jpg"
            path.write_bytes(b"fixture")
            extracted = extract_with_doctr(
                path,
                predictor_factory=lambda: (Predictor(), "1.1.0"),
                document_loader=lambda p: [str(p)],
            )

        self.assertEqual(extracted.text, "Groses/\nProteinos(g)")

    def test_missing_image_fails_closed(self):
        with self.assertRaises(DocTRExtractionError):
            extract_with_doctr("/definitely/missing.jpg")


if __name__ == "__main__":
    unittest.main()
