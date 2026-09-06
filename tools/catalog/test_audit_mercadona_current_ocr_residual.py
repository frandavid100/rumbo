from __future__ import annotations

import unittest

from audit_mercadona_current_ocr_residual import audit, p9_photo, residual_profile


def row(product_id: str, *, p9: bool, ingredients=None, legal_name=None, allergens=None, packaging=None, unit_size=None):
    return {
        "product_id": product_id,
        "name": f"Product {product_id}",
        "ingredients": ingredients,
        "legal_name": legal_name,
        "allergens": allergens,
        "packaging": packaging,
        "unit_size": unit_size,
        "category_path": [{"name": "Test"}],
        "photos": ([{"perspective": "9", "zoom": f"https://example.invalid/{product_id}.jpg"}] if p9 else []),
    }


class ResidualProfileTests(unittest.TestCase):
    def test_profiles_are_conservative_first_party_routing_only(self):
        self.assertEqual(residual_profile(row("1", p9=False)), "NO_P9")
        self.assertEqual(residual_profile(row("2", p9=True, ingredients=[{"text": "x"}])), "P9_STRUCTURED_INGREDIENTS")
        self.assertEqual(residual_profile(row("3", p9=True, legal_name="food")), "P9_NO_INGREDIENTS_FOOD_SIGNAL")
        self.assertEqual(residual_profile(row("4", p9=True, allergens=["milk"])), "P9_NO_INGREDIENTS_FOOD_SIGNAL")
        self.assertEqual(residual_profile(row("5", p9=True, packaging="bag", unit_size=100)), "P9_NO_INGREDIENTS_PACKAGED_SIGNAL")
        self.assertEqual(residual_profile(row("6", p9=True)), "P9_NO_INGREDIENTS_OTHER")

    def test_p9_requires_zoom_url(self):
        value = row("1", p9=True)
        value["photos"][0]["zoom"] = None
        self.assertIsNone(p9_photo(value))

    def test_audit_rejects_wrong_processed_union_before_routing(self):
        products = [row(str(i), p9=False) for i in range(4280)]
        with self.assertRaisesRegex(ValueError, "expected 3 distinct processed"):
            audit(products, {"0", "1"}, expected_processed=3)

    def test_audit_routes_only_unprocessed_p9(self):
        products = [row(str(i), p9=False) for i in range(4280)]
        products[7] = row("7", p9=True, ingredients=[{"text": "x"}])
        products[8] = row("8", p9=True, packaging="bag", unit_size=100)
        residual_rows, summary = audit(products, {"7"}, expected_processed=1)
        self.assertEqual([item["product_id"] for item in residual_rows], ["8"])
        self.assertEqual(summary["p9_residual_total"], 1)
        self.assertEqual(summary["residual_profiles"]["P9_NO_INGREDIENTS_PACKAGED_SIGNAL"], 1)
        self.assertEqual(summary["CLASSIFIED"], 0)
        self.assertEqual(summary["MENU_ELIGIBLE"], 0)


if __name__ == "__main__":
    unittest.main()
