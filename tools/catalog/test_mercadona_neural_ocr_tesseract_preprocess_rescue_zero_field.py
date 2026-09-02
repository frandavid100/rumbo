from __future__ import annotations

from dataclasses import dataclass
import unittest

from mercadona_neural_ocr_tesseract_preprocess_rescue_zero_field import (
    _should_run_zero_field_preprocess_rescue,
)


@dataclass
class FakeEnsemble:
    declared_usable: bool = False
    basis: str | None = "100_g"
    independent_engine_families: int = 2
    corroborated_fields: int = 0
    nutrition: dict | None = None
    reasons: tuple[str, ...] = ()

    def __post_init__(self):
        if self.nutrition is None:
            self.nutrition = {
                "calories": 200.0,
                "fat_g": 8.0,
                "carbohydrate_g": 20.0,
                "protein_g": 10.0,
            }


class ZeroFieldPreprocessRescuePolicyTests(unittest.TestCase):
    def test_accepts_safe_zero_field_shape(self):
        self.assertTrue(_should_run_zero_field_preprocess_rescue(FakeEnsemble()))

    def test_keeps_validated_one_two_and_three_field_shapes(self):
        for fields in (1, 2, 3):
            with self.subTest(fields=fields):
                self.assertTrue(
                    _should_run_zero_field_preprocess_rescue(
                        FakeEnsemble(corroborated_fields=fields)
                    )
                )

    def test_rejects_already_declared(self):
        self.assertFalse(
            _should_run_zero_field_preprocess_rescue(FakeEnsemble(declared_usable=True))
        )

    def test_rejects_missing_basis(self):
        self.assertFalse(_should_run_zero_field_preprocess_rescue(FakeEnsemble(basis=None)))

    def test_rejects_single_engine_family(self):
        self.assertFalse(
            _should_run_zero_field_preprocess_rescue(
                FakeEnsemble(independent_engine_families=1)
            )
        )

    def test_rejects_missing_core_value(self):
        ensemble = FakeEnsemble()
        del ensemble.nutrition["protein_g"]
        self.assertFalse(_should_run_zero_field_preprocess_rescue(ensemble))

    def test_rejects_hard_field_conflict(self):
        self.assertFalse(
            _should_run_zero_field_preprocess_rescue(
                FakeEnsemble(reasons=("OCR_FIELD_CONFLICT:protein_g",))
            )
        )

    def test_rejects_same_engine_conflict(self):
        self.assertFalse(
            _should_run_zero_field_preprocess_rescue(
                FakeEnsemble(reasons=("OCR_SAME_ENGINE_CONFLICT:protein_g:tesseract",))
            )
        )

    def test_rejects_basis_conflict(self):
        self.assertFalse(
            _should_run_zero_field_preprocess_rescue(
                FakeEnsemble(reasons=("OCR_BASIS_CONFLICT",))
            )
        )

    def test_rejects_energy_macro_mismatch(self):
        self.assertFalse(
            _should_run_zero_field_preprocess_rescue(
                FakeEnsemble(reasons=("ENERGY_MACRO_MISMATCH:12.0",))
            )
        )


if __name__ == "__main__":
    unittest.main()
