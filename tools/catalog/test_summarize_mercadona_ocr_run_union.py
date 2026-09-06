from __future__ import annotations

import unittest

from summarize_mercadona_ocr_run_union import is_canonical_status_row, reconcile_latest_observations


N1 = {"calories": 100.0, "protein_g": 5.0, "carbohydrate_g": 10.0, "fat_g": 4.0}
N2 = {"calories": 101.0, "protein_g": 5.0, "carbohydrate_g": 10.0, "fat_g": 4.0}


class LatestObservationReconciliationTests(unittest.TestCase):
    def test_latest_run_replaces_older_review_with_new_declared_evidence(self):
        result = reconcile_latest_observations([
            (10, "A", "REVIEW", None),
            (20, "A", "DECLARED", N1),
        ])
        self.assertEqual(result["A"]["latest_run_id"], 20)
        self.assertEqual(result["A"]["status"], "DECLARED")
        self.assertTrue(result["A"]["usable_complete"])
        self.assertEqual(result["A"]["nutrition"], N1)

    def test_latest_review_never_inherits_older_declared_nutrition(self):
        result = reconcile_latest_observations([
            (10, "A", "DECLARED", N1),
            (20, "A", "REVIEW", None),
        ])
        self.assertEqual(result["A"]["status"], "REVIEW")
        self.assertFalse(result["A"]["usable_complete"])
        self.assertIsNone(result["A"]["nutrition"])

    def test_mixed_statuses_in_latest_run_are_never_usable(self):
        result = reconcile_latest_observations([
            (20, "A", "DECLARED", N1),
            (20, "A", "REVIEW", None),
        ])
        self.assertEqual(result["A"]["status"], "MULTIPLE_STATUSES_LATEST_RUN")
        self.assertFalse(result["A"]["usable_complete"])
        self.assertIsNone(result["A"]["nutrition"])

    def test_conflicting_declared_nutrition_in_latest_run_is_never_usable(self):
        result = reconcile_latest_observations([
            (20, "A", "DECLARED", N1),
            (20, "A", "DECLARED", N2),
        ])
        self.assertEqual(result["A"]["status"], "DECLARED")
        self.assertFalse(result["A"]["usable_complete"])
        self.assertEqual(result["A"]["nutrition_issue"], "CONFLICTING_COMPLETE_NUTRITION_LATEST_RUN")
        self.assertIsNone(result["A"]["nutrition"])

    def test_declared_missing_any_macro_is_never_usable(self):
        partial = {"calories": 100.0, "protein_g": 5.0, "carbohydrate_g": 10.0}
        result = reconcile_latest_observations([(20, "A", "DECLARED", partial)])
        self.assertEqual(result["A"]["status"], "DECLARED")
        self.assertFalse(result["A"]["usable_complete"])
        self.assertEqual(result["A"]["nutrition_issue"], "INCOMPLETE_DECLARED_NUTRITION_LATEST_RUN")

    def test_diagnostic_replay_wrapper_never_updates_canonical_status(self):
        live_row = {
            "product_id": "A",
            "status": "REVIEW",
            "nutrition": None,
            "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        }
        replay_wrapper = {
            **live_row,
            "replay": {
                "prior_status": "REVIEW",
                "status": "DECLARED",
                "nutrition": N1,
            },
        }
        self.assertTrue(is_canonical_status_row(live_row))
        self.assertFalse(is_canonical_status_row(replay_wrapper))


if __name__ == "__main__":
    unittest.main()
