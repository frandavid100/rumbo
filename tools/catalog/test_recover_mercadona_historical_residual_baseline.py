from __future__ import annotations

import unittest

from recover_mercadona_historical_residual_baseline import recover_current_residual, validate_recovery_baseline


def baseline_fixture():
    summary = {
        "inventory_products": 5,
        "processed_reconstructed": 2,
        "residual_total": 3,
        "p9_residual_total": 2,
        "no_p9_residual_total": 1,
    }
    canonical = [{"product_id": "a"}, {"product_id": "b"}]
    p9 = [
        {
            "product_id": "c",
            "ean": "1000000000001",
            "profile": "P9_STRUCTURED_INGREDIENTS",
            "ocr_scope_profile": "ACTIONABLE_P9_FIRST_PARTY_FOOD_SIGNAL",
        },
        {
            "product_id": "d",
            "ean": "1000000000002",
            "profile": "P9_NO_INGREDIENTS_OTHER",
            "ocr_scope_profile": "OUT_OF_SCOPE_NON_FOOD_OR_MIXED",
        },
    ]
    no_p9 = [
        {
            "product_id": "e",
            "ean": "1000000000003",
            "ocr_scope_profile": "BLOCKED_NO_P9_FOOD_ROUTE",
        }
    ]
    return summary, canonical, p9, no_p9


def identity_summary(ids):
    return {
        "final_distinct_union": len(ids),
        "identity_reconciliation": {
            "mode": "EARLIEST_RAW_LIVE_EAN_ANCHOR",
            "identity_anchored_products": len(ids),
            "identity_conflict_products": 0,
            "identity_unverified_products": 0,
            "identity_unresolved_products": 0,
        },
    }


class RecoveryBaselineTests(unittest.TestCase):
    def test_filters_newly_processed_historical_residual_without_live_inventory(self):
        summary, baseline_canonical, p9, no_p9 = baseline_fixture()
        current = [{"product_id": value} for value in ("a", "b", "c")]
        remaining_p9, remaining_no_p9, recovered = recover_current_residual(
            summary,
            baseline_canonical,
            p9,
            no_p9,
            current,
            identity_summary({"a", "b", "c"}),
            expected_inventory=5,
            expected_processed=2,
            expected_p9=2,
            expected_no_p9=1,
        )
        self.assertEqual([row["product_id"] for row in remaining_p9], ["d"])
        self.assertEqual([row["product_id"] for row in remaining_no_p9], ["e"])
        self.assertEqual(recovered["processed_reconstructed"], 3)
        self.assertEqual(recovered["residual_total"], 2)
        self.assertEqual(recovered["ocr_actionable_p9_total"], 0)
        self.assertEqual(recovered["ocr_blocked_no_p9_food_route_total"], 1)
        self.assertTrue(recovered["historical_membership_parity_verifiable"])
        self.assertTrue(recovered["historical_residual_ean_parity_verifiable"])
        self.assertTrue(recovered["historical_processed_ean_anchors_complete"])
        self.assertFalse(recovered["historical_full_identity_map_materialized"])
        self.assertFalse(recovered["historical_full_detail_snapshot_recovered"])

    def test_rejects_post_cut_product_in_current_canonical(self):
        summary, baseline_canonical, p9, no_p9 = baseline_fixture()
        current = [{"product_id": value} for value in ("a", "b", "z")]
        with self.assertRaisesRegex(ValueError, "absent from the trusted 4,280-product membership"):
            recover_current_residual(
                summary,
                baseline_canonical,
                p9,
                no_p9,
                current,
                identity_summary({"a", "b", "z"}),
                expected_inventory=5,
                expected_processed=2,
                expected_p9=2,
                expected_no_p9=1,
            )

    def test_rejects_identity_conflict(self):
        summary, baseline_canonical, p9, no_p9 = baseline_fixture()
        current = [{"product_id": value} for value in ("a", "b")]
        union = identity_summary({"a", "b"})
        union["identity_reconciliation"]["identity_conflict_products"] = 1
        with self.assertRaisesRegex(ValueError, "identity reconciliation is not clean"):
            recover_current_residual(
                summary,
                baseline_canonical,
                p9,
                no_p9,
                current,
                union,
                expected_inventory=5,
                expected_processed=2,
                expected_p9=2,
                expected_no_p9=1,
            )

    def test_rejects_overlap_or_missing_residual_ean(self):
        summary, baseline_canonical, p9, no_p9 = baseline_fixture()
        p9[0]["product_id"] = "a"
        with self.assertRaisesRegex(ValueError, "processed and residual partitions overlap"):
            validate_recovery_baseline(
                summary,
                baseline_canonical,
                p9,
                no_p9,
                expected_inventory=5,
                expected_processed=2,
                expected_p9=2,
                expected_no_p9=1,
            )

        summary, baseline_canonical, p9, no_p9 = baseline_fixture()
        p9[0]["ean"] = None
        with self.assertRaisesRegex(ValueError, "missing EAN"):
            validate_recovery_baseline(
                summary,
                baseline_canonical,
                p9,
                no_p9,
                expected_inventory=5,
                expected_processed=2,
                expected_p9=2,
                expected_no_p9=1,
            )


if __name__ == "__main__":
    unittest.main()
