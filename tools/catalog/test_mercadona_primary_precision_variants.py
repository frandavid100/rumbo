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
            with Image.open(variants[0].path) as first:
                self.assertEqual(first.size, (126, 180))
                self.assertEqual(first.format, "PNG")
            with Image.open(variants[1].path) as second:
                self.assertEqual(second.size, (150, 180))
                self.assertEqual(second.format, "PNG")

    def test_custom_width_ratio_is_independent_and_does_not_change_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.jpg"
            Image.new("RGB", (100, 60), "white").save(source, quality=90)

            diagnostic = build_precision_primary_column_variants(
                source,
                root / "diagnostic",
                width_ratios=(0.56,),
            )
            defaults = build_precision_primary_column_variants(source, root / "defaults")

            self.assertEqual([variant.name for variant in diagnostic], ["primary_precision_left_56"])
            with Image.open(diagnostic[0].path) as image:
                self.assertEqual(image.size, (168, 180))
                self.assertEqual(image.format, "PNG")
            self.assertEqual(
                [variant.name for variant in defaults],
                ["primary_precision_left_42", "primary_precision_left_50"],
            )

    def test_full_width_diagnostic_variant_preserves_the_entire_bounded_region(self) -> None:
        """A diagnostic-only 1.0 ratio must upscale, not crop, the OCR region."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.jpg"
            Image.new("RGB", (100, 60), "white").save(source, quality=90)

            diagnostic = build_precision_primary_column_variants(
                source,
                root / "diagnostic-full",
                width_ratios=(1.0,),
            )
            defaults = build_precision_primary_column_variants(source, root / "defaults")

            self.assertEqual(
                [variant.name for variant in diagnostic],
                ["primary_precision_left_100"],
            )
            with Image.open(diagnostic[0].path) as image:
                self.assertEqual(image.size, (300, 180))
                self.assertEqual(image.format, "PNG")
            self.assertEqual(
                [variant.name for variant in defaults],
                ["primary_precision_left_42", "primary_precision_left_50"],
            )

    def test_invalid_width_ratio_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.jpg"
            Image.new("RGB", (100, 60), "white").save(source, quality=90)
            for ratios in ((), (0.0,), (1.01,)):
                with self.subTest(ratios=ratios):
                    with self.assertRaises(ValueError):
                        build_precision_primary_column_variants(
                            source,
                            root / "out",
                            width_ratios=ratios,
                        )

    def test_missing_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                build_precision_primary_column_variants(
                    Path(td) / "missing.jpg", Path(td) / "out"
                )


if __name__ == "__main__":
    unittest.main()
