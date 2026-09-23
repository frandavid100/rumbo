import unittest

from mercadona_tesseract_center_crop_rescue import _profiles_exactly_match
from mercadona_nutrition_reader import VisionExtraction, read_evidence
from mercadona_label_evidence import LabelImageEvidence


EVIDENCE = LabelImageEvidence(
    retailer="Mercadona",
    retailer_sku="21649",
    product_name="Empanada de carne",
    image_url="https://example.invalid/p9.jpg",
    image_index=0,
    observed_at="2026-09-23T00:00:00Z",
    source_page=None,
    redistribution_allowed=False,
    purpose="PACK_LABEL_CANDIDATE",
    perspective=9,
)


def _parsed(text: str):
    return read_evidence(EVIDENCE, VisionExtraction(
        text=text,
        confidence=.95,
        engine="fixture",
        engine_version="test",
    )).parsed


CLEAN = """Información nutricional por 100 g
Valor energético 1004 kJ / 240 kcal
Grasas 12 g
Hidratos de carbono 26 g
Proteínas 6.7 g
"""

REVERSED_PROTEIN = """Información nutricional por 100 g
Valor energético 1004 kJ / 240 kcal
Grasas 12 g
Hidratos de carbono 26 g
6.7 g
Proteínas
Sal 1.1 g
"""


class MercadonaTesseractCenterCropRescueTest(unittest.TestCase):
    def test_21649_exact_independent_complete_profiles_match(self):
        left = _parsed(CLEAN)
        right = _parsed(CLEAN)
        self.assertEqual(left.status, "DECLARED", left)
        self.assertTrue(_profiles_exactly_match(left, right))

    def test_single_reversed_review_can_be_corroborated_by_clean_declared_peer(self):
        reviewed = _parsed(REVERSED_PROTEIN)
        declared = _parsed(CLEAN)
        self.assertEqual(reviewed.status, "REVIEW", reviewed)
        self.assertEqual(reviewed.reasons, ("SINGLE_REVERSED_MACRO_CANDIDATE:protein_g",), reviewed)
        self.assertEqual(declared.status, "DECLARED", declared)
        self.assertTrue(_profiles_exactly_match(reviewed, declared))
        self.assertTrue(_profiles_exactly_match(declared, reviewed))

    def test_two_single_reversed_reviews_do_not_self_corroborate(self):
        left = _parsed(REVERSED_PROTEIN)
        right = _parsed(REVERSED_PROTEIN)
        self.assertEqual(left.status, "REVIEW", left)
        self.assertEqual(right.status, "REVIEW", right)
        self.assertFalse(_profiles_exactly_match(left, right))

    def test_conflicting_autocontrast_observation_cannot_be_cherry_picked(self):
        safe = _parsed(CLEAN)
        conflicting = _parsed("""Información nutricional por 100 g
Valor energético 1004 kJ / 240 kcal
Grasas 12 g
Hidratos de carbono 26 g
Proteínas 6.79 g
""")
        self.assertEqual(safe.status, "DECLARED", safe)
        self.assertEqual(conflicting.status, "DECLARED", conflicting)
        self.assertFalse(_profiles_exactly_match(safe, conflicting))

    def test_partial_profile_never_matches_complete_profile(self):
        complete = _parsed(CLEAN)
        partial = _parsed("""Información nutricional por 100 g
Valor energético 1004 kJ / 240 kcal
Grasas 12 g
Hidratos de carbono 26 g
""")
        self.assertEqual(partial.status, "REVIEW", partial)
        self.assertFalse(_profiles_exactly_match(complete, partial))

    def test_missing_basis_review_is_not_corroboratable(self):
        no_basis = _parsed("""Información nutricional
Valor energético 1004 kJ / 240 kcal
Grasas 12 g
Hidratos de carbono 26 g
6.7 g
Proteínas
Sal 1.1 g
""")
        declared = _parsed(CLEAN)
        self.assertEqual(no_basis.status, "REVIEW", no_basis)
        self.assertFalse(_profiles_exactly_match(no_basis, declared))


if __name__ == "__main__":
    unittest.main()
