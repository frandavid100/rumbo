import unittest

from mercadona_ocr_continuity_rescue import rescue_read


class MercadonaOCRContinuityRescueTest(unittest.TestCase):
    def test_inline_single_line_table_recovers_core_without_touching_values(self):
        observed = """NFORMACIÓN NUTRICIONAL/INFORMAÇÃO NUTRICIONAL: Valores medios por 100g: Valor energético/Energia:
536-kJ (128 kcal) -Grasas/ Lípidos:5.8 g (de las cuales ácidos grasos saturados: 1.23 g)
Hidratos de carbono: 2.42 g (de los cuales azúcares: <0.10 g) - Proteínas: 16.47 g -Sal: 0.793 g.
"""
        result = rescue_read(observed)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition, {
            "calories": 128.0,
            "fat_g": 5.8,
            "carbohydrate_g": 2.42,
            "protein_g": 16.47,
        })

    def test_packaging_heading_interleaved_inside_table_does_not_clip_later_rows(self):
        observed = """INFORMACIÓN NUTRICIONAL/ INFORMAÇÃO NUTRICIONAL
Valores medios / médios
Por 100 g
Valor energético / Energia
128 kJ / 31 kcal
Grasas / Lípidos
0.3 g
CONSERVACIÓN EN EL HOGAR/ CONSERVAÇÃO EM CASA
de las cuales saturadas / dos quais saturados
0.1g
Conservar a -18 °C.
3.8 g
Hidratos de carbono
de los cuales azúcares / dos quais açúcares
3.0g
Fibra alimentaria / Fibra
2.3 g
Proteínas
2.0g
Sal
0.02g
"""
        result = rescue_read(observed)
        self.assertEqual(result.basis, "100_g")
        self.assertEqual(result.nutrition["calories"], 31.0)
        self.assertEqual(result.nutrition["fat_g"], 0.3)
        self.assertEqual(result.nutrition["carbohydrate_g"], 3.8)
        self.assertEqual(result.nutrition["protein_g"], 2.0)

    def test_dotted_value_before_label_is_allowed_only_as_dedicated_row(self):
        observed = """Información nutricional por cada 100 g.
Valor energético......614 kJ / 147 kcal
.. 8.4 g
Grasas.
de las cuales saturadas.
.. 1.3 g
..12g
Hidratos de carbono
de los cuales azúcares
.1.9g
Proteínas.
.5.5 g
Sal 1.1 g
"""
        result = rescue_read(observed)
        self.assertEqual(result.nutrition["fat_g"], 8.4)
        self.assertEqual(result.nutrition["carbohydrate_g"], 12.0)
        self.assertEqual(result.nutrition["protein_g"], 5.5)

    def test_parallel_columns_reject_value_before_label_choice(self):
        observed = """INFORMACIÓN NUTRICIONAL
100 ml
250 ml
Valor 104 kJ 260 kJ
Energético 32 kcal 80 kcal
0.1g
0.3 g
Grasas
de las cuales saturadas
0g
0g
Hidratos de
5.5 g
13.8 g
Carbono
Proteínas
0.2 g
0.5 g
"""
        result = rescue_read(observed)
        self.assertIn("PARALLEL_COLUMN_SIGNAL", result.reasons)
        self.assertNotIn("fat_g", result.nutrition)
        self.assertNotIn("carbohydrate_g", result.nutrition)

    def test_bounded_values_are_not_converted_to_exact_macros(self):
        observed = """INFORMACIÓN NUTRICIONAL por 100 g
Valor energético 1568 kJ / 369 kcal
<0.5 g
Grasas
Hidratos de Carbono 92 g
<0.5 g
Proteínas
Sal 0.15 g
"""
        result = rescue_read(observed)
        self.assertNotIn("fat_g", result.nutrition)
        self.assertNotIn("protein_g", result.nutrition)
        self.assertEqual(result.nutrition["carbohydrate_g"], 92.0)

    def test_zero_kcal_is_valid_declared_energy_evidence(self):
        observed = """INFORMACIÓN NUTRICIONAL
por 100 ml
VALOR ENERGÉTICO
0 Kcal / 0 Kj
0g
GRASAS
HIDRATOS DE CARBONO
0g
PROTEÍNAS
0g
SAL 0.075 g
"""
        result = rescue_read(observed)
        self.assertEqual(result.nutrition["calories"], 0.0)
        self.assertEqual(result.nutrition["fat_g"], 0.0)
        self.assertEqual(result.nutrition["carbohydrate_g"], 0.0)
        self.assertEqual(result.nutrition["protein_g"], 0.0)

    def test_tesseract_terminal_g_merge_repairs_only_large_integer_token(self):
        observed = """INFORMACIÓN NUTRICIONAL por 100g de producto.
Valor energético 1226 kJ / 293 kcal; Grasas: 259; Hidratos de carbono: 0.5g; Proteínas: 16.69; Sal: 2.19.
"""
        result = rescue_read(observed)
        self.assertEqual(result.nutrition["fat_g"], 25.0)
        self.assertEqual(result.nutrition["carbohydrate_g"], 0.5)
        # 16.69 is kept as read; it is not silently rewritten to 16.6.
        self.assertEqual(result.nutrition["protein_g"], 16.69)


if __name__ == "__main__":
    unittest.main()
