import unittest

from nutrition_unit_glyph_repair import repair_observed_trailing_g_as_eight


class NutritionUnitGlyphRepairTest(unittest.TestCase):
    def test_repairs_only_observed_core_row_unit_glyph_eight(self):
        observed = """DATOS NUTRICIONALES
VALORES MEDIOS POR CADA 100g DE PRODUCTO
GRASAS
12.208
DE LAS CUALES SATURADAS
4.60g
HIDRATOS DE CARBONO
1.008
DE LOS CUALES AZÚCARES
0.50g
PROTEINAS
33.50g
SAL
3.60 8
"""
        repaired = repair_observed_trailing_g_as_eight(observed)
        self.assertIn("GRASAS\n12.20 g\n", repaired)
        self.assertIn("HIDRATOS DE CARBONO\n1.00 g\n", repaired)
        self.assertIn("PROTEINAS\n33.50g\n", repaired)
        self.assertIn("SAL\n3.60 8\n", repaired)

    def test_same_line_core_row_is_supported(self):
        observed = """Información nutricional por 100 g
Grasas 12.208
Hidratos de carbono 1.008
Proteínas 33.50 g
"""
        repaired = repair_observed_trailing_g_as_eight(observed)
        self.assertIn("Grasas 12.20 g", repaired)
        self.assertIn("Hidratos de carbono 1.00 g", repaired)

    def test_does_not_repair_bounds_or_unrelated_three_decimal_values(self):
        observed = """Información nutricional por 100 g
Grasas
<12.208
Lote
12.208
Hidratos de carbono
1.008 mg
Proteínas
33.50 g
"""
        repaired = repair_observed_trailing_g_as_eight(observed)
        self.assertIn("<12.208", repaired)
        self.assertIn("Lote\n12.208", repaired)
        self.assertIn("1.008 mg", repaired)
        self.assertNotIn("<12.20 g", repaired)

    def test_does_not_touch_three_decimal_token_without_core_label_adjacency(self):
        observed = """Información nutricional por 100 g
Referencia 15700
1.008
Grasas 12.20 g
Hidratos de carbono 1.00 g
Proteínas 33.50 g
"""
        repaired = repair_observed_trailing_g_as_eight(observed)
        self.assertIn("Referencia 15700\n1.008\n", repaired)


if __name__ == "__main__":
    unittest.main()
