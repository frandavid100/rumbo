from __future__ import annotations

import unittest

from audit_mercadona_p9_single_family_candidates import candidate_payload


CORE = {"calories": 100.0, "protein_g": 5.0, "carbohydrate_g": 12.0, "fat_g": 3.0}


def row(*, families=1, corroborated=0, basis="100_g", nutrition=None, reasons=None, status="REVIEW", replay_status="REVIEW"):
    ensemble = {
        "basis": basis,
        "nutrition": dict(CORE if nutrition is None else nutrition),
        "independent_engine_families": families,
        "corroborated_fields": corroborated,
        "confidence": 0.6,
        "reasons": list(reasons or []),
    }
    return {
        "product_id": "123",
        "ean": "8480000000123",
        "name": "Test",
        "status": status,
        "perspective": "9",
        "replay": {
            "status": replay_status,
            "basis": basis,
            "nutrition": ensemble["nutrition"],
            "attempt_ensembles": [ensemble],
        },
    }


class CandidatePayloadTests(unittest.TestCase):
    def test_safe_single_family_complete_tuple_is_candidate(self):
        payload = candidate_payload(row(reasons=["INSUFFICIENT_INDEPENDENT_OCR_ENGINES"]))
        self.assertIsNotNone(payload)
        self.assertEqual(payload["independent_engine_families"], 1)
        self.assertEqual(payload["corroborated_fields"], 0)
        self.assertEqual(payload["nutrition"], CORE)
        self.assertFalse(payload["redistribution_allowed"])
        self.assertEqual(payload["CLASSIFIED"], 0)
        self.assertEqual(payload["MENU_ELIGIBLE"], 0)

    def test_two_families_is_not_this_stratum(self):
        self.assertIsNone(candidate_payload(row(families=2)))

    def test_any_existing_corroboration_is_not_this_stratum(self):
        self.assertIsNone(candidate_payload(row(corroborated=1)))

    def test_missing_core_field_is_rejected(self):
        nutrition = dict(CORE)
        nutrition.pop("fat_g")
        self.assertIsNone(candidate_payload(row(nutrition=nutrition)))

    def test_missing_explicit_basis_is_rejected(self):
        self.assertIsNone(candidate_payload(row(basis=None)))

    def test_hard_field_conflict_is_rejected(self):
        self.assertIsNone(candidate_payload(row(reasons=["OCR_FIELD_CONFLICT:fat_g"])))

    def test_same_engine_conflict_is_rejected(self):
        self.assertIsNone(candidate_payload(row(reasons=["OCR_SAME_ENGINE_CONFLICT:protein_g"])))

    def test_basis_conflict_is_rejected(self):
        self.assertIsNone(candidate_payload(row(reasons=["OCR_BASIS_CONFLICT"])))

    def test_energy_macro_mismatch_is_rejected(self):
        self.assertIsNone(candidate_payload(row(reasons=["ENERGY_MACRO_MISMATCH:declared=100"])))

    def test_only_stable_review_is_eligible(self):
        self.assertIsNone(candidate_payload(row(status="DECLARED")))
        self.assertIsNone(candidate_payload(row(replay_status="DECLARED")))


if __name__ == "__main__":
    unittest.main()
