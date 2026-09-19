from __future__ import annotations

import unittest

from nutrition_label_reader import LabelReadResult
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


class SingleDigitEnergyEnsembleTest(unittest.TestCase):
    @staticmethod
    def reading(strategy: str, text: str) -> ParsedOCRReading:
        # Mirrors current Mercadona REVIEW rows such as product 60671: the
        # conservative label parser intentionally withholds a one-digit kcal
        # token, while the other three core macros are read exactly.
        parsed = LabelReadResult(
            status="REVIEW",
            basis="100_ml",
            nutrition={"fat_g": 0.0, "carbohydrate_g": 0.0, "protein_g": 0.0},
            confidence=.94,
            reasons=("MISSING_CORE:calories",),
            normalized_text=text,
        )
        return ParsedOCRReading(strategy, parsed, engine_family=strategy)

    def test_two_independent_families_can_rescue_one_anchored_single_digit_kcal(self) -> None:
        text = """100 ml
Valor
10 kJ
Energético/Energía
3 kcal
Grasas 0 g
Hidratos de Carbono 0 g
Proteínas 0 g
"""
        result = fuse_ocr_readings([
            self.reading("easyocr", text),
            self.reading("paddleocr", text),
        ])

        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.basis, "100_ml")
        self.assertEqual(result.nutrition, {
            "calories": 3.0,
            "fat_g": 0.0,
            "carbohydrate_g": 0.0,
            "protein_g": 0.0,
        })
        self.assertEqual(result.corroborated_fields, 4)

    def test_parallel_single_digit_energy_values_remain_ambiguous(self) -> None:
        # Current Mercadona REVIEW products 27487/27488 expose two energy
        # columns on one OCR row (2 kcal and 6 kcal). The rescue must never pick
        # one merely because both values are one digit.
        text = """100 ml
Energía / Valor energético 7 kJ (2 kcal) 24 kJ (6 kcal)
Grasas 0 g
Hidratos de Carbono 0 g
Proteínas 0 g
"""
        result = fuse_ocr_readings([
            self.reading("easyocr", text),
            self.reading("paddleocr", text),
        ])

        self.assertEqual(result.status, "REVIEW", result)
        self.assertIsNone((result.nutrition or {}).get("calories"), result)

    def test_unanchored_single_digit_kcal_is_not_rescued(self) -> None:
        text = """100 ml
Referencia diaria 3 kcal
Grasas 0 g
Hidratos de Carbono 0 g
Proteínas 0 g
"""
        result = fuse_ocr_readings([
            self.reading("easyocr", text),
            self.reading("paddleocr", text),
        ])

        self.assertEqual(result.status, "REVIEW", result)
        self.assertIsNone((result.nutrition or {}).get("calories"), result)


if __name__ == "__main__":
    unittest.main()
