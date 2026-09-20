import unittest

from nutrition_label_reader import LabelReadResult
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


class SplitBoundedCarbohydrateLabelTest(unittest.TestCase):
    def test_split_hidratos_de_bound_carbono_stays_non_exact(self):
        # Fresh Mercadona OCR can wrap the row as:
        #   Hidratos de
        #   <0.5 g
        #   Carbono
        # The printed inequality is still a bound and must veto any exact 0.5 g
        # candidate recovered by another OCR layout/family.
        split_bound = LabelReadResult(
            'DECLARED',
            '100_g',
            {'calories': 160.0, 'fat_g': 9.8, 'carbohydrate_g': 0.5, 'protein_g': 17.9},
            .97,
            tuple(),
            '100 g\nValor energético\n160 kcal\nGrasas\n9.8 g\nHidratos de\n<0.5 g\nCarbono\nProteínas\n17.9 g',
        )
        exact_without_glyph = LabelReadResult(
            'DECLARED',
            '100_g',
            {'calories': 160.0, 'fat_g': 9.8, 'carbohydrate_g': 0.5, 'protein_g': 17.9},
            .96,
            tuple(),
            '100 g\nValor energético\n160 kcal\nGrasas\n9.8 g\nHidratos de Carbono\n0.5 g\nProteínas\n17.9 g',
        )

        result = fuse_ocr_readings([
            ParsedOCRReading('paddleocr', split_bound, engine_family='paddleocr'),
            ParsedOCRReading('tesseract', exact_without_glyph, engine_family='tesseract'),
        ])

        self.assertEqual(result.status, 'REVIEW', result)
        self.assertIsNotNone(result.nutrition)
        self.assertNotIn('carbohydrate_g', result.nutrition)
        self.assertTrue(
            any(reason.startswith('OCR_BOUNDED_CORE_VALUE:carbohydrate_g:') for reason in result.reasons),
            result,
        )


if __name__ == '__main__':
    unittest.main()
