from __future__ import annotations

import unittest

from mercadona_nutrition_label_percentage_guard import (
    guard_interleaved_ingredient_fat_percent,
    read_nutrition_label,
)


class MercadonaIngredientFatPercentageGuardTests(unittest.TestCase):
    def test_interleaved_ingredient_percentage_cannot_become_total_fat(self):
        text = """INFORMACIÓN / INFORMAÇÃO NUTRICIONAL
Valores medios / médios
Por 100 g
grasa (16%). emulgente (lecitina). preparado de cacao
Valor energético / Energia
2032 kJ / 488 kcal
Grasas / Lípidos
33.5 g
de las cuales saturadas
5.9 g
Hidratos de Carbono
41.29 g
de los cuales azúcares
29.0 g
Proteínas
4.59 g
Sal
0.1 g
"""
        guarded, changed = guard_interleaved_ingredient_fat_percent(text)
        self.assertTrue(changed)
        self.assertIn("grasa_ingrediente (16%)", guarded)
        self.assertIn("Grasas / Lípidos\n33.5 g", guarded)

        result = read_nutrition_label(text, extraction_confidence=0.95)
        self.assertEqual(result.status, "DECLARED")
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(
            result.nutrition,
            {
                "calories": 488.0,
                "fat_g": 33.5,
                "carbohydrate_g": 41.29,
                "protein_g": 4.59,
            },
        )

    def test_ocr_reordered_pre_heading_ingredient_context_is_guarded(self):
        # Regression from product 84736 / Tesseract psm4/psm6: OCR can emit the
        # ingredient fragment before the nutrition heading/row anchors, so a
        # heading-only guard leaves a false 16 g fat candidate alive.
        text = """grasa (16%). emulgente (lecitina). preparado de cacao
Valores medios / médios
Por 100 g
Valor energético / Energia
2032 kJ / 488 kcal
Grasas / Lípidos
33.5 g
de las cuales saturadas
7.6 g
Hidratos de Carbono
41.2 g
de los cuales azúcares
32.6 g
Fibra alimentaria / Fibra
1.9 g
Proteínas
4.5 g
Sal
0.73 g
"""
        guarded, changed = guard_interleaved_ingredient_fat_percent(text)
        self.assertTrue(changed)
        self.assertTrue(guarded.startswith("grasa_ingrediente (16%). emulgente"))
        self.assertIn("Grasas / Lípidos\n33.5 g", guarded)

        result = read_nutrition_label(text, extraction_confidence=0.95)
        self.assertEqual(result.status, "DECLARED")
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(
            result.nutrition,
            {
                "calories": 488.0,
                "fat_g": 33.5,
                "carbohydrate_g": 41.2,
                "protein_g": 4.5,
            },
        )

    def test_real_fat_row_with_reference_percentage_is_untouched(self):
        text = """INFORMACIÓN NUTRICIONAL
Por 100 g
Valor energético 2032 kJ / 488 kcal
Grasas 33.5 g (48%)
Hidratos de Carbono 41.29 g
Proteínas 4.59 g
Sal 0.1 g
"""
        guarded, changed = guard_interleaved_ingredient_fat_percent(text)
        self.assertFalse(changed)
        self.assertEqual(guarded, text)

        result = read_nutrition_label(text, extraction_confidence=0.95)
        self.assertEqual(result.status, "DECLARED")
        self.assertEqual(result.nutrition["fat_g"], 33.5)

    def test_bare_pre_heading_percentage_without_ingredient_context_is_untouched(self):
        text = """grasa (16%)
INFORMACIÓN NUTRICIONAL
Por 100 g
Valor energético 2032 kJ / 488 kcal
Grasas 33.5 g
Hidratos de Carbono 41.29 g
Proteínas 4.59 g
Sal 0.1 g
"""
        guarded, changed = guard_interleaved_ingredient_fat_percent(text)
        self.assertFalse(changed)
        self.assertEqual(guarded, text)


if __name__ == "__main__":
    unittest.main()
