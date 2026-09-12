from __future__ import annotations

import unittest

from audit_mercadona_current_identity import audit_identity_rows


class CurrentIdentityAuditTests(unittest.TestCase):
    def test_match_and_reassignment_are_distinguished_without_mutating_canonical(self) -> None:
        report, rows = audit_identity_rows(
            [
                {"product_id": "10", "ean": "111"},
                {"product_id": "20", "ean": "222"},
            ],
            [
                {"product_id": "10", "ean": "111", "name": "Same"},
                {"product_id": "20", "ean": "999", "name": "Replacement"},
            ],
            [],
            observed_at="2026-09-12T00:00:00+00:00",
        )
        by_id = {row["product_id"]: row for row in rows}
        self.assertEqual(report["status_counts"], {"MATCH": 1, "REASSIGNED_PRODUCT_ID": 1})
        self.assertEqual(report["reassigned_ids"], ["20"])
        self.assertEqual(by_id["20"]["anchor_ean"], "222")
        self.assertEqual(by_id["20"]["current_eans"], ["999"])
        self.assertFalse(by_id["20"]["canonical_mutation_allowed"])
        self.assertFalse(report["nutrition_values_changed"])

    def test_missing_ean_not_found_fetch_error_and_no_observation_fail_closed(self) -> None:
        report, rows = audit_identity_rows(
            [
                {"product_id": "1", "ean": "101"},
                {"product_id": "2", "ean": "202"},
                {"product_id": "3", "ean": "303"},
                {"product_id": "4", "ean": "404"},
            ],
            [{"product_id": "1", "ean": None, "name": "No barcode"}],
            [
                {"product_id": "2", "error": "HTTPError:HTTP Error 404: Not Found"},
                {"product_id": "4", "error": "HTTPError:HTTP Error 503: Service Unavailable"},
            ],
        )
        by_id = {row["product_id"]: row for row in rows}
        self.assertEqual(by_id["1"]["status"], "MISSING_CURRENT_EAN")
        self.assertEqual(by_id["2"]["status"], "CURRENT_PRODUCT_NOT_FOUND")
        self.assertEqual(by_id["3"]["status"], "NO_CURRENT_OBSERVATION")
        self.assertEqual(by_id["4"]["status"], "FETCH_ERROR")
        self.assertEqual(report["current_not_found_products"], 1)
        self.assertEqual(report["current_not_found_ids"], ["2"])
        self.assertEqual(report["unresolved_products"], 4)

    def test_404_must_be_the_only_fetch_outcome_to_count_as_current_not_found(self) -> None:
        report, rows = audit_identity_rows(
            [{"product_id": "5", "ean": "505"}],
            [],
            [
                {"product_id": "5", "error": "HTTPError:HTTP Error 404: Not Found"},
                {"product_id": "5", "error": "TimeoutError:timed out"},
            ],
        )
        self.assertEqual(rows[0]["status"], "FETCH_ERROR")
        self.assertEqual(report["current_not_found_products"], 0)

    def test_conflicting_current_eans_are_ambiguous(self) -> None:
        report, rows = audit_identity_rows(
            [{"product_id": "7", "ean": "700"}],
            [
                {"product_id": "7", "ean": "700"},
                {"product_id": "7", "ean": "701"},
            ],
            [],
        )
        self.assertEqual(rows[0]["status"], "AMBIGUOUS_CURRENT_IDENTITY")
        self.assertEqual(report["matched_products"], 0)
        self.assertEqual(report["unresolved_products"], 1)

    def test_conflicting_anchor_eans_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            audit_identity_rows(
                [
                    {"product_id": "8", "ean": "800"},
                    {"product_id": "8", "ean": "801"},
                ],
                [],
                [],
            )


if __name__ == "__main__":
    unittest.main()
