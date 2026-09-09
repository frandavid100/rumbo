import unittest

from nutrition_label_reader import read_nutrition_label


def label(calories: float, fat: float, carbs: float, protein: float) -> str:
    return f"""Información nutricional por 100 g
Valor energético 1000 kJ / {calories} kcal
Grasas {fat} g
Hidratos de carbono {carbs} g
Proteínas {protein} g
Sal 1 g
"""


class NutritionEnergyCoherenceGuardTest(unittest.TestCase):
    def test_rejects_observed_kabanos_tuple_just_inside_legacy_ten_percent_band(self):
        # Mercadona 35197: all OCR families read the same printed tuple, but
        # 35*9 + 4*4 + 13*4 = 383 kcal versus 349 kcal on the label. Automatic
        # OCR usability must prefer precision and route this to REVIEW.
        result = read_nutrition_label(label(349, 35, 4, 13), extraction_confidence=.99)
        self.assertEqual(result.status, "REVIEW", result)
        self.assertTrue(
            any(reason.startswith("ENERGY_MACRO_MISMATCH:383.0") for reason in result.reasons),
            result.reasons,
        )

    def test_keeps_current_wave_coherent_promotions_inside_narrow_rounding_band(self):
        # Four other exact-image wave observations remain compatible with the
        # tighter guard; this prevents fixing 35197 by simply breaking the wave.
        fixtures = (
            (500, 25, 62, 4.6),
            (356, 0, 0, 89),
            (553, 33, 54, 6.7),
            (324, 24, 0, 26),
        )
        for values in fixtures:
            with self.subTest(values=values):
                result = read_nutrition_label(label(*values), extraction_confidence=.99)
                self.assertEqual(result.status, "DECLARED", result)


if __name__ == "__main__":
    unittest.main()
