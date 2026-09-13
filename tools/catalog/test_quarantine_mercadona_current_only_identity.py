from __future__ import annotations

import unittest

from quarantine_mercadona_current_only_identity import build_safe_subset, current_only_introductions


BASE = {
    "schema_version": "1.0.1",
    "canonical_status_source": "run-union-summary/latest-live reconciliation",
    "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
    "source": "MERCADONA_FIRST_PARTY/label image",
    "source_record_kind": "label image",
    "redistribution_allowed": False,
    "missing_values_inferred": False,
    "structured_api_macros_claimed": False,
    "classified": False,
    "menu_eligible": False,
}


def row(product_id: str, status: str, usable: bool) -> dict:
    return {
        **BASE,
        "product_id": product_id,
        "status": status,
        "usable_complete": usable,
        "nutrition": {"calories": 100.0, "protein_g": 1.0, "carbohydrate_g": 2.0, "fat_g": 3.0} if usable else None,
        "nutrition_provenance": {} if usable else None,
        "latest_live_run_id": 20 if usable else None,
        "workflow_names": [],
    }


class CurrentOnlyIdentityQuarantineTests(unittest.TestCase):
    def test_only_first_seen_current_delta_ids_are_quarantined(self) -> None:
        summary = {
            "runs": [
                {"run_id": 10, "workflow_names": ["Historical OCR"], "new_product_ids": ["1", "2"]},
                {
                    "run_id": 20,
                    "workflow_names": ["Catalog Mercadona neural OCR p9 no-ingredients current delta"],
                    "new_product_ids": ["3", "4"],
                },
                {
                    "run_id": 30,
                    "workflow_names": ["Catalog Mercadona neural OCR p9 no-ingredients current delta"],
                    "new_product_ids": [],
                },
            ]
        }
        quarantine = current_only_introductions(summary)
        self.assertEqual(set(quarantine), {"3", "4"})
        safe, manifest = build_safe_subset(
            summary,
            [row("1", "DECLARED", True), row("2", "REVIEW", False), row("3", "DECLARED", True), row("4", "REVIEW", False)],
        )
        self.assertEqual([item["product_id"] for item in safe], ["1", "2"])
        self.assertEqual(manifest["quarantined_current_only_product_ids"], ["3", "4"])
        self.assertEqual(manifest["quarantined_usable_product_ids"], ["3"])
        self.assertEqual(manifest["safe_subset_usable_complete"], 1)
        self.assertFalse(manifest["historical_snapshot_full_parity_verified"])

    def test_later_current_delta_observation_does_not_quarantine_historical_id(self) -> None:
        summary = {
            "runs": [
                {"run_id": 10, "workflow_names": ["Historical OCR"], "new_product_ids": ["1"]},
                {
                    "run_id": 20,
                    "workflow_names": ["Catalog Mercadona neural OCR p9 no-ingredients current delta"],
                    "new_product_ids": [],
                    "overlap_product_ids": ["1"],
                },
            ]
        }
        self.assertEqual(current_only_introductions(summary), {})
        safe, manifest = build_safe_subset(summary, [row("1", "DECLARED", True)])
        self.assertEqual(len(safe), 1)
        self.assertEqual(manifest["quarantined_current_only_products"], 0)

    def test_provenance_drift_fails_closed(self) -> None:
        summary = {"runs": [{"run_id": 10, "workflow_names": ["Historical OCR"], "new_product_ids": ["1"]}]}
        bad = row("1", "DECLARED", True)
        bad["redistribution_allowed"] = True
        with self.assertRaises(ValueError):
            build_safe_subset(summary, [bad])


if __name__ == "__main__":
    unittest.main()
