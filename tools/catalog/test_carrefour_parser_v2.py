import unittest

from carrefour_radar_catalog_importer_v2 import parse_nutrition


class CarrefourParserV2Tests(unittest.TestCase):
    def test_package_weight_is_not_nutrition(self):
        text = (
            "Pasta seca 500 g precio 1,20 €. "
            "Información nutricional Información nutricional por 100 g "
            "Valor energético — / 350 kcal Grasas 2 g de las cuales saturadas 0,4 g "
            "Hidratos de carbono 70 g de los cuales azúcares 2 g Fibra 4 g "
            "Proteínas 12 g Sal 1,2 g "
            "Datos nutricionales: Open Food Facts. "
            "Formato 500 g"
        )
        self.assertEqual(parse_nutrition(text), (350.0, 12.0, 70.0, 2.0, 4.0, 1.2))

    def test_missing_values_remain_unknown(self):
        text = (
            "Atún claro 82 g. Información nutricional por 100 g "
            "Valor energético — / 377 kcal Grasas 33 g de las cuales saturadas 4,8 g "
            "Hidratos de carbono 0 g de los cuales azúcares — Fibra — Proteínas — Sal — "
            "Datos nutricionales: Open Food Facts. Cada 100 g puede aportar proteína según descripción."
        )
        self.assertEqual(parse_nutrition(text), (377.0, None, 0.0, 33.0, None, None))

    def test_text_after_attribution_cannot_contaminate_table(self):
        text = (
            "Producto 900 g. Información nutricional por 100 g "
            "Valor energético — / 100 kcal Grasas 2 g Hidratos de carbono 5 g Proteínas — Sal 1 g "
            "Datos nutricionales: Open Food Facts. Sobre este producto: aporta 25 g de proteínas. Formato 900 g"
        )
        self.assertEqual(parse_nutrition(text), (100.0, None, 5.0, 2.0, None, 1.0))


if __name__ == "__main__":
    unittest.main()
