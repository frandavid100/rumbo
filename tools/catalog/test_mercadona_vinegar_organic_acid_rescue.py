from __future__ import annotations

from types import SimpleNamespace
import unittest

from nutrition_label_reader import read_nutrition_label
from nutrition_ocr_ensemble import OCREnsembleResult
from mercadona_vinegar_organic_acid_rescue import promote_explicit_vinegar_acidity


VALUES = {
    "calories": 20.0,
    "fat_g": 0.0,
    "carbohydrate_g": 0.0,
    "protein_g": 0.0,
}


def review(*, reasons=("ENERGY_MACRO_MISMATCH:0.0",), basis="100_ml"):
    return OCREnsembleResult(
        status="REVIEW",
        basis=basis,
        nutrition=dict(VALUES),
        confidence=.87,
        fields=tuple(),
        corroborated_fields=4,
        independent_engine_families=3,
        reasons=tuple(reasons),
    )


def reading(family: str, text: str):
    parsed = SimpleNamespace(normalized_text=text)
    return (f"{family}-fixture", family, SimpleNamespace(parsed=parsed))


GOOD_TEXT = """VINAGRE DE VINO BLANCO
100 ml
Acidez: 6%
Valor
85 kJ
Energético/Energia
20 kcal
Grasas/Lípidos
0 g
Hidratos de Carbono
0 g
Proteínas
0 g
"""


class MercadonaVinegarOrganicAcidRescueTest(unittest.TestCase):
    def test_promotes_only_when_explicit_vinegar_acidity_accounts_for_energy(self) -> None:
        candidate = promote_explicit_vinegar_acidity(
            review(),
            [reading("paddleocr", GOOD_TEXT), reading("doctr", GOOD_TEXT)],
        )
        self.assertEqual(candidate.status, "DECLARED", candidate)
        self.assertTrue(candidate.declared_usable)
        self.assertEqual(candidate.nutrition, VALUES)
        self.assertTrue(any(
            reason.startswith("EXPLICIT_VINEGAR_ACIDITY_ENERGY_COHERENCE")
            for reason in candidate.reasons
        ))

    def test_requires_two_independent_ocr_families_for_acidity_and_energy_pair(self) -> None:
        candidate = promote_explicit_vinegar_acidity(
            review(),
            [reading("paddleocr", GOOD_TEXT)],
        )
        self.assertEqual(candidate.status, "REVIEW")

    def test_does_not_promote_when_acidity_cannot_explain_declared_energy(self) -> None:
        bad = GOOD_TEXT.replace("Acidez: 6%", "Acidez: 2%")
        candidate = promote_explicit_vinegar_acidity(
            review(),
            [reading("paddleocr", bad), reading("doctr", bad)],
        )
        self.assertEqual(candidate.status, "REVIEW")

    def test_does_not_override_any_non_energy_safety_blocker(self) -> None:
        candidate = promote_explicit_vinegar_acidity(
            review(reasons=("ENERGY_MACRO_MISMATCH:0.0", "OCR_FIELD_CONFLICT:calories")),
            [reading("paddleocr", GOOD_TEXT), reading("doctr", GOOD_TEXT)],
        )
        self.assertEqual(candidate.status, "REVIEW")

    def test_generic_parser_remains_conservative_without_explicit_noncore_energy_evidence(self) -> None:
        label = """INFORMACIÓN NUTRICIONAL
Por 100 ml
Valor energético 85 kJ / 20 kcal
Grasas 0 g
Hidratos de Carbono 0 g
Proteínas 0 g
Sal 0.05 g
"""
        parsed = read_nutrition_label(label, extraction_confidence=.99)
        self.assertEqual(parsed.status, "REVIEW")
        self.assertTrue(any(reason.startswith("ENERGY_MACRO_MISMATCH") for reason in parsed.reasons))


if __name__ == "__main__":
    unittest.main()
