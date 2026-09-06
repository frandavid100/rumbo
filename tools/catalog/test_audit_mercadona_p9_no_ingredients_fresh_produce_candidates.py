from __future__ import annotations

import unittest

from audit_mercadona_p9_no_ingredients_fresh_produce_candidates import (
    candidate_payload,
    is_food_signal_candidate,
    prior_food_signal_processed_ids,
    stable_key,
    top_level_category,
)


def row(pid: str, *, category: str = "Fruta y verdura", ingredients=None, legal_name: str | None = "Fruta fresca"):
    return {
        "product_id": pid,
        "ean": f"84{int(pid):011d}"[-13:],
        "name": f"Producto {pid}",
        "ingredients": ingredients,
        "legal_name": legal_name,
        "allergens": None,
        "category_path": [{"name": category}],
        "photos": [{"perspective": 9, "zoom": f"https://example.invalid/{pid}.jpg"}],
    }


class FreshProduceRoutingTest(unittest.TestCase):
    def test_requires_p9_no_ingredients_food_signal(self):
        good = row("1")
        self.assertTrue(is_food_signal_candidate(good))
        with_ingredients = row("2", ingredients="manzana")
        self.assertFalse(is_food_signal_candidate(with_ingredients))
        no_signal = row("3", legal_name=None)
        self.assertFalse(is_food_signal_candidate(no_signal))
        non_food = row("4", category="Limpieza y hogar")
        self.assertFalse(is_food_signal_candidate(non_food))

    def test_prior_tranche_is_exactly_eight_per_four_shards_when_available(self):
        rows = [row(str(i)) for i in range(1, 41)]
        prior = prior_food_signal_processed_ids(rows)
        self.assertEqual(32, len(prior))
        ordered = sorted(rows, key=stable_key)
        expected = set()
        for shard in range(4):
            shard_rows = [item for index, item in enumerate(ordered) if index % 4 == shard]
            expected.update(str(item["product_id"]) for item in shard_rows[:8])
        self.assertEqual(expected, prior)

    def test_payload_is_provenance_only_and_not_classified(self):
        source = row("5")
        payload = candidate_payload(source)
        self.assertEqual("Fruta y verdura", top_level_category(source))
        self.assertEqual("MERCADONA_FIRST_PARTY", payload["source"])
        self.assertFalse(payload["redistribution_allowed"])
        self.assertIsNone(payload["ingredients"])
        self.assertEqual(0, payload["CLASSIFIED"])
        self.assertEqual(0, payload["MENU_ELIGIBLE"])


if __name__ == "__main__":
    unittest.main()
