import unittest

from mercadona_nutrition_interleaved_marker_replay import (
    strip_interleaved_packaging_marker_lines,
)
from nutrition_label_reader import read_nutrition_label


class MercadonaInterleavedMarkerReplayTest(unittest.TestCase):
    def test_removes_packaging_marker_only_when_it_clips_missing_core_row(self):
        observed = """INFORMACIÓN NUTRICIONAL
VALORES MEDIOS Por 100 g
VALOR ENERGÉTICO
910 kJ / 220 kcal
GRASAS
13 g
- de las cuales saturadas
1.5 g
HIDRATOS DE CARBONO
15 g
Consumir preferentemente antes del fin de:
- de los cuales azúcares
0.8 g
Nº de Lote:
PROTEINAS
11 g
SAL
1.3 g
"""
        before = read_nutrition_label(observed, extraction_confidence=.96)
        self.assertEqual(before.status, "REVIEW", before)
        self.assertIn("MISSING_CORE:protein_g", before.reasons)

        cleaned, removed = strip_interleaved_packaging_marker_lines(
            observed, missing_core_field="protein_g"
        )
        self.assertEqual(removed, ("consumir preferentemente",))
        self.assertNotIn("Consumir preferentemente antes del fin de:", cleaned)
        after = read_nutrition_label(cleaned, extraction_confidence=.96)
        self.assertEqual(after.status, "DECLARED", after)
        self.assertEqual(after.nutrition, {
            "calories": 220.0,
            "fat_g": 13.0,
            "carbohydrate_g": 15.0,
            "protein_g": 11.0,
        })

    def test_does_not_remove_marker_after_target_core_row(self):
        observed = """INFORMACIÓN NUTRICIONAL por 100 g
Valor energético 910 kJ / 220 kcal
Grasas 13 g
Hidratos de Carbono 15 g
Proteínas 11 g
Consumir preferentemente antes del fin de: ver envase
Sal 1.3 g
"""
        cleaned, removed = strip_interleaved_packaging_marker_lines(
            observed, missing_core_field="protein_g"
        )
        self.assertEqual(cleaned, observed)
        self.assertEqual(removed, ())

    def test_does_not_remove_marker_without_explicit_nutrition_heading(self):
        observed = """100 g
Valor energético 220 kcal
Grasas 13 g
Hidratos de Carbono 15 g
Consumir preferentemente antes del fin de:
Proteínas 11 g
"""
        cleaned, removed = strip_interleaved_packaging_marker_lines(
            observed, missing_core_field="protein_g"
        )
        self.assertEqual(cleaned, observed)
        self.assertEqual(removed, ())

    def test_does_not_remove_marker_when_target_row_is_not_nearby(self):
        observed = """INFORMACIÓN NUTRICIONAL por 100 g
Valor energético 220 kcal
Grasas 13 g
Hidratos de Carbono 15 g
Consumir preferentemente antes del fin de:
texto uno
texto dos
texto tres
texto cuatro
texto cinco
texto seis
texto siete
texto ocho
texto nueve
Proteínas 11 g
"""
        cleaned, removed = strip_interleaved_packaging_marker_lines(
            observed, missing_core_field="protein_g"
        )
        self.assertEqual(cleaned, observed)
        self.assertEqual(removed, ())

    def test_inequality_is_still_not_promoted(self):
        observed = """INFORMACIÓN NUTRICIONAL por 100 g
Valor energético 163 kcal
Grasas 9.1 g
Proteínas 20 g
Consumir preferentemente antes del fin de:
Hidratos de Carbono <0.5 g
Sal 1.4 g
"""
        cleaned, removed = strip_interleaved_packaging_marker_lines(
            observed, missing_core_field="carbohydrate_g"
        )
        self.assertEqual(removed, ("consumir preferentemente",))
        parsed = read_nutrition_label(cleaned, extraction_confidence=.98)
        self.assertEqual(parsed.status, "REVIEW", parsed)
        self.assertIn("MISSING_CORE:carbohydrate_g", parsed.reasons)

    def test_marker_text_inside_prose_is_not_rewritten(self):
        observed = """INFORMACIÓN NUTRICIONAL por 100 g
Valor energético 220 kcal
Grasas 13 g
Hidratos de Carbono 15 g
Nota: consumir preferentemente antes del fin de la fecha indicada.
Proteínas 11 g
"""
        cleaned, removed = strip_interleaved_packaging_marker_lines(
            observed, missing_core_field="protein_g"
        )
        self.assertEqual(cleaned, observed)
        self.assertEqual(removed, ())


if __name__ == "__main__":
    unittest.main()
