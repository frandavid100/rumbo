from __future__ import annotations

import unittest
from types import SimpleNamespace

from mercadona_bounded_doctr_rescue import (
    should_run_bounded_doctr_rescue,
    should_run_post_doctr_easyocr_rescue,
)
from nutrition_label_reader import LabelReadResult
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


def ensemble(
    *,
    status: str = "REVIEW",
    declared_usable: bool = False,
    basis: str = "100_g",
    nutrition: dict | None = None,
    families: int = 2,
    corroborated_fields: int = 0,
    reasons: list[str] | None = None,
):
    return SimpleNamespace(
        status=status,
        declared_usable=declared_usable,
        basis=basis,
        nutrition=nutrition,
        independent_engine_families=families,
        corroborated_fields=corroborated_fields,
        reasons=reasons or [],
    )


def partial(nutrition: dict[str, float]) -> LabelReadResult:
    missing = [
        field
        for field in ("calories", "fat_g", "carbohydrate_g", "protein_g")
        if field not in nutrition
    ]
    reasons = ("MISSING_CORE:" + ",".join(missing),) if missing else ()
    return LabelReadResult(
        "REVIEW" if missing else "DECLARED",
        "100_g",
        {key: float(value) for key, value in nutrition.items()},
        .95,
        reasons,
        "fixture",
    )


class BoundedDoctrRescueRoutingTest(unittest.TestCase):
    def test_routes_clean_incomplete_review_without_relaxing_acceptance(self) -> None:
        candidate = ensemble(
            nutrition={"calories": 220.0, "fat_g": 12.0, "carbohydrate_g": 18.0},
            families=2,
            reasons=["MISSING_PROTEIN"],
        )
        self.assertTrue(should_run_bounded_doctr_rescue(candidate))

    def test_requires_explicit_per_100_basis(self) -> None:
        candidate = ensemble(
            basis=None,
            nutrition={"calories": 220.0, "fat_g": 12.0, "carbohydrate_g": 18.0},
        )
        self.assertFalse(should_run_bounded_doctr_rescue(candidate))

    def test_requires_at_least_two_core_fields(self) -> None:
        candidate = ensemble(nutrition={"calories": 220.0})
        self.assertFalse(should_run_bounded_doctr_rescue(candidate))

    def test_refuses_hard_conflict(self) -> None:
        candidate = ensemble(
            nutrition={"calories": 220.0, "fat_g": 12.0, "carbohydrate_g": 18.0},
            reasons=["OCR_FIELD_CONFLICT:protein_g"],
        )
        self.assertFalse(should_run_bounded_doctr_rescue(candidate))

    def test_refuses_multiple_columns(self) -> None:
        candidate = ensemble(
            nutrition={"calories": 220.0, "fat_g": 12.0, "carbohydrate_g": 18.0},
            reasons=["MULTIPLE_NUTRITION_COLUMNS"],
        )
        self.assertFalse(should_run_bounded_doctr_rescue(candidate))

    def test_does_not_reroute_already_declared_observation(self) -> None:
        candidate = ensemble(
            status="DECLARED",
            declared_usable=True,
            nutrition={
                "calories": 220.0,
                "fat_g": 12.0,
                "carbohydrate_g": 18.0,
                "protein_g": 8.0,
            },
        )
        self.assertFalse(should_run_bounded_doctr_rescue(candidate))

    def test_routes_post_doctr_easyocr_only_for_clean_complete_three_of_four(self) -> None:
        candidate = ensemble(
            nutrition={
                "calories": 165.0,
                "fat_g": 10.0,
                "carbohydrate_g": 12.0,
                "protein_g": 5.9,
            },
            families=3,
            corroborated_fields=3,
            reasons=["UNCORROBORATED_CORE_FIELDS", "LOW_EXTRACTION_CONFIDENCE"],
        )
        self.assertTrue(should_run_post_doctr_easyocr_rescue(candidate))

    def test_post_doctr_easyocr_refuses_incomplete_or_hard_blocked_tuple(self) -> None:
        incomplete = ensemble(
            nutrition={"calories": 165.0, "fat_g": 10.0, "carbohydrate_g": 12.0},
            families=3,
            corroborated_fields=3,
            reasons=["UNCORROBORATED_CORE_FIELDS"],
        )
        blocked = ensemble(
            nutrition={
                "calories": 165.0,
                "fat_g": 10.0,
                "carbohydrate_g": 12.0,
                "protein_g": 5.9,
            },
            families=3,
            corroborated_fields=3,
            reasons=["UNCORROBORATED_CORE_FIELDS", "OCR_FIELD_CONFLICT:protein_g"],
        )
        self.assertFalse(should_run_post_doctr_easyocr_rescue(incomplete))
        self.assertFalse(should_run_post_doctr_easyocr_rescue(blocked))

    def test_easyocr_fourth_family_can_corroborate_only_missing_field_under_existing_contract(self) -> None:
        baseline = (
            ParsedOCRReading(
                "paddle",
                partial({"calories": 165, "fat_g": 10, "carbohydrate_g": 12}),
                .95,
                "paddleocr",
            ),
            ParsedOCRReading(
                "tesseract",
                partial({"calories": 165, "fat_g": 10, "carbohydrate_g": 12}),
                .95,
                "tesseract",
            ),
            ParsedOCRReading(
                "doctr",
                partial({"fat_g": 10, "carbohydrate_g": 12, "protein_g": 5.9}),
                .95,
                "doctr",
            ),
        )
        before = fuse_ocr_readings(baseline)
        self.assertEqual(before.status, "REVIEW")
        self.assertEqual(before.corroborated_fields, 3)
        self.assertEqual(before.independent_engine_families, 3)
        self.assertTrue(should_run_post_doctr_easyocr_rescue(before))

        after = fuse_ocr_readings((
            *baseline,
            ParsedOCRReading(
                "easyocr",
                partial({"protein_g": 5.9}),
                .95,
                "easyocr",
            ),
        ))
        self.assertTrue(after.declared_usable)
        self.assertEqual(after.corroborated_fields, 4)
        protein = next(field for field in after.fields if field.name == "protein_g")
        self.assertEqual(set(protein.engine_families), {"doctr", "easyocr"})


if __name__ == "__main__":
    unittest.main()
