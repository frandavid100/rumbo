import unittest

from nutrition_label_reader import LabelReadResult
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


def reading(status, basis, nutrition, confidence, *reasons):
    return LabelReadResult(status, basis, nutrition, confidence, tuple(reasons), "fixture")


class OCREnsembleTest(unittest.TestCase):
    def test_almost_good_complete_reading_can_be_confirmed(self):
        a = reading('REVIEW', '100_g', {
            'calories': 568.0, 'fat_g': 42.0, 'carbohydrate_g': 32.0, 'protein_g': 10.0
        }, .8495, 'LOW_EXTRACTION_CONFIDENCE')
        b = reading('REVIEW', '100_g', {
            'calories': 568.0, 'fat_g': 42.0
        }, .888, 'MISSING_CORE:carbohydrate_g,protein_g')
        r = fuse_ocr_readings([ParsedOCRReading('psm6', a), ParsedOCRReading('psm11', b)])
        self.assertEqual(r.status, 'DECLARED', r)
        self.assertGreaterEqual(r.corroborated_fields, 2)
        self.assertEqual(r.nutrition['fat_g'], 42.0)
        self.assertEqual(r.nutrition['carbohydrate_g'], 32.0)
        self.assertEqual(r.nutrition['protein_g'], 10.0)

    def test_partial_readings_do_not_get_promoted_on_arithmetic_alone(self):
        a = reading('REVIEW', '100_g', {
            'calories': 427.0, 'fat_g': 9.2, 'carbohydrate_g': 76.0
        }, .762, 'MISSING_CORE:protein_g')
        b = reading('REVIEW', '100_g', {
            'calories': 427.0, 'protein_g': 7.4
        }, .879, 'MISSING_CORE:fat_g,carbohydrate_g')
        r = fuse_ocr_readings([ParsedOCRReading('psm6', a), ParsedOCRReading('psm11', b)])
        self.assertEqual(r.status, 'REVIEW')
        self.assertEqual(r.nutrition['calories'], 427.0)
        self.assertEqual(r.nutrition['protein_g'], 7.4)
        self.assertEqual(r.corroborated_fields, 1)

    def test_conflicting_fields_are_review(self):
        a = reading('REVIEW', '100_g', {
            'calories': 400.0, 'fat_g': 10.0, 'carbohydrate_g': 60.0, 'protein_g': 20.0
        }, .93)
        b = reading('REVIEW', '100_g', {
            'calories': 400.0, 'fat_g': 30.0, 'carbohydrate_g': 20.0, 'protein_g': 20.0
        }, .92)
        r = fuse_ocr_readings([ParsedOCRReading('a', a), ParsedOCRReading('b', b)])
        self.assertEqual(r.status, 'REVIEW')
        self.assertTrue(any(x.startswith('OCR_FIELD_CONFLICT') for x in r.reasons))


if __name__ == '__main__': unittest.main()
