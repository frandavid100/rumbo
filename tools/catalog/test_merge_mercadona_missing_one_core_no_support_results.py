from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from merge_mercadona_missing_one_core_results import merge


class MissingOneCoreNoSupportMergeTests(unittest.TestCase):
    def test_empty_prior_support_can_promote_only_after_full_final_corroboration(self):
        baseline_row = {
            "product_id": "1",
            "ean": "8410000000001",
            "name": "Fixture",
            "perspective": 9,
            "basis": "100_g",
            "nutrition": {
                "calories": 200.0,
                "protein_g": 10.0,
                "carbohydrate_g": 20.0,
                "fat_g": None,
            },
            "missing_core_field": "fat_g",
            "missing_field_support": [],
            "source": "MERCADONA_FIRST_PARTY/label image",
            "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
            "redistribution_allowed": False,
        }
        declared_row = {
            "product_id": "1",
            "ean": "8410000000001",
            "name": "Fixture",
            "perspective": 9,
            "basis": "100_g",
            "status": "DECLARED",
            "nutrition": {
                "calories": 200.0,
                "protein_g": 10.0,
                "carbohydrate_g": 20.0,
                "fat_g": 8.0,
            },
            "attempts": [
                {
                    "ensemble": {
                        "status": "DECLARED",
                        "basis": "100_g",
                        "nutrition": {
                            "calories": 200.0,
                            "protein_g": 10.0,
                            "carbohydrate_g": 20.0,
                            "fat_g": 8.0,
                        },
                        "independent_engine_families": 3,
                        "corroborated_fields": 4,
                    }
                }
            ],
            "source": "MERCADONA_FIRST_PARTY",
            "source_record_kind": "label image",
            "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
            "redistribution_allowed": False,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results.jsonl"
            selection = root / "selection.json"
            baseline = root / "baseline.jsonl"
            out = root / "merged"
            results.write_text(json.dumps(declared_row) + "\n", encoding="utf-8")
            selection.write_text(json.dumps({"product_ids": ["1"]}) + "\n", encoding="utf-8")
            baseline.write_text(json.dumps(baseline_row) + "\n", encoding="utf-8")
            summary = merge(
                result_paths=[results],
                selection_paths=[selection],
                baseline_path=baseline,
                out=out,
                expected_universe=1,
                expected_selected=1,
            )
            promotions = json.loads((out / "safe-promotions.json").read_text(encoding="utf-8"))

        self.assertEqual(summary["safety_assessment"], "VALIDATED")
        self.assertEqual(summary["safe_promotion_products"], 1)
        self.assertEqual(summary["prior_missing_field_support_disagreements"], [])
        self.assertEqual(promotions[0]["preexisting_independent_support"], [])
        self.assertFalse(promotions[0]["prior_support_agrees"])
        self.assertEqual(promotions[0]["nutrition"]["fat_g"], 8.0)


if __name__ == "__main__":
    unittest.main()
