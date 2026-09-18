from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from PIL import Image

from mercadona_safety_blocked_ocr_expansion import (
    build_scaled_variants,
    should_expand_safety_blocked_review,
)
from nutrition_label_reader import read_nutrition_label


def ensemble(*, status="REVIEW", declared_usable=False, basis="100_g", reasons=None):
    return SimpleNamespace(
        status=status,
        declared_usable=declared_usable,
        basis=basis,
        reasons=reasons or [],
    )


class SafetyBlockedOCRExpansionTest(unittest.TestCase):
    def test_routes_explicit_hard_block_without_relaxing_acceptance(self) -> None:
        candidate = ensemble(reasons=["MULTIPLE_NUTRITION_COLUMNS", "ENERGY_MACRO_MISMATCH:611.0"])
        self.assertTrue(should_expand_safety_blocked_review(candidate))

    def test_routes_complete_under_corroborated_review(self) -> None:
        candidate = ensemble(reasons=["UNCORROBORATED_CORE_FIELDS", "LOW_EXTRACTION_CONFIDENCE"])
        self.assertTrue(should_expand_safety_blocked_review(candidate))

    def test_does_not_route_declared_or_missing_basis(self) -> None:
        self.assertFalse(should_expand_safety_blocked_review(
            ensemble(status="DECLARED", declared_usable=True, reasons=["LOW_EXTRACTION_CONFIDENCE"])
        ))
        self.assertFalse(should_expand_safety_blocked_review(
            ensemble(basis=None, reasons=["MULTIPLE_NUTRITION_COLUMNS"])
        ))

    def test_scaled_variants_are_deterministic_two_x_views(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.jpg"
            Image.new("RGB", (200, 120), "white").save(source)
            variants = build_scaled_variants(source, Path(td) / "out")
            self.assertEqual(
                [variant.name for variant in variants],
                [
                    "scaled_full_autocontrast",
                    "scaled_crop_center",
                    "scaled_crop_left",
                    "scaled_crop_top",
                    "scaled_crop_bottom",
                ],
            )
            for variant in variants:
                self.assertTrue(variant.path.is_file())
                with Image.open(variant.path) as image:
                    self.assertGreaterEqual(image.width, 2)
                    self.assertGreaterEqual(image.height, 2)

    def test_energy_macro_incoherence_still_cannot_be_declared(self) -> None:
        label = """INFORMACIÓN NUTRICIONAL\nPor 100 ml\nValor energético 85 kJ / 20 kcal\nGrasas 0 g\nHidratos de Carbono 0 g\nProteínas 0 g\nSal 0.05 g\n"""
        parsed = read_nutrition_label(label, extraction_confidence=.99)
        self.assertEqual(parsed.status, "REVIEW")
        self.assertFalse(parsed.declared_usable)
        self.assertTrue(any(reason.startswith("ENERGY_MACRO_MISMATCH") for reason in parsed.reasons))


if __name__ == "__main__":
    unittest.main()
