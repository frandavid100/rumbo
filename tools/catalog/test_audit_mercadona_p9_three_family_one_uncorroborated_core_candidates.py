from __future__ import annotations

import unittest

from audit_mercadona_p9_three_family_one_uncorroborated_core_candidates import candidate_payload

CORE = {"calories": 100.0, "protein_g": 5.0, "carbohydrate_g": 12.0, "fat_g": 3.0}


def row(*, families=3, corroborated=3, perspective=9, basis="100_g", nutrition=None, reasons=None,
        status="REVIEW", replay_status="REVIEW", uncorroborated="fat_g", source_family="paddleocr"):
    values = dict(CORE if nutrition is None else nutrition)
    fields = [
        {
            "name": field,
            "value": value,
            "corroborated": field != uncorroborated,
            "engine_families": ["paddleocr", "tesseract"] if field != uncorroborated else [source_family],
        }
        for field, value in values.items()
    ]
    ensemble = {
        "basis": basis,
        "nutrition": values,
        "independent_engine_families": families,
        "corroborated_fields": corroborated,
        "confidence": 0.84,
        "fields": fields,
        "reasons": list(reasons or ["UNCORROBORATED_CORE_FIELDS", "LOW_EXTRACTION_CONFIDENCE"]),
    }
    return {
        "product_id": "123",
        "ean": "8480000000123",
        "name": "Test",
        "status": status,
        "perspective": perspective,
        "replay": {"status": replay_status, "basis": basis, "nutrition": values, "attempt_ensembles": [ensemble]},
    }


class CandidatePayloadTests(unittest.TestCase):
    def test_three_family_one_uncorroborated_core_is_candidate(self):
        payload = candidate_payload(row())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["uncorroborated_core_field"], "fat_g")
        self.assertEqual(payload["uncorroborated_source_family"], "paddleocr")
        self.assertEqual(payload["independent_engine_families"], 3)
        self.assertEqual(payload["corroborated_fields"], 3)
        self.assertFalse(payload["redistribution_allowed"])
        self.assertEqual(payload["CLASSIFIED"], 0)
        self.assertEqual(payload["MENU_ELIGIBLE"], 0)

    def test_two_family_previous_stratum_is_excluded(self):
        self.assertIsNone(candidate_payload(row(families=2)))

    def test_wrong_corroborated_count_is_excluded(self):
        self.assertIsNone(candidate_payload(row(corroborated=2)))
        self.assertIsNone(candidate_payload(row(corroborated=4)))

    def test_non_p9_is_excluded(self):
        self.assertIsNone(candidate_payload(row(perspective=7)))

    def test_missing_core_is_excluded(self):
        nutrition = dict(CORE)
        nutrition.pop("fat_g")
        self.assertIsNone(candidate_payload(row(nutrition=nutrition, uncorroborated="protein_g")))

    def test_unsafe_basis_is_excluded(self):
        self.assertIsNone(candidate_payload(row(basis=None)))
        self.assertIsNone(candidate_payload(row(reasons=["UNCORROBORATED_BASIS", "UNCORROBORATED_CORE_FIELDS"])))

    def test_conflicts_and_energy_mismatch_are_excluded(self):
        self.assertIsNone(candidate_payload(row(reasons=["OCR_FIELD_CONFLICT:fat_g"])))
        self.assertIsNone(candidate_payload(row(reasons=["OCR_SAME_ENGINE_CONFLICT:fat_g:tesseract"])))
        self.assertIsNone(candidate_payload(row(reasons=["OCR_BASIS_CONFLICT"])))
        self.assertIsNone(candidate_payload(row(reasons=["ENERGY_MACRO_MISMATCH:declared=100"])))

    def test_only_stable_review_is_eligible(self):
        self.assertIsNone(candidate_payload(row(status="DECLARED")))
        self.assertIsNone(candidate_payload(row(replay_status="DECLARED")))

    def test_uncorroborated_field_must_be_single_family_observation(self):
        r = row()
        ensemble = r["replay"]["attempt_ensembles"][0]
        for field in ensemble["fields"]:
            if field["name"] == "fat_g":
                field["engine_families"] = ["paddleocr", "easyocr"]
        self.assertIsNone(candidate_payload(r))


if __name__ == "__main__":
    unittest.main()
