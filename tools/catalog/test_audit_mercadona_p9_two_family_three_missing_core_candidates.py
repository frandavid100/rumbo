from __future__ import annotations

import copy
import unittest

from audit_mercadona_p9_two_family_three_missing_core_candidates import candidate_payload


def safe_row() -> dict:
    ensemble = {
        "basis": "100_g",
        "nutrition": {"calories": 123.0},
        "independent_engine_families": 2,
        "corroborated_fields": 1,
        "confidence": 0.9,
        "reasons": ["MISSING_CORE:protein_g,carbohydrate_g,fat_g"],
        "fields": [
            {
                "name": "calories",
                "value": 123.0,
                "corroborated": True,
                "engine_families": ["paddleocr", "tesseract"],
            }
        ],
    }
    return {
        "product_id": "1",
        "ean": "8410000000001",
        "name": "Producto",
        "perspective": 9,
        "status": "REVIEW",
        "replay": {"status": "REVIEW", "basis": "100_g", "nutrition": {"calories": 123.0}, "attempt_ensembles": [ensemble]},
    }


class CandidatePayloadTest(unittest.TestCase):
    def test_accepts_exactly_one_corroborated_core_and_three_missing(self) -> None:
        payload = candidate_payload(safe_row())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["observed_core_fields"], ["calories"])
        self.assertEqual(payload["missing_core_fields"], ["carbohydrate_g", "fat_g", "protein_g"])
        self.assertEqual(payload["independent_engine_families"], 2)

    def test_rejects_hard_conflict(self) -> None:
        row = safe_row()
        row["replay"]["attempt_ensembles"][0]["reasons"].append("OCR_FIELD_CONFLICT:calories")
        self.assertIsNone(candidate_payload(row))

    def test_rejects_uncorroborated_observed_field(self) -> None:
        row = safe_row()
        row["replay"]["attempt_ensembles"][0]["fields"][0]["corroborated"] = False
        self.assertIsNone(candidate_payload(row))

    def test_rejects_values_conflict_in_any_attempt(self) -> None:
        row = safe_row()
        conflict = copy.deepcopy(row["replay"]["attempt_ensembles"][0])
        conflict["values_conflict"] = True
        conflict["confidence"] = 0.1
        row["replay"]["attempt_ensembles"].append(conflict)
        self.assertIsNone(candidate_payload(row))

    def test_rejects_two_observed_core_fields(self) -> None:
        row = safe_row()
        ensemble = row["replay"]["attempt_ensembles"][0]
        ensemble["nutrition"]["protein_g"] = 6.0
        ensemble["corroborated_fields"] = 2
        ensemble["fields"].append({
            "name": "protein_g",
            "value": 6.0,
            "corroborated": True,
            "engine_families": ["paddleocr", "tesseract"],
        })
        self.assertIsNone(candidate_payload(row))


if __name__ == "__main__":
    unittest.main()
