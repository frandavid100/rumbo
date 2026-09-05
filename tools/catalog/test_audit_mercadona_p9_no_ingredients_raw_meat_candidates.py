import unittest

import audit_mercadona_p9_no_ingredients_raw_meat_candidates as audit


class RawMeatRoutingAuditTest(unittest.TestCase):
    def row(self, product_id: str, *, ingredients=None, legal_name="CARNE", allergens=None, perspective="9"):
        return {
            "product_id": product_id,
            "ean": f"84{int(product_id):011d}"[-13:],
            "name": f"Producto {product_id}",
            "brand": None,
            "packaging": "Bandeja",
            "ingredients": ingredients,
            "legal_name": legal_name,
            "allergens": allergens,
            "category_path": [{"name": "Carne", "level": 0}],
            "photos": [{"perspective": perspective, "zoom": f"https://example.invalid/{product_id}.jpg"}],
        }

    def test_food_signal_requires_p9_no_ingredients_and_first_party_food_signal(self):
        self.assertTrue(audit.is_food_signal_candidate(self.row("1")))
        self.assertFalse(audit.is_food_signal_candidate(self.row("2", ingredients="pollo")))
        self.assertFalse(audit.is_food_signal_candidate(self.row("3", perspective="1")))
        self.assertFalse(audit.is_food_signal_candidate(self.row("4", legal_name=None, allergens=None)))

    def test_prior_food_signal_selection_reproduces_first_eight_per_four_way_shard(self):
        rows = [self.row(str(i)) for i in range(1, 41)]
        selected = audit.prior_food_signal_processed_ids(rows)
        self.assertEqual(32, len(selected))
        ordered = sorted(rows, key=audit.stable_key)
        expected = set()
        for shard in range(4):
            shard_rows = [row for i, row in enumerate(ordered) if i % 4 == shard]
            expected.update(str(row["product_id"]) for row in shard_rows[:8])
        self.assertEqual(expected, selected)

    def test_candidate_payload_keeps_routing_non_semantic_and_non_redistributable(self):
        payload = audit.candidate_payload(self.row("10"))
        self.assertEqual("MERCADONA_FIRST_PARTY", payload["source"])
        self.assertFalse(payload["redistribution_allowed"])
        self.assertEqual(0, payload["CLASSIFIED"])
        self.assertEqual(0, payload["MENU_ELIGIBLE"])
        self.assertIsNone(payload["ingredients"])


if __name__ == "__main__":
    unittest.main()
