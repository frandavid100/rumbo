from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import mercadona_ambiguous_primary_column_rescue as rescue


CORE_VALUES = {
    "calories": 545.0,
    "fat_g": 33.0,
    "carbohydrate_g": 54.0,
    "protein_g": 8.29,
}


def diagnostic(**overrides):
    row = {
        "canonical_status": "REVIEW",
        "corroborated_fields": 3,
        "independent_engine_families": 3,
        "basis": "100_g",
        "diagnostic_candidate_values": dict(CORE_VALUES),
        "safety_blockers": ["AMBIGUOUS_TABLE"],
        "reason_prefixes": ["MULTIPLE_NUTRITION_COLUMNS", "UNCORROBORATED_CORE_FIELDS"],
        "product_id": "82199",
        "ean": "8423102920106",
        "image_url": "https://prod-mercadona.imgix.net/example.jpg",
    }
    row.update(overrides)
    return row


class AmbiguousPrimaryColumnTargetSelectionTest(unittest.TestCase):
    def test_selects_only_complete_three_of_four_ambiguity_only_rows(self) -> None:
        rows = [
            diagnostic(product_id="82199"),
            diagnostic(product_id="21713", basis="100_ml"),
        ]
        selected = rescue.select_ambiguous_primary_column_targets(rows)
        self.assertEqual([row["product_id"] for row in selected], ["21713", "82199"])

    def test_rejects_other_safety_blockers(self) -> None:
        rows = [
            diagnostic(safety_blockers=["AMBIGUOUS_TABLE", "ENERGY_MACRO_INCOHERENCE"]),
            diagnostic(safety_blockers=["ENERGY_MACRO_INCOHERENCE"]),
            diagnostic(reason_prefixes=["ENERGY_MACRO_MISMATCH"]),
        ]
        self.assertEqual(rescue.select_ambiguous_primary_column_targets(rows), [])

    def test_requires_exact_identity_image_and_complete_candidate(self) -> None:
        incomplete = dict(CORE_VALUES)
        incomplete.pop("protein_g")
        rows = [
            diagnostic(ean=""),
            diagnostic(image_url=""),
            diagnostic(diagnostic_candidate_values=incomplete),
            diagnostic(corroborated_fields=2),
            diagnostic(independent_engine_families=2),
        ]
        self.assertEqual(rescue.select_ambiguous_primary_column_targets(rows), [])


class IndependentPrimaryColumnObservationTest(unittest.TestCase):
    def test_declared_crop_replaces_ambiguous_baseline_without_cross_fusion(self) -> None:
        baseline = SimpleNamespace(declared_usable=False)
        review_crop = SimpleNamespace(declared_usable=False)
        declared_crop = SimpleNamespace(declared_usable=True)
        baseline_readings = [("whole", "paddleocr", object())]
        first_crop_readings = [("paddleocr", "paddleocr", object())]
        second_crop_readings = [
            ("paddleocr", "paddleocr", object()),
            ("tesseract-psm6", "tesseract", object()),
        ]
        variants = [
            SimpleNamespace(name="primary_left_42", path=Path("left42.jpg")),
            SimpleNamespace(name="primary_left_50", path=Path("left50.jpg")),
        ]
        bounded = SimpleNamespace(
            _extract_region_with_post_doctr_easyocr=Mock(
                return_value=(baseline_readings, {"whole": "blocked"}, baseline)
            ),
            build_bounded_primary_column_variants=Mock(return_value=variants),
            _DOCTR_EXTRACT_REGION=Mock(side_effect=[
                (first_crop_readings, {"first": "review"}, review_crop),
                (second_crop_readings, {}, declared_crop),
            ]),
        )

        with patch.object(rescue, "_bounded_module", return_value=bounded):
            readings, errors, ensemble = rescue._extract_region(
                object(), Path("region.jpg"), "visual_region"
            )

        self.assertIs(ensemble, declared_crop)
        self.assertEqual(
            [strategy for strategy, _family, _reading in readings],
            ["primary_left_50/paddleocr", "primary_left_50/tesseract-psm6"],
        )
        self.assertNotIn("whole", [strategy for strategy, _family, _reading in readings])
        self.assertEqual(errors, {})

    def test_failed_crops_leave_original_ambiguous_observation_unchanged(self) -> None:
        baseline = SimpleNamespace(declared_usable=False)
        review_crop = SimpleNamespace(declared_usable=False)
        baseline_readings = [("whole", "paddleocr", object())]
        baseline_errors = {"whole": "ambiguous"}
        variants = [SimpleNamespace(name="primary_left_42", path=Path("left42.jpg"))]
        bounded = SimpleNamespace(
            _extract_region_with_post_doctr_easyocr=Mock(
                return_value=(baseline_readings, baseline_errors, baseline)
            ),
            build_bounded_primary_column_variants=Mock(return_value=variants),
            _DOCTR_EXTRACT_REGION=Mock(
                return_value=([("paddleocr", "paddleocr", object())], {}, review_crop)
            ),
        )

        with patch.object(rescue, "_bounded_module", return_value=bounded):
            readings, errors, ensemble = rescue._extract_region(
                object(), Path("region.jpg"), "visual_region"
            )

        self.assertIs(ensemble, baseline)
        self.assertEqual(readings, baseline_readings)
        self.assertEqual(errors, baseline_errors)


if __name__ == "__main__":
    unittest.main()
