from __future__ import annotations

import unittest

from audit_mercadona_p9_no_ingredients_food_signal_candidates import candidate_payload


def _row(**updates):
    row = {
        "product_id": "123",
        "ean": "8410000000000",
        "name": "Producto alimentario",
        "brand": "Hacendado",
        "category_id": "1",
        "category_name": "Carne",
        "category_path": [{"id": "3", "name": "Carne", "level": "0"}],
        "legal_name": "Preparado alimenticio",
        "allergens": None,
        "ingredients": None,
        "photos": [{"perspective": 9, "zoom": "https://example.invalid/back.jpg"}],
        "observed_at": "2026-08-27T00:00:00+00:00",
        "share_url": "https://tienda.mercadona.es/product/123",
    }
    row.update(updates)
    return row


class CandidatePayloadTests(unittest.TestCase):
    def test_accepts_food_category_with_p9_and_legal_name(self):
        payload = candidate_payload(_row())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["top_level_category"], "Carne")
        self.assertEqual(payload["routing_signals"], {"legal_name": True, "allergens": False})
        self.assertEqual(payload["CLASSIFIED"], 0)
        self.assertEqual(payload["MENU_ELIGIBLE"], 0)

    def test_accepts_allergen_signal_without_legal_name(self):
        payload = candidate_payload(_row(legal_name=None, allergens="Leche"))
        self.assertIsNotNone(payload)
        self.assertEqual(payload["routing_signals"], {"legal_name": False, "allergens": True})

    def test_rejects_existing_structured_ingredients(self):
        self.assertIsNone(candidate_payload(_row(ingredients="agua, sal")))

    def test_rejects_non_food_top_level_category(self):
        self.assertIsNone(candidate_payload(_row(category_path=[{"name": "Limpieza y hogar"}])))

    def test_rejects_without_food_routing_signal(self):
        self.assertIsNone(candidate_payload(_row(legal_name=None, allergens=None)))

    def test_rejects_without_perspective_9_zoom(self):
        self.assertIsNone(candidate_payload(_row(photos=[{"perspective": 2, "zoom": "https://example.invalid/front.jpg"}])))


if __name__ == "__main__":
    unittest.main()
