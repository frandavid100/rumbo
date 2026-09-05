from __future__ import annotations

import unittest

from audit_mercadona_p9_no_ingredients_baby_food_candidates import candidate_payload


def _row(**updates):
    row = {
        "product_id": "60400",
        "ean": "8480000000000",
        "name": "Bolsita postre lácteo galleta Hacendado +8 meses",
        "brand": "Hacendado",
        "packaging": None,
        "unit_size": 0.1,
        "category_id": "805",
        "category_name": "Yogures y postres",
        "category_path": [
            {"id": "24", "name": "Bebé", "level": "0"},
            {"id": "216", "name": "Alimentación infantil", "level": "1"},
            {"id": "805", "name": "Yogures y postres", "level": "2"},
        ],
        "legal_name": "Producto lácteo pasteurizado después de la fermentación con galleta",
        "allergens": "Puede contener huevos y productos a base de huevo. Contiene leche.",
        "ingredients": None,
        "photos": [{"perspective": 9, "zoom": "https://example.invalid/back.jpg"}],
        "observed_at": "2026-08-27T00:00:00+00:00",
        "share_url": "https://tienda.mercadona.es/product/60400",
    }
    row.update(updates)
    return row


class CandidatePayloadTests(unittest.TestCase):
    def test_accepts_baby_food_with_first_party_food_signals(self):
        payload = candidate_payload(_row())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["top_level_category"], "Bebé")
        self.assertEqual(
            payload["routing_signals"],
            {
                "baby_food_branch": True,
                "brand": True,
                "legal_name": True,
                "substantive_allergens": True,
            },
        )
        self.assertEqual(payload["CLASSIFIED"], 0)
        self.assertEqual(payload["MENU_ELIGIBLE"], 0)

    def test_rejects_non_food_baby_branch(self):
        self.assertIsNone(
            candidate_payload(
                _row(
                    category_path=[
                        {"id": "24", "name": "Bebé", "level": "0"},
                        {"id": "999", "name": "Higiene y cuidado", "level": "1"},
                    ]
                )
            )
        )

    def test_rejects_without_legal_food_denomination(self):
        self.assertIsNone(candidate_payload(_row(legal_name=None, legal_denomination=None)))

    def test_rejects_placeholder_allergen(self):
        self.assertIsNone(candidate_payload(_row(allergens="x99.")))

    def test_rejects_without_brand(self):
        self.assertIsNone(candidate_payload(_row(brand=None)))

    def test_rejects_existing_structured_ingredients(self):
        self.assertIsNone(candidate_payload(_row(ingredients="leche, galleta")))

    def test_rejects_without_perspective_9_zoom(self):
        self.assertIsNone(
            candidate_payload(
                _row(photos=[{"perspective": 2, "zoom": "https://example.invalid/front.jpg"}])
            )
        )


if __name__ == "__main__":
    unittest.main()
