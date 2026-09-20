from __future__ import annotations

from types import SimpleNamespace
import unittest

import mercadona_preselected_three_of_four_variant_rescue as target


CORE = {
    "calories": 46.0,
    "fat_g": 0.0,
    "carbohydrate_g": 11.0,
    "protein_g": 0.1,
}


def ensemble(*, corroborated=2, families=2, reasons=("UNCORROBORATED_CORE_FIELDS",), nutrition=None,
             basis="100_ml", status="REVIEW", declared_usable=False):
    return SimpleNamespace(
        status=status,
        declared_usable=declared_usable,
        basis=basis,
        nutrition=CORE if nutrition is None else nutrition,
        independent_engine_families=families,
        corroborated_fields=corroborated,
        reasons=reasons,
    )


class PreselectedThreeOfFourVariantRescueTests(unittest.TestCase):
    def test_routes_clean_one_of_four_fresh_reread(self):
        self.assertTrue(target.should_run_preselected_three_of_four_variant_rescue(ensemble(corroborated=1)))

    def test_routes_clean_two_of_four_fresh_reread(self):
        self.assertTrue(target.should_run_preselected_three_of_four_variant_rescue(ensemble(corroborated=2)))

    def test_routes_clean_three_of_four_fresh_reread(self):
        self.assertTrue(target.should_run_preselected_three_of_four_variant_rescue(ensemble(corroborated=3)))

    def test_routes_clean_fresh_reread_missing_exactly_one_core_field(self):
        partial = {"calories": 46.0, "fat_g": 0.0, "carbohydrate_g": 11.0}
        self.assertTrue(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            nutrition=partial,
            corroborated=3,
            reasons=("MISSING_CORE:protein_g",),
        )))

    def test_routes_missing_one_core_field_with_two_corroborated_fields(self):
        partial = {"calories": 46.0, "fat_g": 0.0, "carbohydrate_g": 11.0}
        self.assertTrue(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            nutrition=partial,
            corroborated=2,
            reasons=("MISSING_CORE:protein_g",),
        )))

    def test_routes_missing_one_core_field_with_one_corroborated_field(self):
        partial = {"calories": 46.0, "fat_g": 0.0, "carbohydrate_g": 11.0}
        self.assertTrue(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            nutrition=partial,
            corroborated=1,
            reasons=("MISSING_CORE:protein_g",),
        )))

    def test_routes_single_family_zero_corroborated_missing_one_for_observation_retry(self):
        partial = {"calories": 494.0, "fat_g": 24.0, "carbohydrate_g": 62.0}
        self.assertTrue(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            nutrition=partial,
            families=1,
            corroborated=0,
            basis="100_g",
            reasons=("MISSING_CORE:protein_g",),
        )))

    def test_routes_single_family_complete_tuple_for_observation_retry(self):
        self.assertTrue(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            families=1,
            corroborated=0,
            basis="100_ml",
            reasons=("INSUFFICIENT_INDEPENDENT_OCR_ENGINES", "UNCORROBORATED_BASIS", "UNCORROBORATED_CORE_FIELDS"),
        )))

    def test_rejects_zero_of_four(self):
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(corroborated=0)))

    def test_rejects_tuple_missing_two_core_fields(self):
        partial = {"calories": 46.0, "carbohydrate_g": 11.0}
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            nutrition=partial,
            corroborated=2,
            reasons=("MISSING_CORE:fat_g,protein_g",),
        )))

    def test_rejects_missing_one_core_field_without_matching_missing_reason(self):
        partial = {"calories": 46.0, "fat_g": 0.0, "carbohydrate_g": 11.0}
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            nutrition=partial,
            corroborated=3,
            reasons=("UNCORROBORATED_CORE_FIELDS",),
        )))

    def test_rejects_hard_safety_blocker(self):
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            reasons=("UNCORROBORATED_CORE_FIELDS", "ENERGY_MACRO_MISMATCH"),
        )))

    def test_rejects_hard_safety_blocker_on_single_family_complete_tuple(self):
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            families=1,
            corroborated=0,
            reasons=("INSUFFICIENT_INDEPENDENT_OCR_ENGINES", "UNCORROBORATED_CORE_FIELDS", "MULTIPLE_NUTRITION_COLUMNS"),
        )))

    def test_rejects_hard_safety_blocker_on_partial_tuple(self):
        partial = {"calories": 46.0, "fat_g": 0.0, "carbohydrate_g": 11.0}
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            nutrition=partial,
            corroborated=3,
            reasons=("MISSING_CORE:protein_g", "OCR_FIELD_CONFLICT:protein_g"),
        )))

    def test_rejects_zero_engine_families_for_missing_one(self):
        partial = {"calories": 46.0, "fat_g": 0.0, "carbohydrate_g": 11.0}
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            nutrition=partial,
            families=0,
            corroborated=0,
            reasons=("MISSING_CORE:protein_g",),
        )))

    def test_rejects_already_usable(self):
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            corroborated=4,
            reasons=(),
            status="DECLARED",
            declared_usable=True,
        )))


if __name__ == "__main__":
    unittest.main()
