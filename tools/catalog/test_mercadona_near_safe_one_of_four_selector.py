import json
from pathlib import Path
import tempfile
import unittest

from mercadona_near_safe_one_of_four_selector import build_one_of_four_candidates


class MercadonaNearSafeOneOfFourSelectorTest(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def test_selects_only_clean_one_of_four_with_exact_identity_and_unique_current_p9_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diagnostic = root / "diagnostic.jsonl"
            products = root / "products.jsonl"
            image_100 = "https://example.invalid/100.jpg"
            image_200 = "https://example.invalid/200.jpg"
            image_300 = "https://example.invalid/300.jpg"
            self._write_jsonl(
                diagnostic,
                [
                    {
                        "product_id": "100",
                        "ean": "84100",
                        "canonical_status": "REVIEW",
                        "corroborated_fields": 1,
                        "independent_engine_families": 3,
                        "basis": "100_g",
                        "diagnostic_candidate_values": {"calories": 100, "fat_g": 2, "carbohydrate_g": 3, "protein_g": 4},
                        "safety_blockers": [],
                        "image_url": image_100,
                        "confidence": 0.9,
                        "latest_raw_run_id": 1,
                    },
                    {
                        "product_id": "200",
                        "ean": "84200",
                        "canonical_status": "REVIEW",
                        "corroborated_fields": 2,
                        "independent_engine_families": 3,
                        "basis": "100_g",
                        "diagnostic_candidate_values": {"calories": 100, "fat_g": 2, "carbohydrate_g": 3, "protein_g": 4},
                        "safety_blockers": [],
                        "image_url": image_200,
                    },
                    {
                        "product_id": "300",
                        "ean": "84300",
                        "canonical_status": "REVIEW",
                        "corroborated_fields": 1,
                        "independent_engine_families": 2,
                        "basis": "100_g",
                        "diagnostic_candidate_values": {"calories": 100, "fat_g": 2, "carbohydrate_g": 3, "protein_g": 4},
                        "safety_blockers": ["MULTIPLE_NUTRITION_COLUMNS"],
                        "image_url": image_300,
                    },
                ],
            )
            self._write_jsonl(
                products,
                [
                    {
                        "product_id": "100",
                        "ean": "84100",
                        "ingredients": "x",
                        "photos": [{"zoom": image_100, "perspective": 9}],
                    },
                    {
                        "product_id": "200",
                        "ean": "84200",
                        "ingredients": "x",
                        "photos": [{"zoom": image_200, "perspective": 9}],
                    },
                    {
                        "product_id": "300",
                        "ean": "84300",
                        "ingredients": "x",
                        "photos": [{"zoom": image_300, "perspective": 9}],
                    },
                ],
            )

            selected, summary = build_one_of_four_candidates(diagnostic, products)
            self.assertEqual([row["product_id"] for row in selected], ["100"])
            self.assertEqual(selected[0]["photos"][0]["perspective"], 9)
            meta = selected[0]["_near_safe_image_meta"]
            self.assertEqual(meta["perspective"], 9)
            self.assertEqual(meta["canonical_corroborated_fields"], 1)
            self.assertEqual(meta["canonical_ean"], "84100")
            self.assertEqual(meta["current_ean"], "84100")
            self.assertEqual(meta["identity_basis"], "EXACT_CURRENT_EAN_MATCH")
            self.assertEqual(summary["canonical_one_of_four_targets"], 1)
            self.assertEqual(summary["current_exact_identity_and_first_party_p9_targets"], 1)
            self.assertFalse(summary["acceptance_policy_changed"])
            self.assertFalse(summary["cross_run_value_fusion"])

    def test_reassigned_product_id_is_excluded_even_when_image_url_still_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diagnostic = root / "diagnostic.jsonl"
            products = root / "products.jsonl"
            image = "https://example.invalid/shared.jpg"
            self._write_jsonl(
                diagnostic,
                [{
                    "product_id": "14031",
                    "ean": "8480000140318",
                    "canonical_status": "REVIEW",
                    "corroborated_fields": 1,
                    "independent_engine_families": 3,
                    "basis": "100_g",
                    "diagnostic_candidate_values": {"calories": 100, "fat_g": 2, "carbohydrate_g": 3, "protein_g": 4},
                    "safety_blockers": [],
                    "image_url": image,
                }],
            )
            self._write_jsonl(
                products,
                [{
                    "product_id": "14031",
                    "ean": "8436039788039",
                    "photos": [{"zoom": image, "perspective": 9}],
                }],
            )
            selected, summary = build_one_of_four_candidates(diagnostic, products)
            self.assertEqual(selected, [])
            self.assertEqual(summary["reassigned_current_product_ids"], ["14031"])
            self.assertEqual(summary["unmatched_current_first_party_p9"], [])

    def test_missing_ean_or_replaced_or_non_p9_image_is_not_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diagnostic = root / "diagnostic.jsonl"
            products = root / "products.jsonl"
            exact = "https://example.invalid/old.jpg"
            self._write_jsonl(
                diagnostic,
                [
                    {
                        "product_id": "100",
                        "ean": "84100",
                        "canonical_status": "REVIEW",
                        "corroborated_fields": 1,
                        "independent_engine_families": 2,
                        "basis": "100_ml",
                        "diagnostic_candidate_values": {"calories": 20, "fat_g": 0, "carbohydrate_g": 5, "protein_g": 0},
                        "safety_blockers": [],
                        "image_url": exact,
                    },
                    {
                        "product_id": "200",
                        "ean": "84200",
                        "canonical_status": "REVIEW",
                        "corroborated_fields": 1,
                        "independent_engine_families": 2,
                        "basis": "100_g",
                        "diagnostic_candidate_values": {"calories": 100, "fat_g": 2, "carbohydrate_g": 3, "protein_g": 4},
                        "safety_blockers": [],
                        "image_url": "https://example.invalid/200.jpg",
                    },
                    {
                        "product_id": "300",
                        "ean": "84300",
                        "canonical_status": "REVIEW",
                        "corroborated_fields": 1,
                        "independent_engine_families": 2,
                        "basis": "100_g",
                        "diagnostic_candidate_values": {"calories": 100, "fat_g": 2, "carbohydrate_g": 3, "protein_g": 4},
                        "safety_blockers": [],
                        "image_url": "https://example.invalid/300.jpg",
                    },
                ],
            )
            self._write_jsonl(
                products,
                [
                    {
                        "product_id": "100",
                        "ean": "84100",
                        "photos": [{"zoom": exact, "perspective": 7}],
                    },
                    {
                        "product_id": "200",
                        "ean": "84200",
                        "photos": [{"zoom": "https://example.invalid/replaced.jpg", "perspective": 9}],
                    },
                    {
                        "product_id": "300",
                        "photos": [{"zoom": "https://example.invalid/300.jpg", "perspective": 9}],
                    },
                ],
            )
            selected, summary = build_one_of_four_candidates(diagnostic, products)
            self.assertEqual(selected, [])
            self.assertEqual(summary["unmatched_current_first_party_p9"], ["100", "200"])
            self.assertEqual(summary["missing_current_ean"], ["300"])

    def test_limit_prefers_structured_ingredients_then_stronger_family_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diagnostic = root / "diagnostic.jsonl"
            products = root / "products.jsonl"
            diagnostics = []
            product_rows = []
            for pid, families, ingredients in (("100", 2, None), ("200", 2, "x"), ("300", 3, "x")):
                image = f"https://example.invalid/{pid}.jpg"
                ean = f"84{pid}"
                diagnostics.append(
                    {
                        "product_id": pid,
                        "ean": ean,
                        "canonical_status": "REVIEW",
                        "corroborated_fields": 1,
                        "independent_engine_families": families,
                        "basis": "100_g",
                        "diagnostic_candidate_values": {"calories": 100, "fat_g": 2, "carbohydrate_g": 3, "protein_g": 4},
                        "safety_blockers": [],
                        "image_url": image,
                        "confidence": 0.9,
                    }
                )
                product_rows.append(
                    {
                        "product_id": pid,
                        "ean": ean,
                        "ingredients": ingredients,
                        "photos": [{"zoom": image, "perspective": 9}],
                    }
                )
            self._write_jsonl(diagnostic, diagnostics)
            self._write_jsonl(products, product_rows)

            selected, _ = build_one_of_four_candidates(diagnostic, products, limit=2)
            self.assertEqual([row["product_id"] for row in selected], ["300", "200"])


if __name__ == "__main__":
    unittest.main()
