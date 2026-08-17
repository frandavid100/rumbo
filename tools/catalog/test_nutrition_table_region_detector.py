import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from nutrition_table_region_detector import OCRWord, detect_nutrition_regions


class NutritionRegionDetectorTest(unittest.TestCase):
    def test_detects_compact_marker_region(self):
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / 'pack.png'
            Image.new('RGB', (1000, 1000), 'white').save(image_path)
            words = [
                OCRWord('ingredientes', .92, 80, 100, 100, 20),
                OCRWord('Valor', .95, 570, 420, 55, 24),
                OCRWord('energético', .94, 630, 420, 100, 24),
                OCRWord('568', .97, 800, 420, 45, 24),
                OCRWord('kcal', .97, 850, 420, 45, 24),
                OCRWord('Grasas', .96, 570, 470, 75, 24),
                OCRWord('42', .96, 800, 470, 30, 24),
                OCRWord('Hidratos', .95, 570, 520, 85, 24),
                OCRWord('32', .96, 800, 520, 30, 24),
                OCRWord('Proteínas', .95, 570, 570, 90, 24),
                OCRWord('10', .96, 800, 570, 30, 24),
                OCRWord('100', .93, 570, 370, 40, 22),
                OCRWord('g', .93, 615, 370, 15, 22),
            ]
            regions = detect_nutrition_regions(
                image_path, Path(td) / 'regions', word_extractor=lambda _: words
            )
            self.assertTrue(regions)
            best = regions[0]
            self.assertGreaterEqual(len(best.marker_kinds), 4)
            self.assertIn('energy', best.marker_kinds)
            self.assertIn('protein', best.marker_kinds)
            self.assertTrue(best.path.exists())
            l, t, r, b = best.box
            self.assertLessEqual(l, 570)
            self.assertGreaterEqual(r, 845)
            self.assertLessEqual(t, 420)
            self.assertGreaterEqual(b, 594)

    def test_does_not_invent_region_from_unrelated_text(self):
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / 'pack.png'
            Image.new('RGB', (600, 600), 'white').save(image_path)
            words = [
                OCRWord('Hacendado', .98, 50, 80, 100, 25),
                OCRWord('Conservar', .92, 50, 150, 90, 20),
                OCRWord('frío', .90, 145, 150, 35, 20),
            ]
            regions = detect_nutrition_regions(
                image_path, Path(td) / 'regions', word_extractor=lambda _: words
            )
            self.assertEqual(regions, [])


if __name__ == '__main__':
    unittest.main()
