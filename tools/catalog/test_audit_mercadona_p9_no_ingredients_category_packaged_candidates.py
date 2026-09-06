from __future__ import annotations

import unittest

from audit_mercadona_p9_no_ingredients_category_packaged_candidates import (
    candidate_payload,
    has_food_signal,
    is_category_packaged_candidate,
    stable_key,
    top_level_category,
)


def row(
    pid: str,
    *,
    category: str = "Cereales y galletas",
    ingredients=None,
    legal_name: str | None = None,
    allergens=None,
    packaging: str | None = "Paquete",
    unit_size=0.4,
    perspective: int = 9,
):
    return {
        "product_id": pid,
        "ean": f"84{int(pid):011d}"[-13:],
        "name": f"Producto {pid}",
        "ingredients": ingredients,
        "legal_name": legal_name,
        "allergens": allergens,
        "packaging": packaging,
        "unit_size": unit_size,
        "category_path": [{"name": category}],
        "photos": [{"perspective": perspective, "zoom": f"https://example.invalid/{pid}.jpg"}],
    }


class CategoryPackagedRoutingTest(unittest.TestCase):
    def test_requires_p9_no_ingredients_no_strong_signal_and_packaging_metadata(self):
        good = row("1")
        self.assertTrue(is_category_packaged_candidate(good))
        self.assertFalse(has_food_signal(good))

        self.assertFalse(is_category_packaged_candidate(row("2", ingredients="trigo")))
        self.assertFalse(is_category_packaged_candidate(row("3", legal_name="Galletas")))
        self.assertFalse(is_category_packaged_candidate(row("4", allergens={"gluten": True})))
        self.assertFalse(is_category_packaged_candidate(row("5", packaging=None)))
        self.assertFalse(is_category_packaged_candidate(row("6", unit_size=None)))
        self.assertFalse(is_category_packaged_candidate(row("7", perspective=8)))

    def test_excludes_bodega_fresh_raw_and_non_food_departments(self):
        for category in ("Bodega", "Carne", "Fruta y verdura", "Marisco y pescado", "Limpieza y hogar"):
            with self.subTest(category=category):
                self.assertFalse(is_category_packaged_candidate(row("8", category=category)))

    def test_stable_key_is_deterministic(self):
        rows = [row(str(i)) for i in range(1, 12)]
        first = [item["product_id"] for item in sorted(rows, key=stable_key)]
        second = [item["product_id"] for item in sorted(reversed(rows), key=stable_key)]
        self.assertEqual(first, second)

    def test_payload_preserves_provenance_and_does_not_classify(self):
        source = row("9")
        payload = candidate_payload(source)
        self.assertEqual("Cereales y galletas", top_level_category(source))
        self.assertEqual("MERCADONA_FIRST_PARTY", payload["source"])
        self.assertFalse(payload["redistribution_allowed"])
        self.assertIsNone(payload["ingredients"])
        self.assertIsNone(payload["legal_name"])
        self.assertIsNone(payload["allergens"])
        self.assertEqual(0, payload["CLASSIFIED"])
        self.assertEqual(0, payload["MENU_ELIGIBLE"])


if __name__ == "__main__":
    unittest.main()
