import unittest

import nutrition_label_reader as reader
import mercadona_protcinas_typo_retry as retry


class MercadonaProtcinasTypoRetryTest(unittest.TestCase):
    def test_exact_standalone_protcinas_row_is_repaired_without_changing_values(self):
        observed = """INFORMACION NUTRICIONAL
Por 100 g
Valor energetico 640 kJ / 153 kcal
Grasas
8.9 g
Hidratos de carbono
0 g
Protcinas
18 g
Sal
0.15 g
"""
        original = reader.normalize_text
        try:
            retry.install_protcinas_normalizer()
            result = reader.read_nutrition_label(observed, extraction_confidence=.98)
        finally:
            reader.normalize_text = original

        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.nutrition, {
            "calories": 153.0,
            "fat_g": 8.9,
            "carbohydrate_g": 0.0,
            "protein_g": 18.0,
        })

    def test_protcinas_in_prose_is_not_repaired_as_a_row_label(self):
        observed = """INFORMACION NUTRICIONAL
Por 100 g
Valor energetico 640 kJ / 153 kcal
Grasas 8.9 g
Hidratos de carbono 0 g
ingrediente protcinas de leche 18 g
Sal 0.15 g
"""
        original = reader.normalize_text
        try:
            retry.install_protcinas_normalizer()
            result = reader.read_nutrition_label(observed, extraction_confidence=.98)
        finally:
            reader.normalize_text = original

        self.assertEqual(result.status, "REVIEW", result)
        self.assertIn("MISSING_CORE:protein_g", result.reasons)

    def test_normalizer_alone_preserves_numeric_tokens(self):
        source = "Protcinas\n18 9\n"
        normalized = retry.normalize_text_with_protcinas(source)
        self.assertEqual(normalized, "Proteinas\n18 9")


if __name__ == "__main__":
    unittest.main()
