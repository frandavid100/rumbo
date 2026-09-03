from __future__ import annotations

import unittest

from audit_mercadona_p9_no_ingredients_processed_candidates import candidate_payload


def _row(**updates):
    row = {
        "product_id": "123",
        "ean": "8410000000000",
        "name": "Producto alimentario envasado",
        "brand": "Hacendado",
        "packaging": "Paquete",
        "unit_size": 0.3,
        "category_id": "1",
        "category_name": "Charcutería y quesos",
        "category_path": [{"id": "3", "name": "Charcutería y quesos", "level": "0"}],
        "legal_name": None,
        "allergens": None,
        "ingredients": None,
        "photos": [{"perspective": 9, "zoom": "https://example.invalid/back.jpg"}],
        "observed_at": "2026-08-27T00:00:00+00:00",
        "share_url": "https://tienda.mercadona.es/product/123",
    }
    row.update(updates)
    return row


class CandidatePayloadTests(unittest.TestCase):
    def test_accepts_processed_category_without_legal_or_allergen_signal(self):
        payload = candidate_payload(_row())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["top_level_category"], "Charcutería y quesos")
        self.assertTrue(payload["routing_signals"]["processed_top_level_category"])
        self.assertFalse(payload["routing_signals"]["legal_name"])
        self.assertFalse(payload["routing_signals"]["allergens"])
        self.assertEqual(payload["CLASSIFIED"], 0)
        self.assertEqual(payload["MENU_ELIGIBLE"], 0)

    def test_placeholder_allergen_is_not_positive_routing_signal(self):
        payload = candidate_payload(_row(allergens="x99."))
        self.assertIsNotNone(payload)
        self.assertFalse(payload["routing_signals"]["allergens"])

    def test_meaningful_allergen_is_retained_for_audit(self):
        payload = candidate_payload(_row(allergens="Contiene leche"))
        self.assertIsNotNone(payload)
        self.assertTrue(payload["routing_signals"]["allergens"])

    def test_rejects_existing_structured_ingredients(self):
        self.assertIsNone(candidate_payload(_row(ingredients="agua, sal")))

    def test_rejects_fresh_meat_category(self):
        self.assertIsNone(candidate_payload(_row(category_path=[{"name": "Carne"}])))

    def test_rejects_bodega_category(self):
        self.assertIsNone(candidate_payload(_row(category_path=[{"name": "Bodega"}])))

    def test_rejects_birthday_candles_misrouted_under_bakery(self):
        self.assertIsNone(candidate_payload(_row(
            name="Vela de cumpleaños 2 Hacendado",
            category_path=[{"name": "Panadería y pastelería"}],
        )))

    def test_rejects_ice_as_no_nutrition_label_route(self):
        self.assertIsNone(candidate_payload(_row(
            name="Cubos de hielo Hacendado",
            category_path=[{"name": "Congelados"}],
        )))

    def test_rejects_without_perspective_9_zoom(self):
        self.assertIsNone(candidate_payload(_row(photos=[{"perspective": 2, "zoom": "https://example.invalid/front.jpg"}])))


if __name__ == "__main__":
    unittest.main()
