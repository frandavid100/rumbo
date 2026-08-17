import json
import unittest

from fooddata_central_adapter import (
    GenericMapping, parse_food, search_foods, to_generic_candidate, UPSTREAM_LICENSE,
)
from nutrition_resolver import ProductIdentity


class FoodDataCentralAdapterTest(unittest.TestCase):
    def fixture(self):
        return {
            "fdcId": 123,
            "description": "Pears, raw",
            "dataType": "Foundation",
            "foodNutrients": [
                {"nutrient": {"number": "208", "name": "Energy"}, "amount": 57},
                {"nutrient": {"number": "204", "name": "Total lipid (fat)"}, "amount": 0.14},
                {"nutrient": {"number": "205", "name": "Carbohydrate, by difference"}, "amount": 15.23},
                {"nutrient": {"number": "203", "name": "Protein"}, "amount": 0.36},
                {"nutrient": {"number": "291", "name": "Fiber, total dietary"}, "amount": 3.1},
            ],
        }

    def test_parse_and_build_explicit_generic_candidate(self):
        food = parse_food(self.fixture())
        self.assertEqual(food.nutrition["calories"], 57.0)
        mapping = GenericMapping("Pera", 123, "Pears, raw", "fresh unbranded whole pear")
        candidate = to_generic_candidate(ProductIdentity("Pera Conferencia"), mapping, food)
        self.assertEqual(candidate.evidence_level, "GENERIC")
        self.assertEqual(candidate.upstream_license, UPSTREAM_LICENSE)
        self.assertTrue(candidate.redistribution_allowed)
        self.assertEqual(candidate.source_record_id, "123")

    def test_foundation_energy_uses_kcal_and_ignores_kj(self):
        payload = {
            "fdcId": 456,
            "description": "Example raw food",
            "dataType": "Foundation",
            "foodNutrients": [
                {"nutrient": {"id": 1008, "name": "Energy", "unitName": "kJ"}, "amount": 239},
                {"nutrient": {"id": 2047, "name": "Metabolizable Energy (Atwater General Factor)", "unitName": "kcal"}, "amount": 57},
                {"nutrient": {"id": 1004, "name": "Total lipid (fat)", "unitName": "g"}, "amount": 0.14},
                {"nutrient": {"id": 1005, "name": "Carbohydrate, by difference", "unitName": "g"}, "amount": 15.23},
                {"nutrient": {"id": 1003, "name": "Protein", "unitName": "g"}, "amount": 0.36},
                {"nutrient": {"id": 1079, "name": "Fiber, total dietary", "unitName": "g"}, "amount": 3.1},
            ],
        }
        food = parse_food(payload)
        self.assertEqual(food.nutrition["calories"], 57.0)
        self.assertEqual(food.nutrition["protein_g"], 0.36)
        self.assertEqual(food.nutrition["fat_g"], 0.14)
        self.assertEqual(food.nutrition["carbohydrate_g"], 15.23)
        self.assertEqual(food.nutrition["fiber_g"], 3.1)

    def test_mapping_must_match_exact_fdc_record(self):
        food = parse_food(self.fixture())
        bad = GenericMapping("Pera", 124, "Pears, raw", "wrong id")
        with self.assertRaises(ValueError):
            to_generic_candidate(ProductIdentity("Pera"), bad, food)

    def test_search_is_proposal_only_and_filters_generic_data_types(self):
        seen = {}
        def transport(url, headers, body, timeout):
            seen.update(url=url, headers=headers, body=json.loads(body.decode()), timeout=timeout)
            return json.dumps({"foods": [{"fdcId": 123, "description": "Pears, raw"}]}).encode()
        foods = search_foods("pear raw", api_key="demo", transport=transport)
        self.assertEqual(foods[0]["fdcId"], 123)
        self.assertEqual(seen["body"]["dataType"], ["Foundation", "SR Legacy"])


if __name__ == "__main__":
    unittest.main()
