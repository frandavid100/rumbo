from __future__ import annotations

import unittest

from audit_mercadona_exact_residual_fresh_food_candidates import (
    EXPECTED_CANDIDATE_IDS,
    audit_rows,
)


def product(product_id: str, category: str, *, p9: bool = True, ingredients=None, legal_name=None, allergens=None):
    return {
        "product_id": product_id,
        "ean": f"84{product_id}",
        "name": f"Product {product_id}",
        "brand": None,
        "packaging": "Bandeja",
        "unit_size": 1.0,
        "ingredients": ingredients,
        "legal_name": legal_name,
        "allergens": allergens,
        "category_path": [{"name": category}],
        "photos": ([{"perspective": "9", "zoom": f"https://example.invalid/{product_id}.jpg"}] if p9 else []),
    }


def residual(product_id: str, category: str):
    return {
        "product_id": product_id,
        "top_level_category": category,
        "profile": "P9_NO_INGREDIENTS_PACKAGED_SIGNAL",
        "p9_url": f"https://example.invalid/{product_id}.jpg",
    }


class ExactResidualFreshFoodTests(unittest.TestCase):
    def fixture(self):
        categories = {
            "17564": "Carne",
            "81416": "Marisco y pescado",
            "81422": "Marisco y pescado",
            "87196": "Marisco y pescado",
            "87254": "Marisco y pescado",
            "68462": "Fruta y verdura",
            "69287": "Fruta y verdura",
            "69495": "Fruta y verdura",
        }
        rows = [product(pid, categories[pid]) for pid in sorted(EXPECTED_CANDIDATE_IDS)]
        rows.extend(product(f"x{i}", "Limpieza y hogar", p9=False) for i in range(4280 - len(rows)))
        residual_rows = [residual(pid, categories[pid]) for pid in sorted(EXPECTED_CANDIDATE_IDS)]
        residual_rows.append(residual("x0", "Limpieza y hogar"))
        return rows, residual_rows

    def test_routes_exact_unprocessed_fresh_food_ids_only(self):
        rows, residual_rows = self.fixture()
        candidates, summary = audit_rows(rows, residual_rows)
        self.assertEqual({row["product_id"] for row in candidates}, EXPECTED_CANDIDATE_IDS)
        self.assertEqual(summary["candidate_universe"], 8)
        self.assertEqual(summary["CLASSIFIED"], 0)
        self.assertEqual(summary["MENU_ELIGIBLE"], 0)

    def test_candidate_with_structured_or_legal_food_data_is_rejected_as_drift(self):
        rows, residual_rows = self.fixture()
        target = next(row for row in rows if row["product_id"] == "17564")
        target["legal_name"] = "pollo"
        with self.assertRaisesRegex(ValueError, "expected exact residual fresh-food ids"):
            audit_rows(rows, residual_rows)

    def test_product_not_present_in_exact_residual_is_not_routed(self):
        rows, residual_rows = self.fixture()
        residual_rows = [row for row in residual_rows if row["product_id"] != "17564"]
        with self.assertRaisesRegex(ValueError, "expected exact residual fresh-food ids"):
            audit_rows(rows, residual_rows)


if __name__ == "__main__":
    unittest.main()
