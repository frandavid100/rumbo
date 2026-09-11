import json
from pathlib import Path
import tempfile
import unittest

from mercadona_near_safe_current_image_rescue import build_current_image_rescue_candidates


class MercadonaNearSafeCurrentImageRescueTest(unittest.TestCase):
    def _diagnostic(self, pid="2787", **overrides):
        row = {
            "product_id": pid,
            "canonical_status": "REVIEW",
            "corroborated_fields": 2,
            "independent_engine_families": 3,
            "basis": "100_g",
            "diagnostic_candidate_values": {
                "calories": 250,
                "fat_g": 10,
                "carbohydrate_g": 30,
                "protein_g": 8,
            },
            "safety_blockers": [],
            "image_url": f"https://old.invalid/{pid}.jpg",
            "confidence": 0.95,
            "latest_raw_run_id": 123,
        }
        row.update(overrides)
        return row

    def _run(self, diagnostics, products, *, limit=8):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diagnostic = root / "diagnostic.jsonl"
            product_path = root / "products.jsonl"
            diagnostic.write_text("".join(json.dumps(x) + "\n" for x in diagnostics), encoding="utf-8")
            product_path.write_text("".join(json.dumps(x) + "\n" for x in products), encoding="utf-8")
            return build_current_image_rescue_candidates(
                diagnostic, product_path, corroborated_fields=2, limit=limit
            )

    def test_replacement_single_p9_is_new_observation_without_cross_image_fusion(self):
        selected, summary = self._run(
            [self._diagnostic()],
            [{
                "product_id": "2787",
                "ingredients": "x",
                "source_url": "https://tienda.mercadona.es/api/v1_1/products/2787?lang=es",
                "observed_at": "2026-09-11T12:00:00+00:00",
                "photos": [{"zoom": "https://new.invalid/2787.jpg", "perspective": 9}],
            }],
        )
        self.assertEqual([r["product_id"] for r in selected], ["2787"])
        meta = selected[0]["_current_image_rescue_meta"]
        self.assertEqual(meta["canonical_prior_image_url"], "https://old.invalid/2787.jpg")
        self.assertEqual(meta["current_image_url"], "https://new.invalid/2787.jpg")
        self.assertFalse(meta["cross_image_fusion"])
        self.assertTrue(meta["current_observation_must_satisfy_declared_contract_independently"])
        self.assertEqual(summary["selected_product_ids"], ["2787"])
        self.assertFalse(summary["cross_image_fusion"])

    def test_canonical_image_still_current_is_reserved_for_exact_image_route(self):
        selected, summary = self._run(
            [self._diagnostic()],
            [{
                "product_id": "2787",
                "photos": [
                    {"zoom": "https://old.invalid/2787.jpg", "perspective": 9},
                    {"zoom": "https://alt.invalid/2787.jpg", "perspective": 1},
                ],
            }],
        )
        self.assertEqual(selected, [])
        self.assertEqual(summary["canonical_image_still_current"], ["2787"])

    def test_multiple_current_p9_replacements_are_rejected_as_ambiguous(self):
        selected, summary = self._run(
            [self._diagnostic()],
            [{
                "product_id": "2787",
                "photos": [
                    {"zoom": "https://new.invalid/a.jpg", "perspective": 9},
                    {"zoom": "https://new.invalid/b.jpg", "perspective": 9},
                ],
            }],
        )
        self.assertEqual(selected, [])
        self.assertEqual(summary["ambiguous_current_p9"], ["2787"])

    def test_blocked_or_incomplete_diagnostic_never_becomes_target(self):
        blocked = self._diagnostic("1", safety_blockers=["OCR_FIELD_CONFLICT:fat_g"])
        incomplete = self._diagnostic("2")
        incomplete["diagnostic_candidate_values"].pop("protein_g")
        products = [
            {"product_id": "1", "photos": [{"zoom": "https://new.invalid/1.jpg", "perspective": 9}]},
            {"product_id": "2", "photos": [{"zoom": "https://new.invalid/2.jpg", "perspective": 9}]},
        ]
        selected, summary = self._run([blocked, incomplete], products)
        self.assertEqual(selected, [])
        self.assertEqual(summary["canonical_targets"], 0)

    def test_limit_zero_keeps_all_and_prioritizes_structured_ingredients(self):
        diagnostics = [self._diagnostic(str(pid)) for pid in (3, 1, 2)]
        products = [
            {
                "product_id": "1",
                "ingredients": None,
                "photos": [{"zoom": "https://new.invalid/1.jpg", "perspective": 9}],
            },
            {
                "product_id": "2",
                "ingredients": "x",
                "photos": [{"zoom": "https://new.invalid/2.jpg", "perspective": 9}],
            },
            {
                "product_id": "3",
                "ingredients": "x",
                "photos": [{"zoom": "https://new.invalid/3.jpg", "perspective": 9}],
            },
        ]
        selected, summary = self._run(diagnostics, products, limit=0)
        self.assertEqual([r["product_id"] for r in selected], ["2", "3", "1"])
        self.assertEqual(summary["selected"], 3)


if __name__ == "__main__":
    unittest.main()
