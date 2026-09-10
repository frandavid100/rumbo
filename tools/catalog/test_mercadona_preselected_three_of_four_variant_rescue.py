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
    def test_routes_clean_two_of_four_fresh_reread(self):
        self.assertTrue(target.should_run_preselected_three_of_four_variant_rescue(ensemble(corroborated=2)))

    def test_routes_clean_three_of_four_fresh_reread(self):
        self.assertTrue(target.should_run_preselected_three_of_four_variant_rescue(ensemble(corroborated=3)))

    def test_rejects_one_of_four(self):
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(corroborated=1)))

    def test_rejects_incomplete_tuple(self):
        partial = {"calories": 46.0, "fat_g": 0.0, "carbohydrate_g": 11.0}
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(nutrition=partial)))

    def test_rejects_hard_safety_blocker(self):
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            reasons=("UNCORROBORATED_CORE_FIELDS", "ENERGY_MACRO_MISMATCH"),
        )))

    def test_rejects_single_engine_family(self):
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(families=1)))

    def test_rejects_already_usable(self):
        self.assertFalse(target.should_run_preselected_three_of_four_variant_rescue(ensemble(
            corroborated=4,
            reasons=(),
            status="DECLARED",
            declared_usable=True,
        )))


if __name__ == "__main__":
    unittest.main()
