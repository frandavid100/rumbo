import unittest

from nutrition_label_reader import LabelReadResult
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


def reading(status, basis, nutrition, confidence, *reasons):
    return LabelReadResult(status, basis, nutrition, confidence, tuple(reasons), "fixture")


class OCREnsembleTest(unittest.TestCase):
    def test_same_engine_layouts_do_not_count_as_independent_corroboration(self):
        a = reading('REVIEW', '100_g', {
            'calories': 568.0, 'fat_g': 42.0, 'carbohydrate_g': 32.0, 'protein_g': 10.0
        }, .8495, 'LOW_EXTRACTION_CONFIDENCE')
        b = reading('REVIEW', '100_g', {
            'calories': 568.0, 'fat_g': 42.0
        }, .888, 'MISSING_CORE:carbohydrate_g,protein_g')
        r = fuse_ocr_readings([
            ParsedOCRReading('psm6', a, engine_family='tesseract'),
            ParsedOCRReading('psm11', b, engine_family='tesseract'),
        ])
        self.assertEqual(r.status, 'REVIEW', r)
        self.assertEqual(r.independent_engine_families, 1)
        self.assertEqual(r.corroborated_fields, 0)
        self.assertIn('INSUFFICIENT_INDEPENDENT_OCR_ENGINES', r.reasons)

    def test_same_engine_layouts_can_fill_complementary_fields_without_becoming_extra_evidence(self):
        paddle = reading('DECLARED', '100_g', {
            'calories': 184.0, 'fat_g': 12.0, 'carbohydrate_g': 2.0, 'protein_g': 17.0
        }, .98)
        tess_psm6 = reading('REVIEW', None, {
            'calories': 184.0, 'fat_g': 12.0, 'protein_g': 17.0
        }, .81, 'MISSING_100G_100ML_BASIS', 'MISSING_CORE:carbohydrate_g')
        tess_psm11 = reading('REVIEW', '100_g', {
            'carbohydrate_g': 2.0
        }, .86, 'MISSING_CORE:calories,fat_g,protein_g')
        r = fuse_ocr_readings([
            ParsedOCRReading('paddle-region', paddle, engine_family='paddleocr'),
            ParsedOCRReading('tesseract-psm6', tess_psm6, engine_family='tesseract'),
            ParsedOCRReading('tesseract-psm11', tess_psm11, engine_family='tesseract'),
        ])
        self.assertEqual(r.status, 'DECLARED', r)
        self.assertEqual(r.independent_engine_families, 2)
        self.assertEqual(r.corroborated_fields, 4)
        self.assertEqual(r.nutrition, {
            'calories': 184.0, 'fat_g': 12.0, 'carbohydrate_g': 2.0, 'protein_g': 17.0
        })

    def test_independent_engines_can_confirm_a_complete_reading(self):
        a = reading('REVIEW', '100_g', {
            'calories': 568.0, 'fat_g': 42.0, 'carbohydrate_g': 32.0, 'protein_g': 10.0
        }, .8495, 'LOW_EXTRACTION_CONFIDENCE')
        b = reading('REVIEW', '100_g', {
            'calories': 568.0, 'fat_g': 42.0, 'carbohydrate_g': 32.0, 'protein_g': 10.0
        }, .91)
        r = fuse_ocr_readings([
            ParsedOCRReading('psm6', a, engine_family='tesseract'),
            ParsedOCRReading('paddle-region', b, engine_family='paddleocr'),
        ])
        self.assertEqual(r.status, 'DECLARED', r)
        self.assertGreaterEqual(r.corroborated_fields, 4)
        self.assertEqual(r.independent_engine_families, 2)
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
        r = fuse_ocr_readings([
            ParsedOCRReading('psm6', a, engine_family='tesseract'),
            ParsedOCRReading('paddle-region', b, engine_family='paddleocr'),
        ])
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
        r = fuse_ocr_readings([
            ParsedOCRReading('tesseract', a, engine_family='tesseract'),
            ParsedOCRReading('paddle', b, engine_family='paddleocr'),
        ])
        self.assertEqual(r.status, 'REVIEW')
        self.assertTrue(any(x.startswith('OCR_FIELD_CONFLICT') for x in r.reasons))


if __name__ == '__main__': unittest.main()
