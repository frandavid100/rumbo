from __future__ import annotations

import unittest

from audit_mercadona_p9_no_ingredients_deferred_packaged_candidates import candidate_payload


def _row(**updates):
    row = {
        "product_id": "52776",
        "ean": "8480000000000",
        "name": "Preparado de carne picada vacuno Hacendado",
        "brand": "Hacendado",
        "packaging": "Paquete",
        "unit_size": 0.4,
        "category_id": "783",
        "category_name": "Picadas y otros",
        "category_path": [
            {"id": "3", "name": "Carne", "level": "0"},
            {"id": "44", "name": "Hamburguesas y picadas", "level": "1"},
            {"id": "783", "name": "Picadas y otros", "level": "2"},
        ],
        "legal_name": None,
        "allergens": "Contiene soja y productos a base de soja. Contiene cereales que contengan gluten.",
        "ingredients": None,
        "photos": [{"perspective": 9, "zoom": "https://example.invalid/back.jpg"}],
        "observed_at": "2026-08-27T00:00:00+00:00",
        "share_url": "https://tienda.mercadona.es/product/52776",
    }
    row.update(updates)
    return row


class CandidatePayloadTests(unittest.TestCase):
    def test_accepts_deferred_fresh_department_with_strong_packaged_signals(self):
        payload = candidate_payload(_row())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["top_level_category"], "Carne")
        self.assertEqual(
            payload["routing_signals"],
            {"brand": True, "packaging": True, "substantive_allergens": True},
        )
        self.assertEqual(payload["CLASSIFIED"], 0)
        self.assertEqual(payload["MENU_ELIGIBLE"], 0)

    def test_rejects_live_seafood_allergen_signal_without_brand(self):
        self.assertIsNone(
            candidate_payload(
                _row(
                    product_id="85145",
                    name="Mejillón vivo selección",
                    brand=None,
                    category_path=[{"id": "4", "name": "Marisco y pescado", "level": "0"}],
                    allergens="Contiene moluscos y productos a base de moluscos.",
                )
            )
        )

    def test_rejects_placeholder_allergen(self):
        self.assertIsNone(candidate_payload(_row(allergens="x99.")))

    def test_rejects_without_packaging(self):
        self.assertIsNone(candidate_payload(_row(packaging=None)))

    def test_rejects_processed_category_already_covered_by_previous_route(self):
        self.assertIsNone(
            candidate_payload(
                _row(category_path=[{"id": "8", "name": "Charcutería y quesos", "level": "0"}])
            )
        )

    def test_rejects_existing_structured_ingredients(self):
        self.assertIsNone(candidate_payload(_row(ingredients="carne de vacuno, sal")))

    def test_rejects_without_perspective_9_zoom(self):
        self.assertIsNone(
            candidate_payload(
                _row(photos=[{"perspective": 1, "zoom": "https://example.invalid/front.jpg"}])
            )
        )


if __name__ == "__main__":
    unittest.main()
