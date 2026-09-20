import tempfile
import unittest
from pathlib import Path

from PIL import Image

from label_image_preprocess import build_fallback_variants


class LabelImagePreprocessTest(unittest.TestCase):
    def test_builds_autocontrast_and_overlapping_crops(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "label.jpg"
            Image.new("RGB", (1200, 900), "white").save(source)
            out = Path(td) / "variants"
            variants = build_fallback_variants(source, out)
            names = {v.name for v in variants}
            self.assertEqual(names, {
                "full_autocontrast", "crop_center", "crop_left", "crop_right",
                "crop_top", "crop_bottom",
            })
            self.assertTrue(all(v.path.is_file() for v in variants))
            self.assertTrue(all(v.path.stat().st_size > 0 for v in variants))

    def test_large_image_adds_native_resolution_tiles_below_paddle_limit(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "large-label.jpg"
            Image.new("RGB", (2804, 5220), "white").save(source)
            out = Path(td) / "variants"
            variants = build_fallback_variants(source, out)
            tiles = [v for v in variants if v.name.startswith("native_tile_")]

            self.assertEqual(
                [v.name for v in tiles],
                ["native_tile_r0_c0", "native_tile_r1_c0"],
            )
            self.assertTrue(tiles)
            for tile in tiles:
                with Image.open(tile.path) as image:
                    self.assertLessEqual(max(image.size), 3900)
                    # Native-resolution tiles may crop, but must never upscale the
                    # first-party pixels merely to satisfy Paddle's detector cap.
                    self.assertLessEqual(image.width, 2804)
                    self.assertLessEqual(image.height, 5220)

    def test_legacy_enlarged_crops_never_trigger_paddle_internal_downscale(self):
        # Mercadona p9 URLs commonly request 3600x3600. The previous fixed 1.5x
        # fallback enlargement turned their ~3024 px crops into ~4536 px images,
        # so PaddleOCR immediately shrank them again at its 4000 px detector cap.
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "mercadona-p9.jpg"
            Image.new("RGB", (3600, 3600), "white").save(source)
            out = Path(td) / "variants"
            variants = build_fallback_variants(source, out)

            crop_variants = [v for v in variants if v.name.startswith("crop_")]
            self.assertEqual(len(crop_variants), 5)
            for variant in crop_variants:
                with Image.open(variant.path) as image:
                    self.assertLessEqual(
                        max(image.size), 3900,
                        f"{variant.name} would be downscaled internally by PaddleOCR: {image.size}",
                    )


if __name__ == "__main__":
    unittest.main()
