from __future__ import annotations

import unittest

from audit_mercadona_missing_one_core_no_support_candidates import candidate_payload


class MissingOneCoreNoSupportCandidateAuditTests(unittest.TestCase):
    def _row(self):
        return {
            "status": "REVIEW",
            "replay": {
                "status": "REVIEW",
                "basis": "100_g",
                "nutrition": {"calories": 200.0, "protein_g": 10.0, "carbohydrate_g": 20.0},
                "attempt_ensembles": [
                    {
                        "status": "REVIEW",
                        "basis": "100_g",
                        "nutrition": {"calories": 200.0, "protein_g": 10.0, "carbohydrate_g": 20.0},
                        "corroborated_fields": 3,
                        "independent_engine_families": 2,
                        "confidence": 0.9,
                        "reasons": ["MISSING_CORE:fat_g"],
                    }
                ],
            },
            "attempts": [
                {
                    "engines": {
                        "paddleocr": {
                            "status": "REVIEW",
                            "basis": "100_g",
                            "nutrition": {"calories": 200.0, "protein_g": 10.0},
                        },
                        "easyocr": {
                            "status": "REVIEW",
                            "basis": "100_g",
                            "nutrition": {"carbohydrate_g": 20.0},
                        },
                    }
                }
            ],
            "product_id": "1",
            "ean": "8410000000001",
            "name": "Fixture",
            "perspective": "9",
        }

    def test_accepts_three_corroborated_existing_fields_without_missing_field_support(self):
        payload = candidate_payload(self._row())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["missing_core_field"], "fat_g")
        self.assertEqual(payload["missing_field_support"], [])
        self.assertEqual(payload["corroborated_fields"], 3)

    def test_rejects_if_missing_field_already_has_non_tesseract_support(self):
        row = self._row()
        row["attempts"][0]["engines"]["paddleocr"]["nutrition"]["fat_g"] = 8.0
        self.assertIsNone(candidate_payload(row))

    def test_rejects_only_two_corroborated_existing_fields(self):
        row = self._row()
        row["replay"]["attempt_ensembles"][0]["corroborated_fields"] = 2
        self.assertIsNone(candidate_payload(row))

    def test_rejects_hard_conflict(self):
        row = self._row()
        row["replay"]["attempt_ensembles"][0]["reasons"].append("OCR_FIELD_CONFLICT:fat_g")
        self.assertIsNone(candidate_payload(row))

    def test_rejects_energy_mismatch(self):
        row = self._row()
        row["replay"]["attempt_ensembles"][0]["reasons"].append("ENERGY_MACRO_MISMATCH:20")
        self.assertIsNone(candidate_payload(row))

    def test_rejects_four_core_values(self):
        row = self._row()
        row["replay"]["nutrition"]["fat_g"] = 8.0
        row["replay"]["attempt_ensembles"][0]["nutrition"]["fat_g"] = 8.0
        self.assertIsNone(candidate_payload(row))


if __name__ == "__main__":
    unittest.main()
