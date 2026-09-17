import unittest

from mercadona_explicit_serving_column_rescue import project_explicit_serving_column


CANDIDATE_64499 = """100 g
50 g
Valor
1679 kJ
840 kJ
(azúcar.
Energético/Energia
403 kcal
202 kcal
n polvo.
13.5 g
Grasas/Lípidos
27.1 g
itina de
de las cuales/dos quais:
(23.5%)
13.5 g
6.8 g
- Saturadas/Saturados
- Monoinsaturadas/Monoinsaturados
7.9 g
3.9 g
5.2 g
2.6 g
-Poliinsaturadas/Polinsaturados
Hidratos de Carbono
35.3 g
17.7 g
de los cuales/dos quais:
- Azúcares/Açúcares
34.5 g
17.2 g
Fibra alimentaria/Fibra
1.0 g
0.5 g
Proteínas
4.1 g
2.0 g
Sal
0.11 g
0.05 g
Contiene 8 unidades de aprox. 50 g.
"""


class MercadonaExplicitServingColumnRescueTest(unittest.TestCase):
    def test_projects_observed_64499_100g_column_without_inference(self):
        projection = project_explicit_serving_column(CANDIDATE_64499, extraction_confidence=.96)
        self.assertIsNotNone(projection)
        self.assertEqual(projection.serving_amount, 50.0)
        self.assertEqual(projection.serving_unit, "g")
        self.assertEqual(projection.result.status, "DECLARED")
        self.assertEqual(projection.result.basis, "100_g")
        self.assertEqual(projection.result.nutrition, {
            "calories": 403.0,
            "fat_g": 27.1,
            "carbohydrate_g": 35.3,
            "protein_g": 4.1,
        })
        self.assertEqual(projection.observed_pairs["calories"], (403.0, 202.0))
        self.assertEqual(projection.observed_pairs["fat_g"], (27.1, 13.5))
        self.assertEqual(projection.observed_pairs["carbohydrate_g"], (35.3, 17.7))
        self.assertEqual(projection.observed_pairs["protein_g"], (4.1, 2.0))
        self.assertIn("EXPLICIT_SERVING_COLUMN_PROJECTION serving=50g", projection.result.normalized_text)

    def test_rejects_two_parallel_per_100_headers(self):
        text = CANDIDATE_64499.replace("100 g\n50 g", "100 g\n100 g", 1)
        self.assertIsNone(project_explicit_serving_column(text))

    def test_rejects_third_column_header(self):
        text = CANDIDATE_64499.replace("100 g\n50 g", "100 g\n50 g\n25 g", 1)
        self.assertIsNone(project_explicit_serving_column(text))

    def test_rejects_inconsistent_serving_ratio(self):
        text = CANDIDATE_64499.replace("35.3 g\n17.7 g", "35.3 g\n12.0 g", 1)
        self.assertIsNone(project_explicit_serving_column(text))

    def test_rejects_missing_second_core_cell(self):
        text = CANDIDATE_64499.replace("4.1 g\n2.0 g\nSal", "4.1 g\nSal", 1)
        self.assertIsNone(project_explicit_serving_column(text))

    def test_rejects_missing_explicit_serving_headers(self):
        text = CANDIDATE_64499.replace("100 g\n50 g\n", "", 1)
        self.assertIsNone(project_explicit_serving_column(text))

    def test_supports_explicit_100ml_and_serving_ml_pair(self):
        text = """100 ml
25 ml
Valor energético
40 kcal
10 kcal
Grasas
0 g
0 g
Hidratos de Carbono
10 g
2.5 g
Proteínas
0 g
0 g
Sal
0 g
0 g
"""
        projection = project_explicit_serving_column(text, extraction_confidence=.95)
        self.assertIsNotNone(projection)
        self.assertEqual(projection.result.status, "DECLARED")
        self.assertEqual(projection.result.basis, "100_ml")
        self.assertEqual(projection.result.nutrition, {
            "calories": 40.0,
            "fat_g": 0.0,
            "carbohydrate_g": 10.0,
            "protein_g": 0.0,
        })


if __name__ == "__main__":
    unittest.main()
