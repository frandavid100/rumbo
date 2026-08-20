from __future__ import annotations

import unittest

from tools.build_bedca_catalog import normalize
from tools.catalog.classify import classify


def detail(*components: dict) -> dict:
    return {"components": list(components)}


def component(code: str, value: str | None, unit: str = "g") -> dict:
    return {"eur_name": code, "best_location": value, "v_unit": unit}


class BedcaNormalizerTest(unittest.TestCase):
    def test_converts_kilojoules_and_sodium(self):
        result = normalize(detail(component("ENERC", "418.4", "kJ"), component("PROT", "10"),
                                  component("CHO", "20"), component("FAT", "5"),
                                  component("NA", "400", "mg")))
        self.assertAlmostEqual(100.0, result["calories"])
        self.assertAlmostEqual(0.4, result["sodium_g"])
        self.assertAlmostEqual(1.0, result["salt_g"])

    def test_missing_is_not_zero(self):
        result = normalize(detail(component("ENERC", "418.4", "kJ")))
        self.assertIsNone(result["protein_g"])
        self.assertIsNone(result["carbohydrate_g"])

    def test_derives_energy_only_when_all_macros_exist(self):
        result = normalize(detail(component("PROT", "10"), component("CHO", "20"),
                                  component("FAT", "5"), component("FIBT", "4")))
        self.assertEqual(173.0, result["calories"])
        self.assertTrue(result["calories_derived"])


class BedcaClassifierTest(unittest.TestCase):
    def test_dry_rice_is_primary_carbohydrate_plate_base(self):
        result = classify("Arroz blanco, crudo", "6", {"calories": 350.0, "protein_g": 7.0,
                          "carbohydrate_g": 78.0, "fat_g": 1.0})
        self.assertIn("PRIMARY_CARBOHYDRATE", result.nutritional_roles)
        self.assertEqual(("PLATE_BASE",), result.culinary_roles)
        self.assertEqual(80.0, result.portion_basis_grams)
        self.assertEqual("arroz", result.food_family)

    def test_oil_uses_functional_portion(self):
        result = classify("Aceite de oliva virgen", "5", {"calories": 900.0, "protein_g": 0.0,
                          "carbohydrate_g": 0.0, "fat_g": 100.0})
        self.assertEqual(("CONCENTRATED_FAT",), result.nutritional_roles)
        self.assertEqual(10.0, result.portion_basis_grams)
        self.assertIn("COOKING_MEDIUM", result.culinary_roles)

    def test_rice_pudding_is_not_a_beverage(self):
        result = classify("Arroz con leche", "1", {"calories": 100.0, "protein_g": 3.0,
                          "carbohydrate_g": 17.0, "fat_g": 2.0})
        self.assertNotIn("BEVERAGE", result.culinary_roles)
        self.assertEqual(("DESSERT", "STANDALONE"), result.culinary_roles)

    def test_olive_does_not_satisfy_fruit_requirement(self):
        result = classify("Aceituna negra, con hueso", "9", {"calories": 200.0, "protein_g": 2.0,
                          "carbohydrate_g": 4.0, "fat_g": 20.0})
        self.assertNotIn("FRUIT", result.nutritional_roles)
        self.assertEqual(30.0, result.portion_basis_grams)

    def test_processed_meat_uses_smaller_physical_basis(self):
        result = classify("Bacon, crudo", "3", {"calories": 450.0, "protein_g": 12.5,
                          "carbohydrate_g": 0.0, "fat_g": 46.0})
        self.assertEqual(50.0, result.portion_basis_grams)
        self.assertNotIn("PRIMARY_PROTEIN", result.nutritional_roles)

    def test_vegetable_juice_does_not_count_as_fruit(self):
        result = classify("Zanahoria, zumo fresco", "9", {"calories": 25.0, "protein_g": 0.6,
                          "carbohydrate_g": 4.7, "fat_g": 0.1})
        self.assertNotIn("FRUIT", result.nutritional_roles)
        self.assertEqual(("BEVERAGE", "STANDALONE"), result.culinary_roles)

    def test_compound_does_not_receive_simple_family(self):
        result = classify("Pastel de manzana", "6", {"calories": 380.0, "protein_g": 3.5,
                          "carbohydrate_g": 57.0, "fat_g": 15.0})
        self.assertIsNone(result.food_family)


if __name__ == "__main__":
    unittest.main()
