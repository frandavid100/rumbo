from pathlib import Path
import tempfile
import unittest

from PIL import Image

from mercadona_bounded_doctr_rescue import build_bounded_primary_column_variants


class BoundedPrimaryColumnVariantsTest(unittest.TestCase):
    def test_builds_only_deterministic_left_column_crops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "label.jpg"
            Image.new("RGB", (100, 40), "white").save(source)

            variants = build_bounded_primary_column_variants(source, root / "variants")

            self.assertEqual(
                [variant.name for variant in variants],
                ["primary_left_42", "primary_left_50"],
            )
            sizes = []
            for variant in variants:
                self.assertTrue(variant.path.is_file())
                with Image.open(variant.path) as image:
                    sizes.append(image.size)
            self.assertEqual(sizes, [(84, 80), (100, 80)])
            with Image.open(source) as original:
                self.assertEqual(original.size, (100, 40))

    def test_rejects_missing_source_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                build_bounded_primary_column_variants(
                    root / "missing.jpg",
                    root / "variants",
                )


if __name__ == "__main__":
    unittest.main()
