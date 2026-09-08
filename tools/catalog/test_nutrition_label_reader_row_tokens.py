import unittest
from nutrition_label_reader import read_nutrition_label

class RowTokenRegressionTest(unittest.TestCase):
    def test_observed_fat_translation_tokens(self):
        variants = ('Grasas Lipidos', 'GRASASILíPIDOS', 'GRASAS/LÁPIDOS', 'Grasas/ípidos')
        for row in variants:
            with self.subTest(row=row):
                text = (
                    'INFORMACIÓN NUTRICIONAL\npor 100 ml\n'
                    'VALOR ENERGÉTICO 1382 kJ/335 kcal\n' + row + '\n35 g\n'
                    'de las cuales saturadas 24 g\nHIDRATOS DE CARBONO\n3.1 g\n'
                    'PROTEINAS\n2.0 g\nSAL 0.10 g\n'
                )
                r = read_nutrition_label(text, extraction_confidence=.96)
                self.assertEqual(r.status, 'DECLARED', (row, r))
                self.assertEqual(r.nutrition['fat_g'], 35.0)

    def test_observed_portuguese_total_fat_qualifier(self):
        text = (
            'INFORMACIÓN NUTRICIONAL\nPor 100 g\n'
            'VALOR ENERGÉTICO / ENERGIA\n943 kJ / 224 kcal\n'
            'GRASAS / LÍPIDOS TOTAIS.\n.7.4 g\n'
            'de las cuales saturadas / dos quais saturados\n2.2 g\n'
            'HIDRATOS DE CARBONO\n33 g\nPROTEÍNAS\n5.6 g\nSAL\n1.0 g\n'
        )
        r = read_nutrition_label(text, extraction_confidence=.96)
        self.assertEqual(r.status, 'DECLARED', r)
        self.assertEqual(r.nutrition['fat_g'], 7.4)
        self.assertEqual(r.nutrition['carbohydrate_g'], 33.0)
        self.assertEqual(r.nutrition['protein_g'], 5.6)

    def test_total_fat_qualifier_does_not_disable_prose_guard(self):
        text = (
            'INFORMACIÓN NUTRICIONAL\nPor 100 g\nValor energético 224 kcal\n'
            'GRASAS / LÍPIDOS TOTAIS ingredientes 7.4 g\n'
            'Hidratos de carbono 33 g\nProteínas 5.6 g\nSal 1.0 g\n'
        )
        r = read_nutrition_label(text, extraction_confidence=.96)
        self.assertEqual(r.status, 'REVIEW', r)
        self.assertIn('MISSING_CORE:fat_g', r.reasons)

    def test_observed_protein_underscore_tokens(self):
        for row in ('PROTEINAS_', 'PROTE_NAS .'):
            with self.subTest(row=row):
                text = (
                    'INFORMACIÓN NUTRICIONAL\npor 100 g\nValor energético 110 kJ / 26 kcal\n'
                    'Grasas 0.6 g\nHidratos de carbono 2.4 g\n' + row + '\n2.1 g\nSal 0.08 g\n'
                )
                r = read_nutrition_label(text, extraction_confidence=.96)
                self.assertEqual(r.status, 'DECLARED', (row, r))
                self.assertEqual(r.nutrition['protein_g'], 2.1)

    def test_letter_o_g_is_zero_only_as_complete_macro_cell(self):
        text = (
            'INFORMACIÓN NUTRICIONAL\npor 100 g\nValor energético 878 kJ / 211 kcal\n'
            'Grasas 15 g\nHidratos de carbono\nOg\nProteínas 19 g\nSal 0.18 g\n'
        )
        r = read_nutrition_label(text, extraction_confidence=.96)
        self.assertEqual(r.status, 'DECLARED', r)
        self.assertEqual(r.nutrition['carbohydrate_g'], 0.0)
        bounded = text.replace('Og\nProteínas', '<Og\nProteínas')
        rb = read_nutrition_label(bounded, extraction_confidence=.96)
        self.assertEqual(rb.status, 'REVIEW', rb)
        self.assertIn('MISSING_CORE:carbohydrate_g', rb.reasons)

    def test_protein_prose_guard_is_preserved(self):
        text = (
            'INFORMACIÓN NUTRICIONAL\npor 100 g\nValor energético 100 kcal\n'
            'Grasas 4 g\nHidratos de carbono 10 g\n'
            'Proteínas de leche E-331\nSal 0.2 g\n'
        )
        r = read_nutrition_label(text, extraction_confidence=.96)
        self.assertEqual(r.status, 'REVIEW', r)
        self.assertIn('MISSING_CORE:protein_g', r.reasons)

if __name__ == '__main__':
    unittest.main()
