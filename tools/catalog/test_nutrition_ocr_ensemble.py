import unittest

from nutrition_label_reader import read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


class OCREnsembleTest(unittest.TestCase):
    def test_almost_good_complete_reading_can_be_confirmed(self):
        a = read_nutrition_label("""100 y
Energía 568 kcal
Grasas 429
Hidratos de carbono 329
Proteínas 10 g
Sal 0.03 g
""", extraction_confidence=.8495)
        b = read_nutrition_label("""100 g
Energía 568 kcal
Grasas 429
Hidratos de carbono
Proteínas
Sal 0.03 g
""", extraction_confidence=.888)
        r = fuse_ocr_readings([ParsedOCRReading('psm6', a), ParsedOCRReading('psm11', b)])
        self.assertEqual(r.status, 'DECLARED', r)
        self.assertGreaterEqual(r.corroborated_fields, 2)
        self.assertEqual(r.nutrition['fat_g'], 42.0)
        self.assertEqual(r.nutrition['carbohydrate_g'], 32.0)
        self.assertEqual(r.nutrition['protein_g'], 10.0)

    def test_partial_readings_do_not_get_promoted_on_arithmetic_alone(self):
        a = read_nutrition_label("""100 g
Energía 427 kcal
Grasas 9.2 g
Hidratos de carbono 76 g
Proteínas
Sal .92 g
""", extraction_confidence=.762)
        b = read_nutrition_label("""100 g
Energía 427 kcal
Grasas
Hidratos de carbono
Proteínas 7.4 g
Sal .92 g
""", extraction_confidence=.879)
        r = fuse_ocr_readings([ParsedOCRReading('psm6', a), ParsedOCRReading('psm11', b)])
        self.assertEqual(r.status, 'REVIEW')
        self.assertEqual(r.nutrition['calories'], 427.0)
        self.assertEqual(r.nutrition['protein_g'], 7.4)

    def test_conflicting_fields_are_review(self):
        a = read_nutrition_label("""100 g
Energía 400 kcal
Grasas 10 g
Hidratos de carbono 60 g
Proteínas 20 g
Sal .1 g
""", extraction_confidence=.93)
        b = read_nutrition_label("""100 g
Energía 400 kcal
Grasas 30 g
Hidratos de carbono 20 g
Proteínas 20 g
Sal .1 g
""", extraction_confidence=.92)
        r = fuse_ocr_readings([ParsedOCRReading('a', a), ParsedOCRReading('b', b)])
        self.assertEqual(r.status, 'REVIEW')
        self.assertTrue(any(x.startswith('OCR_FIELD_CONFLICT') for x in r.reasons))


if __name__ == '__main__': unittest.main()
