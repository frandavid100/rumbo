from __future__ import annotations

import unittest
from types import SimpleNamespace

from mercadona_bounded_doctr_rescue import should_run_bounded_doctr_rescue


def ensemble(
    *,
    status: str = "REVIEW",
    declared_usable: bool = False,
    basis: str = "100_g",
    nutrition: dict | None = None,
    families: int = 2,
    reasons: list[str] | None = None,
):
    return SimpleNamespace(
        status=status,
        declared_usable=declared_usable,
        basis=basis,
        nutrition=nutrition,
        independent_engine_families=families,
        reasons=reasons or [],
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


if __name__ == "__main__":
    unittest.main()
