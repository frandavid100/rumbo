import json
import unittest
from pathlib import Path
from classifier import ProductFeatures, classify_type

FIXTURE = Path(__file__).parent / "fixtures" / "mercadona_coverage_probe.json"

class CoverageProbeTest(unittest.TestCase):
    def test_observed_current_products_have_expected_type(self):
        rows=json.loads(FIXTURE.read_text())
        self.assertGreaterEqual(len(rows),40)
        failures=[]
        for row in rows:
            result=classify_type(ProductFeatures(row['name']))
            actual=result.value if result else None
            if actual!=row['expected_type']:
                failures.append((row['name'],row['expected_type'],actual))
        self.assertEqual(failures,[])

    def test_precedence_avoids_secondary_word_false_positives(self):
        cases={
            'Pizza Calzone con jamón cocido y queso Hacendado':'PREPARED_DISH',
            'Cereales copos de trigo integral y arroz Hacendado 0% azúcares añadidos':'BREAKFAST_CEREAL',
            'Mini cereales rellenos de leche Hacendado':'BREAKFAST_CEREAL',
            'Zumo de naranja Hacendado':'BEVERAGE',
            'Hummus de garbanzos Hacendado':'SPREAD',
            'Tarta de queso Hacendado':'SNACK_DESSERT',
            'Media tortilla de patata con cebolla Listo para Comer':'PREPARED_DISH',
            'Pan tostado cereales y semillas Hacendado':'BREAD',
        }
        for name,expected in cases.items():
            with self.subTest(name):
                result=classify_type(ProductFeatures(name))
                self.assertIsNotNone(result)
                self.assertEqual(result.value,expected)

if __name__=='__main__': unittest.main()
