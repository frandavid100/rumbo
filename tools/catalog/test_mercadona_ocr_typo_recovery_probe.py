import unittest

from mercadona_ocr_typo_recovery_probe import _safe_fuse, repair_observed_ocr_typos
from nutrition_label_reader import read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading


class MercadonaOCRTypoRecoveryProbeTest(unittest.TestCase):
    def test_repairs_observed_keal_energy_unit_only_after_number(self):
        repaired, repairs = repair_observed_ocr_typos("Valor energético 503 kJ 120 Keal\n")
        self.assertIn("120 kcal", repaired)
        self.assertEqual(repairs, ("ENERGY_UNIT_OCR_VARIANT",))

    def test_repairs_observed_kcai_and_kcall_units(self):
        repaired, repairs = repair_observed_ocr_typos("418 kcai\n529 kcall\n")
        self.assertEqual(repaired, "418 kcal\n529 kcal\n")
        self.assertEqual(repairs, ("ENERGY_UNIT_OCR_VARIANT",))

    def test_dropped_k_is_repaired_only_with_explicit_kj_pair(self):
        repaired, repairs = repair_observed_ocr_typos("Valor enor: ético 503KJ 120 Ícal\n")
        self.assertIn("503KJ 120 kcal", repaired)
        self.assertEqual(repairs, ("ENERGY_UNIT_DROPPED_K",))

        untouched, repairs = repair_observed_ocr_typos("Ración 120 Ícal\n")
        self.assertEqual(untouched, "Ración 120 Ícal\n")
        self.assertEqual(repairs, ())

    def test_repairs_only_exact_standalone_fat_label_variants(self):
        repaired, repairs = repair_observed_ocr_typos("Brasas\n4.0 g\nde las cuales saturadas\n1.3 g\n")
        self.assertTrue(repaired.startswith("Grasas\n4.0 g"))
        self.assertEqual(repairs, ("FAT_LABEL_OCR_VARIANT",))

        untouched, repairs = repair_observed_ocr_typos("Cocinar a las brasas 20 min\n")
        self.assertEqual(untouched, "Cocinar a las brasas 20 min\n")
        self.assertEqual(repairs, ())

    def test_observed_pollolike_text_becomes_complete_only_from_printed_values(self):
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
        repaired, repairs = repair_observed_ocr_typos(observed)
        self.assertEqual(set(repairs), {"ENERGY_UNIT_OCR_VARIANT", "FAT_LABEL_OCR_VARIANT"})
        parsed = read_nutrition_label(repaired, extraction_confidence=.95)
        self.assertEqual(parsed.status, "DECLARED", parsed)
        self.assertEqual(parsed.nutrition, {
            "calories": 120.0,
            "fat_g": 4.0,
            "carbohydrate_g": 0.0,
            "protein_g": 21.0,
        })

    def test_repairs_do_not_bypass_energy_macro_coherence(self):
        observed = """Información nutricional por 100 g
Valor energético 503 kJ 420 Keal
Brasas
4.0 g
Hidratos de carbono 0 g
Proteínas 21 g
Sal 0.2 g
"""
        repaired, _ = repair_observed_ocr_typos(observed)
        parsed = read_nutrition_label(repaired, extraction_confidence=.99)
        self.assertEqual(parsed.status, "REVIEW")
        self.assertTrue(any(reason.startswith("ENERGY_MACRO_MISMATCH") for reason in parsed.reasons))

    def test_repairs_do_not_bypass_multiple_column_guard(self):
        observed = """INFORMACIÓN NUTRICIONAL
Por 100 g de peso neto
Por 100 g de peso escurrido
Valor energético 333 kJ / 79 Keal 417 kJ / 98 kcal
Brasas 0.6 g 1.2 g
Hidratos de carbono 0.9 g 1.1 g
Proteínas 18 g 21 g
"""
        repaired, _ = repair_observed_ocr_typos(observed)
        parsed = read_nutrition_label(repaired, extraction_confidence=.99)
        self.assertEqual(parsed.status, "REVIEW")
        self.assertIn("MULTIPLE_NUTRITION_COLUMNS", parsed.reasons)

    def test_safe_fuse_ignores_review_only_poison_after_two_declared_engines_agree(self):
        good = """Información nutricional por 100 g
Valor energético 503 kJ / 120 kcal
Grasas 4 g
Hidratos de carbono 0 g
Proteínas 21 g
Sal 0.2 g
"""
        poison = good.replace("120 kcal", "420 kcal")
        paddle = read_nutrition_label(good, extraction_confidence=.96)
        tess = read_nutrition_label(good, extraction_confidence=.94)
        easy_review = read_nutrition_label(poison, extraction_confidence=.92)
        self.assertEqual(paddle.status, "DECLARED")
        self.assertEqual(tess.status, "DECLARED")
        self.assertEqual(easy_review.status, "REVIEW")
        fused = _safe_fuse([
            ParsedOCRReading("paddleocr:x", paddle, .96, "paddleocr"),
            ParsedOCRReading("tesseract-psm11:x", tess, .94, "tesseract"),
            ParsedOCRReading("easyocr:x", easy_review, .92, "easyocr"),
        ])
        self.assertEqual(fused.status, "DECLARED", fused)
        self.assertEqual(fused.nutrition["calories"], 120.0)
        self.assertEqual(fused.independent_engine_families, 2)
        self.assertEqual(fused.corroborated_fields, 4)


if __name__ == "__main__":
    unittest.main()
