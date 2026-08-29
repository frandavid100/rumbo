from __future__ import annotations

from types import SimpleNamespace
import unittest

from mercadona_neural_ocr_wave_rescue import _should_run_easyocr


def ensemble(*, declared=False, families=2, fields=3, reasons=()):
    nutrition = {f"field_{i}": float(i) for i in range(fields)} if fields else None
    return SimpleNamespace(
        declared_usable=declared,
        independent_engine_families=families,
        nutrition=nutrition,
        reasons=tuple(reasons),
    )


def reading(status: str):
    return ("strategy", "family", SimpleNamespace(parsed=SimpleNamespace(status=status)))


class RescuePolicyTest(unittest.TestCase):
    def test_preserves_original_declared_reading_rescue(self):
        self.assertTrue(_should_run_easyocr(ensemble(families=1, fields=1), [reading("DECLARED")]))

    def test_rescues_three_nonconflicting_fields_from_two_families(self):
        self.assertTrue(_should_run_easyocr(ensemble(families=2, fields=3), [reading("REVIEW")]))

    def test_rescues_four_nonconflicting_fields_from_two_families(self):
        self.assertTrue(_should_run_easyocr(ensemble(families=2, fields=4), [reading("REVIEW")]))

    def test_does_not_run_after_ensemble_is_already_declared(self):
        self.assertFalse(_should_run_easyocr(ensemble(declared=True, families=2, fields=4), [reading("DECLARED")]))

    def test_does_not_rescue_only_two_fields(self):
        self.assertFalse(_should_run_easyocr(ensemble(families=2, fields=2), [reading("REVIEW")]))

    def test_does_not_rescue_single_family_partial(self):
        self.assertFalse(_should_run_easyocr(ensemble(families=1, fields=4), [reading("REVIEW")]))

    def test_does_not_rescue_cross_engine_field_conflict(self):
        self.assertFalse(_should_run_easyocr(
            ensemble(families=2, fields=3, reasons=("OCR_FIELD_CONFLICT:protein_g",)),
            [reading("REVIEW")],
        ))

    def test_does_not_rescue_same_engine_conflict(self):
        self.assertFalse(_should_run_easyocr(
            ensemble(families=2, fields=3, reasons=("OCR_SAME_ENGINE_CONFLICT:fat_g:tesseract",)),
            [reading("REVIEW")],
        ))

    def test_does_not_rescue_basis_conflict(self):
        self.assertFalse(_should_run_easyocr(
            ensemble(families=2, fields=3, reasons=("OCR_BASIS_CONFLICT",)),
            [reading("REVIEW")],
        ))


if __name__ == "__main__":
    unittest.main()
