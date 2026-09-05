from __future__ import annotations

import unittest

from audit_mercadona_p9_no_ingredients_secondary_processed_brand_candidates import candidate_payload


def _row(**updates):
    row = {
        "product_id": "19852",
        "ean": "8480000000000",
        "name": "Bolitas de pollo Hacendado congeladas",
        "brand": "Hacendado",
        "packaging": "Bolsa",
        "unit_size": 0.75,
        "category_id": "44",
        "category_name": "Carne congelada",
        "category_path": [
            {"id": "3", "name": "Carne", "level": "0"},
            {"id": "44", "name": "Carne congelada", "level": "1"},
            {"id": "44", "name": "Carne congelada", "level": "2"},
            {"id": "17", "name": "Congelados", "level": "0"},
            {"id": "229", "name": "Carne", "level": "1"},
        ],
        "legal_name": None,
        "allergens": None,
        "ingredients": None,
        "photos": [{"perspective": 9, "zoom": "https://example.invalid/back.jpg"}],
        "observed_at": "2026-08-27T00:00:00+00:00",
        "share_url": "https://tienda.mercadona.es/product/19852",
    }
    row.update(updates)
    return row


class CandidatePayloadTests(unittest.TestCase):
    def test_accepts_branded_food_with_secondary_processed_category(self):
        payload = candidate_payload(_row())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["primary_top_level_category"], "Carne")
        self.assertEqual(payload["secondary_processed_top_level_categories"], ["Congelados"])
        self.assertEqual(payload["routing_signals"], {"brand": True, "secondary_processed_category": True})
        self.assertEqual(payload["CLASSIFIED"], 0)
        self.assertEqual(payload["MENU_ELIGIBLE"], 0)

    def test_accepts_branded_baby_food_without_packaging(self):
        payload = candidate_payload(
            _row(
                product_id="22444",
                name="Bolsita postre lácteo cereales y miel Hacendado +12 meses",
                packaging=None,
                category_path=[
                    {"id": "24", "name": "Bebé", "level": "0"},
                    {"id": "216", "name": "Alimentación infantil", "level": "1"},
                    {"id": "805", "name": "Yogures y postres", "level": "2"},
                    {"id": "8", "name": "Postres y yogures", "level": "0"},
                ],
            )
        )
        self.assertIsNotNone(payload)
        self.assertEqual(payload["secondary_processed_top_level_categories"], ["Postres y yogures"])

    def test_rejects_unbranded_raw_frozen_meat(self):
        self.assertIsNone(candidate_payload(_row(product_id="4073", brand=None, legal_name="Pierna de cabrito")))

    def test_rejects_already_processed_baby_food_id(self):
        self.assertIsNone(candidate_payload(_row(product_id="60400")))

    def test_rejects_primary_processed_category(self):
        self.assertIsNone(
            candidate_payload(
                _row(category_path=[{"id": "17", "name": "Congelados", "level": "0"}])
            )
        )

    def test_rejects_existing_structured_ingredients(self):
        self.assertIsNone(candidate_payload(_row(ingredients="pollo, sal")))

    def test_rejects_without_perspective_9_zoom(self):
        self.assertIsNone(
            candidate_payload(_row(photos=[{"perspective": 2, "zoom": "https://example.invalid/front.jpg"}]))
        )


if __name__ == "__main__":
    unittest.main()
