from __future__ import annotations

import unittest

from audit_mercadona_p9_two_family_two_missing_core_candidates import candidate_payload

CORE = {"calories": 100.0, "protein_g": 5.0, "carbohydrate_g": 12.0, "fat_g": 3.0}


def row(
    *,
    observed=("calories", "protein_g"),
    families=2,
    corroborated=2,
    perspective=9,
    basis="100_g",
    reasons=None,
    status="REVIEW",
    replay_status="REVIEW",
    values_conflict=False,
):
    values = {field: (CORE[field] if field in observed else None) for field in CORE}
    fields = [
        {
            "name": field,
            "value": values[field],
            "corroborated": True,
            "engine_families": ["paddleocr", "easyocr"],
        }
        for field in observed
    ]
    ensemble = {
        "basis": basis,
        "nutrition": values,
        "independent_engine_families": families,
        "corroborated_fields": corroborated,
        "confidence": 0.90,
        "fields": fields,
        "reasons": list(reasons or ["MISSING_CORE_FIELDS"]),
        "values_conflict": values_conflict,
    }
    return {
        "product_id": "123",
        "ean": "8480000000123",
        "name": "Test",
        "status": status,
        "perspective": perspective,
        "replay": {
            "status": replay_status,
            "basis": basis,
            "nutrition": values,
            "attempt_ensembles": [ensemble],
        },
    }


class CandidatePayloadTests(unittest.TestCase):
    def test_two_family_two_corroborated_two_missing_is_candidate(self):
        payload = candidate_payload(row())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["observed_core_fields"], ["calories", "protein_g"])
        self.assertEqual(payload["missing_core_fields"], ["carbohydrate_g", "fat_g"])
        self.assertEqual(payload["independent_engine_families"], 2)
        self.assertEqual(payload["corroborated_fields"], 2)
        self.assertFalse(payload["redistribution_allowed"])
        self.assertEqual(payload["CLASSIFIED"], 0)
        self.assertEqual(payload["MENU_ELIGIBLE"], 0)

    def test_all_two_observed_combinations_are_allowed(self):
        fields = tuple(CORE)
        for i, first in enumerate(fields):
            for second in fields[i + 1:]:
                with self.subTest(observed=(first, second)):
                    payload = candidate_payload(row(observed=(first, second)))
                    self.assertIsNotNone(payload)
                    self.assertEqual(set(payload["observed_core_fields"]), {first, second})
                    self.assertEqual(set(payload["missing_core_fields"]), set(CORE) - {first, second})

    def test_wrong_observed_count_is_excluded(self):
        self.assertIsNone(candidate_payload(row(observed=("calories",))))
        self.assertIsNone(candidate_payload(row(observed=("calories", "protein_g", "fat_g"), corroborated=3)))
        self.assertIsNone(candidate_payload(row(observed=tuple(CORE), corroborated=4)))

    def test_wrong_family_or_corroboration_strata_are_excluded(self):
        self.assertIsNone(candidate_payload(row(families=1)))
        self.assertIsNone(candidate_payload(row(families=3)))
        self.assertIsNone(candidate_payload(row(corroborated=1)))
        self.assertIsNone(candidate_payload(row(corroborated=3)))

    def test_non_p9_and_unstable_review_are_excluded(self):
        self.assertIsNone(candidate_payload(row(perspective=7)))
        self.assertIsNone(candidate_payload(row(status="DECLARED")))
        self.assertIsNone(candidate_payload(row(replay_status="DECLARED")))

    def test_unsafe_basis_is_excluded(self):
        self.assertIsNone(candidate_payload(row(basis=None)))
        self.assertIsNone(candidate_payload(row(reasons=["UNCORROBORATED_BASIS", "MISSING_CORE_FIELDS"])))

    def test_conflicts_and_energy_mismatch_are_excluded(self):
        self.assertIsNone(candidate_payload(row(reasons=["OCR_FIELD_CONFLICT:fat_g"])))
        self.assertIsNone(candidate_payload(row(reasons=["OCR_SAME_ENGINE_CONFLICT:protein_g:paddleocr"])))
        self.assertIsNone(candidate_payload(row(reasons=["OCR_BASIS_CONFLICT"])))
        self.assertIsNone(candidate_payload(row(reasons=["ENERGY_MACRO_MISMATCH:declared=100"])))
        self.assertIsNone(candidate_payload(row(values_conflict=True)))

    def test_all_observed_fields_must_be_corroborated(self):
        candidate_row = row()
        ensemble = candidate_row["replay"]["attempt_ensembles"][0]
        ensemble["fields"][0]["corroborated"] = False
        self.assertIsNone(candidate_payload(candidate_row))

    def test_all_observed_fields_must_have_two_families(self):
        candidate_row = row()
        ensemble = candidate_row["replay"]["attempt_ensembles"][0]
        ensemble["fields"][0]["engine_families"] = ["paddleocr"]
        self.assertIsNone(candidate_payload(candidate_row))

    def test_missing_fields_must_not_have_field_rows(self):
        candidate_row = row()
        ensemble = candidate_row["replay"]["attempt_ensembles"][0]
        ensemble["fields"].append(
            {"name": "fat_g", "value": None, "corroborated": False, "engine_families": []}
        )
        self.assertIsNone(candidate_payload(candidate_row))

    def test_conflict_in_non_selected_attempt_is_excluded(self):
        candidate_row = row()
        conflict = dict(candidate_row["replay"]["attempt_ensembles"][0])
        conflict["confidence"] = 0.1
        conflict["values_conflict"] = True
        candidate_row["replay"]["attempt_ensembles"].append(conflict)
        self.assertIsNone(candidate_payload(candidate_row))


if __name__ == "__main__":
    unittest.main()
