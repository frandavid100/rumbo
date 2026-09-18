import unittest
from unittest.mock import patch

import nutrition_label_reader as reader
from mercadona_carb_row_label_typo_rescue import normalize_carb_row_label_typos


class MercadonaCarbRowLabelTypoRescueTest(unittest.TestCase):
    def _read_with_targeted_normalizer(self, text: str):
        with patch.object(reader, "normalize_text", normalize_carb_row_label_typos):
            return reader.read_nutrition_label(text, extraction_confidence=.98)

    def test_observed_line_initial_row_label_typos_are_repaired_without_numeric_edits(self):
        template = """Información nutricional
por 100 ml
Valor energético 48 kJ (11 kcal)
Grasas 0.0 g
{label}
2.4 g
Proteínas 0.0 g
Sal 0.02 g
"""
        for label in ("Nidratos de carbono", "hretos de carbono"):
            with self.subTest(label=label):
                normalized = normalize_carb_row_label_typos(template.format(label=label))
                self.assertIn("Hidratos de carbono\n2.4 g", normalized)
                self.assertIn("48 kJ (11 kcal)", normalized)
                self.assertIn("0.02 g", normalized)
                result = self._read_with_targeted_normalizer(template.format(label=label))
                self.assertEqual(result.status, "DECLARED", result)
                self.assertEqual(result.nutrition["carbohydrate_g"], 2.4)

    def test_mid_line_or_real_nitratos_text_is_not_rewritten(self):
        text = """Información nutricional por 100 ml
Nota hretos de carbono 2.4 g
Nitratos de carbono 7.9 g
Valor energético 48 kJ (11 kcal)
Grasas 0 g
Proteínas 0 g
"""
        normalized = normalize_carb_row_label_typos(text)
        self.assertIn("Nota hretos de carbono 2.4 g", normalized)
        self.assertIn("Nitratos de carbono 7.9 g", normalized)
        self.assertNotIn("Hidratos de carbono", normalized)

    def test_targeted_label_repair_does_not_bypass_energy_macro_coherence(self):
        observed = """Información nutricional
por 100 ml
Valor energético 80 kcal
Grasas 0 g
Nidratos de carbono
2.4 g
Proteínas 0 g
Sal 0.02 g
"""
        result = self._read_with_targeted_normalizer(observed)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertTrue(any(reason.startswith("ENERGY_MACRO_MISMATCH") for reason in result.reasons), result)

    def test_targeted_label_repair_does_not_bypass_multiple_column_guard(self):
        observed = """Información nutricional
Por 100 ml
Por 100 ml
Valor energético 48 kJ (11 kcal) 159 kJ (37 kcal)
Grasas 0 g 0 g
hretos de carbono 2.4 g 7.9 g
Proteínas 0 g 0 g
"""
        result = self._read_with_targeted_normalizer(observed)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertIn("MULTIPLE_NUTRITION_COLUMNS", result.reasons)


if __name__ == "__main__":
    unittest.main()
