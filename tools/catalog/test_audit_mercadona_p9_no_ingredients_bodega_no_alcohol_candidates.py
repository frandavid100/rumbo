from __future__ import annotations

import unittest

from audit_mercadona_p9_no_ingredients_bodega_no_alcohol_candidates import candidate_payload


def row(*, top="Bodega", level1="Cerveza sin alcohol", ingredients=None, perspective=9, zoom="https://example.test/x.jpg"):
    return {
        "product_id": "1",
        "name": "x",
        "ingredients": ingredients,
        "category_path": [
            {"id": "1", "level": "0", "name": top},
            {"id": "2", "level": "1", "name": level1},
        ],
        "photos": [{"perspective": perspective, "zoom": zoom}],
    }


class CandidatePayloadTests(unittest.TestCase):
    def test_accepts_exact_no_alcohol_bodega_branch(self):
        payload = candidate_payload(row())
        self.assertIsNotNone(payload)
        self.assertTrue(payload["routing_signals"]["mercadona_bodega_no_alcohol_branch"])
        self.assertEqual(payload["CLASSIFIED"], 0)
        self.assertEqual(payload["MENU_ELIGIBLE"], 0)

    def test_rejects_regular_beer(self):
        self.assertIsNone(candidate_payload(row(level1="Cerveza")))

    def test_rejects_liquor(self):
        self.assertIsNone(candidate_payload(row(level1="Licores")))

    def test_rejects_same_named_branch_outside_bodega(self):
        self.assertIsNone(candidate_payload(row(top="Agua y refrescos")))

    def test_rejects_structured_ingredients(self):
        self.assertIsNone(candidate_payload(row(ingredients=["malta"])))

    def test_rejects_without_p9_zoom(self):
        self.assertIsNone(candidate_payload(row(perspective=1)))
        self.assertIsNone(candidate_payload(row(zoom=None)))


if __name__ == "__main__":
    unittest.main()
