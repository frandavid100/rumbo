from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from mercadona_neural_ocr_tesseract_preprocess_rescue import (
    MAX_PREPROCESS_SIDE,
    TESSERACT_TIMEOUT_SECONDS,
    _bounded_tesseract_runner,
    _preprocess_variants,
    _should_run_preprocess_rescue,
)


@dataclass
class FakeEnsemble:
    declared_usable: bool = False
    basis: str | None = "100_g"
    independent_engine_families: int = 2
    corroborated_fields: int = 3
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


class PreprocessRescuePolicyTests(unittest.TestCase):
    def test_accepts_one_field_short_safe_shape(self):
        self.assertTrue(_should_run_preprocess_rescue(FakeEnsemble()))

    def test_rejects_already_declared(self):
        self.assertFalse(_should_run_preprocess_rescue(FakeEnsemble(declared_usable=True)))

    def test_rejects_missing_basis(self):
        self.assertFalse(_should_run_preprocess_rescue(FakeEnsemble(basis=None)))

    def test_rejects_single_engine_family(self):
        self.assertFalse(_should_run_preprocess_rescue(FakeEnsemble(independent_engine_families=1)))

    def test_rejects_more_than_one_field_short(self):
        self.assertFalse(_should_run_preprocess_rescue(FakeEnsemble(corroborated_fields=2)))

    def test_rejects_missing_core_value(self):
        ensemble = FakeEnsemble()
        del ensemble.nutrition["protein_g"]
        self.assertFalse(_should_run_preprocess_rescue(ensemble))

    def test_rejects_hard_field_conflict(self):
        self.assertFalse(
            _should_run_preprocess_rescue(
                FakeEnsemble(reasons=("OCR_FIELD_CONFLICT:protein_g",))
            )
        )

    def test_rejects_same_engine_conflict(self):
        self.assertFalse(
            _should_run_preprocess_rescue(
                FakeEnsemble(reasons=("OCR_SAME_ENGINE_CONFLICT:protein_g:tesseract",))
            )
        )

    def test_rejects_basis_conflict(self):
        self.assertFalse(
            _should_run_preprocess_rescue(FakeEnsemble(reasons=("OCR_BASIS_CONFLICT",)))
        )

    def test_rejects_energy_macro_mismatch(self):
        self.assertFalse(
            _should_run_preprocess_rescue(
                FakeEnsemble(reasons=("ENERGY_MACRO_MISMATCH:12.0",))
            )
        )

    def test_preprocess_variants_never_exceed_runtime_side_cap(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "large.png"
            image = np.full((2200, 3000), 255, dtype=np.uint8)
            self.assertTrue(cv2.imwrite(str(source), image))
            variants = _preprocess_variants(source, root / "variants")
            self.assertEqual({name for name, _path in variants}, {"clahe", "otsu", "adaptive"})
            for _name, path in variants:
                loaded = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                self.assertIsNotNone(loaded)
                self.assertLessEqual(max(loaded.shape[:2]), MAX_PREPROCESS_SIDE)

    @patch("mercadona_neural_ocr_tesseract_preprocess_rescue.subprocess.run")
    def test_tesseract_subprocess_has_hard_timeout(self, run):
        run.return_value = SimpleNamespace(stdout="ok", stderr="")
        stdout, stderr = _bounded_tesseract_runner(["tesseract", "x"], "x")
        self.assertEqual((stdout, stderr), ("ok", ""))
        self.assertEqual(run.call_args.kwargs["timeout"], TESSERACT_TIMEOUT_SECONDS)
        self.assertGreater(TESSERACT_TIMEOUT_SECONDS, 0)


if __name__ == "__main__":
    unittest.main()
