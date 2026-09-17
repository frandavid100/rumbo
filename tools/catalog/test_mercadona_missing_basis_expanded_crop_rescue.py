from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from PIL import Image

import mercadona_missing_basis_expanded_crop_rescue as rescue


CORE_VALUES = {
    "calories": 151.0,
    "fat_g": 5.8,
    "carbohydrate_g": 23.0,
    "protein_g": 2.3,
}


def diagnostic(**overrides):
    row = {
        "canonical_status": "REVIEW",
        "corroborated_fields": 3,
        "independent_engine_families": 2,
        "basis": None,
        "diagnostic_candidate_values": dict(CORE_VALUES),
        "safety_blockers": ["ENERGY_MACRO_INCOHERENCE"],
        "reason_prefixes": ["MISSING_100G_100ML_BASIS", "UNCORROBORATED_CORE_FIELDS"],
        "product_id": "7879",
        "ean": "8480000078791",
        "image_url": "https://prod-mercadona.imgix.net/example.jpg",
    }
    row.update(overrides)
    return row


class MissingBasisTargetSelectionTest(unittest.TestCase):
    def test_selects_complete_three_of_four_missing_basis_review(self) -> None:
        selected = rescue.select_missing_basis_targets([diagnostic()])
        self.assertEqual([row["product_id"] for row in selected], ["7879"])

    def test_rejects_rows_that_do_not_need_explicit_basis_recovery(self) -> None:
        rows = [
            diagnostic(basis="100_g"),
            diagnostic(reason_prefixes=["UNCORROBORATED_CORE_FIELDS"]),
            diagnostic(corroborated_fields=2),
            diagnostic(independent_engine_families=1),
        ]
        self.assertEqual(rescue.select_missing_basis_targets(rows), [])

    def test_requires_complete_diagnostic_tuple_and_identity_anchors(self) -> None:
        incomplete = dict(CORE_VALUES)
        incomplete.pop("fat_g")
        rows = [
            diagnostic(diagnostic_candidate_values=incomplete),
            diagnostic(ean=""),
            diagnostic(image_url=""),
        ]
        self.assertEqual(rescue.select_missing_basis_targets(rows), [])


class ExpandedCropGeometryTest(unittest.TestCase):
    def test_expands_upward_and_clips_to_image_bounds(self) -> None:
        box = rescue.expanded_box((20, 30, 90, 80), (100, 100), top_ratio=0.80)
        self.assertEqual(box, (14, 0, 96, 83))

    def test_each_expansion_is_a_separate_ocr_target(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "label.jpg"
            Image.new("RGB", (200, 200), "white").save(image_path)
            region = SimpleNamespace(
                name="region-00",
                box=(40, 70, 160, 150),
                score=0.9,
                horizontal_lines=4,
                vertical_lines=2,
                line_density=0.2,
            )
            targets = rescue.expanded_basis_ocr_targets(image_path, [region])

            self.assertEqual(len(targets), len(rescue.TOP_EXPANSION_RATIOS))
            self.assertTrue(all(kind.startswith("expanded_visual_region_top_") for kind, _path, _meta in targets))
            self.assertTrue(all(path.is_file() for _kind, path, _meta in targets))
            boxes = [meta.box for _kind, _path, meta in targets]
            self.assertEqual(len(set(boxes)), len(boxes))
            self.assertTrue(all(box[1] < region.box[1] for box in boxes))


class MissingBasisDoctrRoutingTest(unittest.TestCase):
    def ensemble(self, **overrides):
        data = {
            "status": "REVIEW",
            "declared_usable": False,
            "basis": None,
            "nutrition": dict(CORE_VALUES),
            "independent_engine_families": 2,
            "reasons": ("MISSING_100G_100ML_BASIS", "UNCORROBORATED_CORE_FIELDS"),
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    def test_routes_complete_missing_basis_observation_to_doctr(self) -> None:
        self.assertTrue(rescue.should_run_missing_basis_doctr_rescue(self.ensemble()))

    def test_does_not_route_missing_basis_rescue_without_three_core_fields(self) -> None:
        nutrition = {"calories": 151.0, "fat_g": 5.8}
        self.assertFalse(
            rescue.should_run_missing_basis_doctr_rescue(self.ensemble(nutrition=nutrition))
        )

    def test_does_not_treat_basis_recovery_as_acceptance(self) -> None:
        self.assertFalse(
            rescue.should_run_missing_basis_doctr_rescue(
                self.ensemble(status="DECLARED", declared_usable=True, basis="100_g")
            )
        )


if __name__ == "__main__":
    unittest.main()
