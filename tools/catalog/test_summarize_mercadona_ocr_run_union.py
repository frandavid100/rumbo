from __future__ import annotations

import unittest

from summarize_mercadona_ocr_run_union import (
    classify_review_reason_families,
    is_canonical_status_row,
    reconcile_latest_observations,
    summarize_declared_to_review_transitions,
)


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


class ReviewTransitionDiagnosticTests(unittest.TestCase):
    def test_reason_classifier_reads_nested_ensemble_conflicts_without_promoting_anything(self):
        row = {
            "status": "REVIEW",
            "attempts": [
                {
                    "nutrition_issue": "INSUFFICIENT_INDEPENDENT_CORROBORATION",
                    "ensemble": {
                        "review_reasons": ["OCR_FIELD_CONFLICT:protein_g"],
                    },
                }
            ],
        }
        self.assertEqual(
            classify_review_reason_families(row),
            ["EXPLICIT_FIELD_CONFLICT", "INSUFFICIENT_CORROBORATION"],
        )

    def test_reason_classifier_does_not_treat_zero_visual_regions_as_no_region_when_fallback_ocr_exists(self):
        row = {
            "status": "REVIEW",
            "visual_regions_detected": 0,
            "attempts": [{"ocr_count": 18, "nutrition_issue": "MISSING_FIELD:protein_g"}],
        }
        self.assertEqual(classify_review_reason_families(row), ["INCOMPLETE_EXTRACTION"])

    def test_reason_classifier_marks_no_region_only_with_no_ocr_signal(self):
        row = {
            "status": "REVIEW",
            "visual_regions_detected": 0,
            "attempts": [{"ocr_count": 0, "nutrition_issue": "NO_VISUAL_REGION"}],
        }
        self.assertEqual(classify_review_reason_families(row), ["NO_VISUAL_REGION"])

    def test_transition_summary_separates_explicit_conflict_from_transient_incomplete_review(self):
        history = {
            "A": [
                (10, "DECLARED", ["NONE"]),
                (20, "REVIEW", ["INCOMPLETE_EXTRACTION"]),
            ],
            "B": [
                (10, "DECLARED", ["NONE"]),
                (30, "REVIEW", ["EXPLICIT_FIELD_CONFLICT"]),
            ],
            "C": [(30, "REVIEW", ["NO_VISUAL_REGION"])],
            "D": [(10, "DECLARED", ["NONE"]), (40, "DECLARED", ["NONE"])],
        }
        summary = summarize_declared_to_review_transitions(history)
        self.assertEqual(summary["historical_declared_products"], 3)
        self.assertEqual(summary["latest_review_after_historical_declared"], 2)
        self.assertEqual(summary["latest_review_after_historical_declared_product_ids"], ["A", "B"])
        self.assertEqual(summary["reason_family_counts"], {
            "EXPLICIT_FIELD_CONFLICT": 1,
            "INCOMPLETE_EXTRACTION": 1,
        })
        self.assertEqual(summary["explicit_contradiction_products"], 1)
        self.assertEqual(summary["non_contradictory_review_products"], 1)


if __name__ == "__main__":
    unittest.main()
