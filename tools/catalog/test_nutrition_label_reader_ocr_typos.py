import unittest

from nutrition_label_reader import read_nutrition_label


class NutritionLabelReaderOCRTyposTest(unittest.TestCase):
    def test_observed_kcal_unit_variants_are_accepted_only_after_numeric_value(self):
        template = """Información nutricional por 100 g
Valor energético 503 kJ / 120 {unit}
Grasas 4 g
Hidratos de carbono 0 g
Proteínas 21 g
Sal 0.2 g
"""
        for unit in ("Keal", "kcai", "kcall", "kcali"):
            with self.subTest(unit=unit):
                r = read_nutrition_label(template.format(unit=unit), extraction_confidence=.98)
                self.assertEqual(r.status, "DECLARED", r)
                self.assertEqual(r.nutrition["calories"], 120.0)

        prose = template.format(unit="kcal").replace("120 kcal", "120 energía Keal")
        r = read_nutrition_label(prose, extraction_confidence=.98)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertIn("MISSING_CORE:calories", r.reasons)

    def test_dropped_k_ical_variant_requires_explicit_same_line_kj_pair(self):
        paired = """Información nutricional por 100 g
Valor energético 503 KJ 120 Ícal
Grasas 4 g
Hidratos de carbono 0 g
Proteínas 21 g
Sal 0.2 g
"""
        r = read_nutrition_label(paired, extraction_confidence=.98)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.nutrition["calories"], 120.0)

        unpaired = paired.replace("503 KJ 120 Ícal", "120 Ícal")
        r = read_nutrition_label(unpaired, extraction_confidence=.98)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertIn("MISSING_CORE:calories", r.reasons)

    def test_exact_standalone_fat_label_variants_are_supported_but_prose_is_not(self):
        template = """Información nutricional por 100 g
Valor energético 503 kJ / 120 kcal
{fat_label}
4 g
de las cuales saturadas 1.3 g
Hidratos de carbono 0 g
Proteínas 21 g
Sal 0.2 g
"""
        for fat_label in ("Brasas", "Vrasas"):
            with self.subTest(fat_label=fat_label):
                r = read_nutrition_label(template.format(fat_label=fat_label), extraction_confidence=.98)
                self.assertEqual(r.status, "DECLARED", r)
                self.assertEqual(r.nutrition["fat_g"], 4.0)

        prose = template.format(fat_label="Cocinar a las brasas 20 min")
        r = read_nutrition_label(prose, extraction_confidence=.98)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertIn("MISSING_CORE:fat_g", r.reasons)

    def test_observed_pollolike_label_recovers_only_printed_values(self):
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g
Valores medios
Valor energetico
503 KJ 120 Keal
Brasas
4.0 g
de las cuales saturadas
1.3 g
Hidratos de carbono
0 g
de los cuales azucares
0 g
Proteinas
21 g
Sal
0.20 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(r.status, "DECLARED", r)
        self.assertEqual(r.nutrition, {
            "calories": 120.0,
            "fat_g": 4.0,
            "carbohydrate_g": 0.0,
            "protein_g": 21.0,
        })

    def test_typo_support_does_not_bypass_energy_macro_coherence(self):
        observed = """Información nutricional por 100 g
Valor energético 503 kJ / 420 Keal
Brasas
4 g
Hidratos de carbono 0 g
Proteínas 21 g
Sal 0.2 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertTrue(any(reason.startswith("ENERGY_MACRO_MISMATCH") for reason in r.reasons))

    def test_typo_support_does_not_bypass_multiple_column_guard(self):
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g de peso neto
Por 100 g de peso escurrido
Valor energético 333 kJ / 79 Keal 417 kJ / 98 kcal
Brasas 0.6 g 1.2 g
Hidratos de carbono 0.9 g 1.1 g
Proteínas 18 g 21 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.99)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertIn("MULTIPLE_NUTRITION_COLUMNS", r.reasons)


if __name__ == "__main__":
    unittest.main()
