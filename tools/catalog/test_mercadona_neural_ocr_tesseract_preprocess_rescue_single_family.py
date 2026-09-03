from __future__ import annotations

from types import SimpleNamespace
import unittest

from mercadona_neural_ocr_tesseract_preprocess_rescue_single_family import (
    _should_run_single_family_preprocess_rescue,
)


CORE = {"calories": 100.0, "fat_g": 3.0, "carbohydrate_g": 12.0, "protein_g": 5.0}


def ensemble(*, declared=False, basis="100_g", families=1, corroborated=0, nutrition=None, reasons=()):
    return SimpleNamespace(
        declared_usable=declared,
        basis=basis,
        independent_engine_families=families,
        corroborated_fields=corroborated,
        nutrition=dict(CORE if nutrition is None else nutrition),
        reasons=tuple(reasons),
    )


class SingleFamilyPreprocessTriggerTests(unittest.TestCase):
    def test_safe_single_family_complete_tuple_runs(self):
        self.assertTrue(_should_run_single_family_preprocess_rescue(ensemble()))

    def test_already_declared_does_not_run(self):
        self.assertFalse(_should_run_single_family_preprocess_rescue(ensemble(declared=True)))

    def test_two_families_does_not_run(self):
        self.assertFalse(_should_run_single_family_preprocess_rescue(ensemble(families=2)))

    def test_existing_corroboration_does_not_run(self):
        self.assertFalse(_should_run_single_family_preprocess_rescue(ensemble(corroborated=1)))

    def test_missing_core_does_not_run(self):
        nutrition = dict(CORE)
        nutrition.pop("protein_g")
        self.assertFalse(_should_run_single_family_preprocess_rescue(ensemble(nutrition=nutrition)))

    def test_non_explicit_basis_does_not_run(self):
        self.assertFalse(_should_run_single_family_preprocess_rescue(ensemble(basis=None)))

    def test_hard_conflict_does_not_run(self):
        self.assertFalse(
            _should_run_single_family_preprocess_rescue(
                ensemble(reasons=("OCR_FIELD_CONFLICT:fat_g",))
            )
        )

    def test_energy_mismatch_does_not_run(self):
        self.assertFalse(
            _should_run_single_family_preprocess_rescue(
                ensemble(reasons=("ENERGY_MACRO_MISMATCH:declared=100",))
            )
        )


if __name__ == "__main__":
    unittest.main()
