import unittest
from types import SimpleNamespace

from mercadona_easyocr_reversal_diagnostic import (
    _corroborates_single_reversal_candidate,
    _is_single_reversal_candidate,
)


def parsed(*, status, basis="100_g", nutrition=None, reasons=()):
    return SimpleNamespace(
        status=status,
        basis=basis,
        nutrition=nutrition,
        reasons=tuple(reasons),
    )


PROFILE = {
    "calories": 266.0,
    "fat_g": 19.0,
    "carbohydrate_g": 18.6,
    "protein_g": 5.1,
}


class MercadonaEasyOCRReversalDiagnosticTest(unittest.TestCase):
    def test_routes_exact_single_reversal_candidate_shape(self):
        paddle = parsed(
            status="REVIEW",
            nutrition=PROFILE,
            reasons=("SINGLE_REVERSED_MACRO_CANDIDATE:protein_g",),
        )
        self.assertTrue(_is_single_reversal_candidate(paddle))

    def test_exact_independent_declared_match_is_diagnostic_corroboration(self):
        paddle = parsed(
            status="REVIEW",
            nutrition=PROFILE,
            reasons=("SINGLE_REVERSED_MACRO_CANDIDATE:protein_g",),
        )
        easy = parsed(status="DECLARED", nutrition=PROFILE)
        self.assertTrue(_corroborates_single_reversal_candidate(paddle, easy))

    def test_extra_blocker_is_not_eligible(self):
        paddle = parsed(
            status="REVIEW",
            nutrition=PROFILE,
            reasons=(
                "SINGLE_REVERSED_MACRO_CANDIDATE:protein_g",
                "MULTI_COLUMN_TABLE_AMBIGUOUS",
            ),
        )
        easy = parsed(status="DECLARED", nutrition=PROFILE)
        self.assertFalse(_is_single_reversal_candidate(paddle))
        self.assertFalse(_corroborates_single_reversal_candidate(paddle, easy))

    def test_incomplete_or_bounded_profile_is_not_eligible(self):
        incomplete = dict(PROFILE)
        incomplete.pop("protein_g")
        paddle = parsed(
            status="REVIEW",
            nutrition=incomplete,
            reasons=("SINGLE_REVERSED_MACRO_CANDIDATE:protein_g",),
        )
        easy = parsed(status="DECLARED", nutrition=PROFILE)
        self.assertFalse(_corroborates_single_reversal_candidate(paddle, easy))

    def test_basis_or_value_disagreement_is_not_corroboration(self):
        paddle = parsed(
            status="REVIEW",
            nutrition=PROFILE,
            reasons=("SINGLE_REVERSED_MACRO_CANDIDATE:protein_g",),
        )
        wrong_basis = parsed(status="DECLARED", basis="100_ml", nutrition=PROFILE)
        self.assertFalse(_corroborates_single_reversal_candidate(paddle, wrong_basis))

        different = dict(PROFILE)
        different["protein_g"] = 1.5
        easy = parsed(status="DECLARED", nutrition=different)
        self.assertFalse(_corroborates_single_reversal_candidate(paddle, easy))

    def test_review_easyocr_never_counts_as_corroboration(self):
        paddle = parsed(
            status="REVIEW",
            nutrition=PROFILE,
            reasons=("SINGLE_REVERSED_MACRO_CANDIDATE:protein_g",),
        )
        easy = parsed(status="REVIEW", nutrition=PROFILE, reasons=("MISSING_CORE:protein_g",))
        self.assertFalse(_corroborates_single_reversal_candidate(paddle, easy))


if __name__ == "__main__":
    unittest.main()
