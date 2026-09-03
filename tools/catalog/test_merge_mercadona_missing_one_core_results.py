from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from merge_mercadona_missing_one_core_results import merge


class MissingOneCoreMergeTests(unittest.TestCase):
    def _baseline(self):
        return {
            "product_id": "23225",
            "ean": "8480000232250",
            "name": "Crema de calabaza y zanahoria Hacendado",
            "perspective": 9,
            "basis": "100_g",
            "nutrition": {
                "calories": 48.0,
                "protein_g": 0.9,
                "carbohydrate_g": 4.2,
                "fat_g": None,
            },
            "missing_core_field": "fat_g",
            "missing_field_support": [
                {
                    "engine": "paddleocr",
                    "engine_family": "paddleocr",
                    "basis": "100_g",
                    "value": 24.0,
                }
            ],
            "source": "MERCADONA_FIRST_PARTY/label image",
            "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
            "redistribution_allowed": False,
        }

    def _declared(self):
        return {
            "product_id": "23225",
            "ean": "8480000232250",
            "name": "Crema de calabaza y zanahoria Hacendado",
            "perspective": 9,
            "basis": "100_g",
            "status": "DECLARED",
            "nutrition": {
                "calories": 48.0,
                "protein_g": 0.9,
                "carbohydrate_g": 4.2,
                "fat_g": 2.89,
            },
            "attempts": [
                {
                    "ensemble": {
                        "status": "DECLARED",
                        "basis": "100_g",
                        "nutrition": {
                            "calories": 48.0,
                            "protein_g": 0.9,
                            "carbohydrate_g": 4.2,
                            "fat_g": 2.89,
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

    def _run(self, row):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results.jsonl"
            selection = root / "selection.json"
            baseline = root / "baseline.jsonl"
            out = root / "merged"
            results.write_text(json.dumps(row) + "\n", encoding="utf-8")
            selection.write_text(
                json.dumps({"product_ids": ["23225"]}) + "\n", encoding="utf-8"
            )
            baseline.write_text(json.dumps(self._baseline()) + "\n", encoding="utf-8")
            summary = merge(
                result_paths=[results],
                selection_paths=[selection],
                baseline_path=baseline,
                out=out,
                expected_universe=1,
                expected_selected=1,
            )
            promotions = json.loads((out / "safe-promotions.json").read_text(encoding="utf-8"))
            return summary, promotions

    def test_new_fully_corroborated_value_can_override_noisy_prior_single_engine_support(self):
        summary, promotions = self._run(self._declared())
        self.assertEqual(summary["safety_assessment"], "VALIDATED")
        self.assertEqual(summary["safe_promotion_products"], 1)
        self.assertEqual(summary["prior_missing_field_support_disagreements"][0]["field"], "fat_g")
        self.assertFalse(promotions[0]["prior_support_agrees"])
        self.assertEqual(promotions[0]["nutrition"]["fat_g"], 2.89)

    def test_rejects_energy_incoherent_declared_as_unsafe(self):
        row = self._declared()
        row["nutrition"]["fat_g"] = 24.0
        row["attempts"][0]["ensemble"]["nutrition"]["fat_g"] = 24.0
        summary, promotions = self._run(row)
        self.assertEqual(summary["safety_assessment"], "FAILED")
        self.assertEqual(summary["safe_promotion_products"], 0)
        self.assertEqual(len(summary["unsafe_declared"]), 1)
        self.assertEqual(promotions, [])

    def test_changed_preexisting_field_is_not_promoted(self):
        row = self._declared()
        row["nutrition"]["carbohydrate_g"] = 8.0
        row["attempts"][0]["ensemble"]["nutrition"]["carbohydrate_g"] = 8.0
        summary, promotions = self._run(row)
        self.assertEqual(summary["safety_assessment"], "VALIDATED")
        self.assertEqual(summary["safe_promotion_products"], 0)
        self.assertEqual(len(summary["rejected_declared"]), 1)
        self.assertEqual(promotions, [])

    def test_provenance_error_fails_contract_and_cannot_promote(self):
        row = self._declared()
        row["redistribution_allowed"] = True
        summary, promotions = self._run(row)
        self.assertEqual(summary["safety_assessment"], "FAILED")
        self.assertEqual(len(summary["provenance_errors"]), 1)
        self.assertEqual(summary["safe_promotion_products"], 0)
        self.assertEqual(promotions, [])


if __name__ == "__main__":
    unittest.main()
