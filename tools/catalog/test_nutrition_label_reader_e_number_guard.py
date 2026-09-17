import unittest

from mercadona_nutrition_label_percentage_guard import read_nutrition_label


class NutritionLabelReaderENumberGuardTest(unittest.TestCase):
    def test_undotted_e_number_noise_after_fat_label_is_not_a_gram_value(self):
        # Observed EasyOCR ordering for Mercadona product 24541. The ingredient
        # additive token `129 E129:` appears immediately after the total-fat
        # label. It must not be repaired as OCR-damaged `12 g`.
        observed = """Información nutricional por 100 g
Valor energético 1543 kJ / 369 kcal
Grasas/Lípidos
129 E129:
de las cuales saturadas
1.1 g
Hidratos de Carbono
85 g
de los cuales azúcares
69 g
Proteínas
2.1 g
Sal
0.02 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.95)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertIsNotNone(r.nutrition)
        self.assertIsNone(r.nutrition.get("fat_g"), r)
        self.assertIn("MISSING_CORE:fat_g", r.reasons)


if __name__ == "__main__":
    unittest.main()
