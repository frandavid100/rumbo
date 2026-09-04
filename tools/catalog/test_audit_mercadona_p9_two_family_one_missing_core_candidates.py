from __future__ import annotations

import unittest

from audit_mercadona_p9_two_family_one_missing_core_candidates import candidate_payload

CORE = {"calories": 100.0, "protein_g": 5.0, "carbohydrate_g": 12.0, "fat_g": 3.0}


def row(
    *,
    missing="fat_g",
    families=2,
    corroborated=3,
    perspective=9,
    basis="100_g",
    reasons=None,
    status="REVIEW",
    replay_status="REVIEW",
):
    values = dict(CORE)
    if missing is not None:
        values[missing] = None
    fields = []
    for field, value in values.items():
        if value is None:
            continue
        fields.append(
            {
                "name": field,
                "value": value,
                "corroborated": True,
                "engine_families": ["paddleocr", "easyocr"],
            }
        )
    ensemble = {
        "basis": basis,
        "nutrition": values,
        "independent_engine_families": families,
        "corroborated_fields": corroborated,
        "confidence": 0.90,
        "fields": fields,
        "reasons": list(reasons or ["MISSING_CORE_FIELDS"]),
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
    def test_two_family_three_corroborated_one_missing_is_candidate(self):
        payload = candidate_payload(row(missing="fat_g"))
        self.assertIsNotNone(payload)
        self.assertEqual(payload["missing_core_field"], "fat_g")
        self.assertEqual(
            payload["observed_core_fields"],
            ["calories", "carbohydrate_g", "protein_g"],
        )
        self.assertEqual(payload["independent_engine_families"], 2)
        self.assertEqual(payload["corroborated_fields"], 3)
        self.assertFalse(payload["redistribution_allowed"])
        self.assertEqual(payload["CLASSIFIED"], 0)
        self.assertEqual(payload["MENU_ELIGIBLE"], 0)

    def test_each_possible_single_missing_core_is_allowed(self):
        for field in CORE:
            with self.subTest(field=field):
                payload = candidate_payload(row(missing=field))
                self.assertIsNotNone(payload)
                self.assertEqual(payload["missing_core_field"], field)

    def test_complete_and_two_missing_rows_are_excluded(self):
        self.assertIsNone(candidate_payload(row(missing=None, corroborated=4)))
        candidate_row = row(missing="fat_g", corroborated=2)
        ensemble = candidate_row["replay"]["attempt_ensembles"][0]
        ensemble["nutrition"]["protein_g"] = None
        ensemble["fields"] = [field for field in ensemble["fields"] if field["name"] != "protein_g"]
        self.assertIsNone(candidate_payload(candidate_row))

    def test_wrong_family_or_corroboration_strata_are_excluded(self):
        self.assertIsNone(candidate_payload(row(families=1)))
        self.assertIsNone(candidate_payload(row(families=3)))
        self.assertIsNone(candidate_payload(row(corroborated=2)))
        self.assertIsNone(candidate_payload(row(corroborated=4)))

    def test_non_p9_and_unstable_review_are_excluded(self):
        self.assertIsNone(candidate_payload(row(perspective=7)))
        self.assertIsNone(candidate_payload(row(status="DECLARED")))
        self.assertIsNone(candidate_payload(row(replay_status="DECLARED")))

    def test_unsafe_basis_is_excluded(self):
        self.assertIsNone(candidate_payload(row(basis=None)))
        self.assertIsNone(
            candidate_payload(row(reasons=["UNCORROBORATED_BASIS", "MISSING_CORE_FIELDS"]))
        )

    def test_conflicts_and_energy_mismatch_are_excluded(self):
        self.assertIsNone(candidate_payload(row(reasons=["OCR_FIELD_CONFLICT:fat_g"])))
        self.assertIsNone(
            candidate_payload(row(reasons=["OCR_SAME_ENGINE_CONFLICT:protein_g:paddleocr"]))
        )
        self.assertIsNone(candidate_payload(row(reasons=["OCR_BASIS_CONFLICT"])))
        self.assertIsNone(candidate_payload(row(reasons=["ENERGY_MACRO_MISMATCH:declared=100"])))

    def test_conflict_in_original_attempt_is_excluded(self):
        candidate_row = row()
        original = dict(candidate_row["replay"]["attempt_ensembles"][0])
        original["reasons"] = ["OCR_FIELD_CONFLICT:fat_g"]
        candidate_row["attempts"] = [{"ensemble": original}]
        self.assertIsNone(candidate_payload(candidate_row))

    def test_values_conflict_in_original_attempt_is_excluded(self):
        candidate_row = row()
        original = dict(candidate_row["replay"]["attempt_ensembles"][0])
        original["values_conflict"] = True
        candidate_row["attempts"] = [{"ensemble": original}]
        self.assertIsNone(candidate_payload(candidate_row))

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

    def test_missing_field_must_not_have_a_field_row(self):
        candidate_row = row()
        ensemble = candidate_row["replay"]["attempt_ensembles"][0]
        ensemble["fields"].append(
            {
                "name": "fat_g",
                "value": None,
                "corroborated": False,
                "engine_families": [],
            }
        )
        self.assertIsNone(candidate_payload(candidate_row))


if __name__ == "__main__":
    unittest.main()
