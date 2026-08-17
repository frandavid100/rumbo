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


if __name__ == "__main__":
    unittest.main()
