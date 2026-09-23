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


class MercadonaTesseractCenterCropRescueTest(unittest.TestCase):
    def test_21649_exact_independent_complete_profiles_match(self):
        text = """Información nutricional por 100 g
Valor energético 1004 kJ / 240 kcal
Grasas 12 g
Hidratos de carbono 26 g
Proteínas 6.7 g
"""
        left = _parsed(text)
        right = _parsed(text)
        self.assertEqual(left.status, "DECLARED", left)
        self.assertTrue(_profiles_exactly_match(left, right))

    def test_conflicting_autocontrast_observation_cannot_be_cherry_picked(self):
        safe = _parsed("""Información nutricional por 100 g
Valor energético 1004 kJ / 240 kcal
Grasas 12 g
Hidratos de carbono 26 g
Proteínas 6.7 g
""")
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
        complete = _parsed("""Información nutricional por 100 g
Valor energético 1004 kJ / 240 kcal
Grasas 12 g
Hidratos de carbono 26 g
Proteínas 6.7 g
""")
        partial = _parsed("""Información nutricional por 100 g
Valor energético 1004 kJ / 240 kcal
Grasas 12 g
Hidratos de carbono 26 g
""")
        self.assertEqual(partial.status, "REVIEW", partial)
        self.assertFalse(_profiles_exactly_match(complete, partial))


if __name__ == "__main__":
    unittest.main()
