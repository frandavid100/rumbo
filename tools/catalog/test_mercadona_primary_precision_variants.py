from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from PIL import Image

from mercadona_primary_precision_variants import build_precision_primary_column_variants


class MercadonaPrimaryPrecisionVariantsTest(unittest.TestCase):
    def test_builds_only_lossless_independent_three_x_primary_column_crops(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.jpg"
            Image.new("RGB", (100, 60), "white").save(source, quality=90)

            variants = build_precision_primary_column_variants(source, root / "out")

            self.assertEqual(
                [variant.name for variant in variants],
                ["primary_precision_left_42", "primary_precision_left_50"],
            )
            self.assertTrue(all(variant.path.suffix == ".png" for variant in variants))
            self.assertEqual(Image.open(variants[0].path).size, (126, 180))
            self.assertEqual(Image.open(variants[1].path).size, (150, 180))
            self.assertEqual(Image.open(variants[0].path).format, "PNG")
            self.assertEqual(Image.open(variants[1].path).format, "PNG")

    def test_missing_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                build_precision_primary_column_variants(
                    Path(td) / "missing.jpg", Path(td) / "out"
                )


if __name__ == "__main__":
    unittest.main()
