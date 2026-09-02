from __future__ import annotations

from dataclasses import dataclass
import unittest

from mercadona_neural_ocr_tesseract_preprocess_rescue_missing_one_core import (
    _should_run_missing_one_core_preprocess_rescue,
)


@dataclass
class FakeEnsemble:
    declared_usable: bool = False
    basis: str | None = "100_g"
    independent_engine_families: int = 2
    corroborated_fields: int = 2
    nutrition: dict | None = None
    reasons: tuple[str, ...] = ()

    def __post_init__(self):
        if self.nutrition is None:
            self.nutrition = {
                "calories": 200.0,
                "carbohydrate_g": 20.0,
                "protein_g": 10.0,
            }


class MissingOneCorePreprocessRescuePolicyTests(unittest.TestCase):
    def test_accepts_exactly_three_core_values(self):
        self.assertTrue(_should_run_missing_one_core_preprocess_rescue(FakeEnsemble()))

    def test_preserves_original_full_core_three_corroborated_trigger(self):
        ensemble = FakeEnsemble(corroborated_fields=3)
        ensemble.nutrition["fat_g"] = 8.0
        self.assertTrue(_should_run_missing_one_core_preprocess_rescue(ensemble))

    def test_rejects_full_core_with_only_two_corroborated(self):
        ensemble = FakeEnsemble(corroborated_fields=2)
        ensemble.nutrition["fat_g"] = 8.0
        self.assertFalse(_should_run_missing_one_core_preprocess_rescue(ensemble))

    def test_rejects_two_core_values(self):
        ensemble = FakeEnsemble()
        del ensemble.nutrition["protein_g"]
        self.assertFalse(_should_run_missing_one_core_preprocess_rescue(ensemble))

    def test_rejects_already_declared(self):
        self.assertFalse(
            _should_run_missing_one_core_preprocess_rescue(FakeEnsemble(declared_usable=True))
        )

    def test_rejects_missing_basis(self):
        self.assertFalse(_should_run_missing_one_core_preprocess_rescue(FakeEnsemble(basis=None)))

    def test_rejects_single_engine_family(self):
        self.assertFalse(
            _should_run_missing_one_core_preprocess_rescue(
                FakeEnsemble(independent_engine_families=1)
            )
        )

    def test_rejects_hard_conflict(self):
        self.assertFalse(
            _should_run_missing_one_core_preprocess_rescue(
                FakeEnsemble(reasons=("OCR_FIELD_CONFLICT:fat_g",))
            )
        )

    def test_rejects_energy_macro_mismatch(self):
        self.assertFalse(
            _should_run_missing_one_core_preprocess_rescue(
                FakeEnsemble(reasons=("ENERGY_MACRO_MISMATCH:20",))
            )
        )


if __name__ == "__main__":
    unittest.main()
