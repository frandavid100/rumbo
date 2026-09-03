from __future__ import annotations

import unittest

from audit_mercadona_missing_one_core_candidates_v2 import candidate_payload


class MissingOneCoreCandidateAuditV2Tests(unittest.TestCase):
    def _row(self, *, calories=200.0, support_fat=8.0):
        return {
            "status": "REVIEW",
            "replay": {
                "status": "REVIEW",
                "basis": "100_g",
                "nutrition": {"calories": calories, "protein_g": 10.0, "carbohydrate_g": 20.0},
                "attempt_ensembles": [
                    {
                        "status": "REVIEW",
                        "basis": "100_g",
                        "nutrition": {"calories": calories, "protein_g": 10.0, "carbohydrate_g": 20.0},
                        "corroborated_fields": 2,
                        "independent_engine_families": 2,
                        "confidence": 0.9,
                        "reasons": ["MISSING_CORE:fat_g"],
                    }
                ],
            },
            "attempts": [
                {
                    "engines": {
                        "paddleocr": {
                            "status": "REVIEW",
                            "basis": "100_g",
                            "nutrition": {"fat_g": support_fat},
                        },
                        "tesseract-psm4": {
                            "status": "REVIEW",
                            "basis": "100_g",
                            "nutrition": {"fat_g": support_fat},
                        },
                    }
                }
            ],
            "product_id": "1",
            "ean": "8410000000001",
            "name": "Fixture",
            "perspective": "9",
        }

    def test_accepts_energy_plausible_missing_macro_support(self):
        payload = candidate_payload(self._row())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["missing_core_field"], "fat_g")
        self.assertEqual(payload["missing_field_support"][0]["value"], 8.0)

    def test_rejects_ingredient_percentage_misread_as_fat(self):
        # Regression from Mercadona product 23225: 48 kcal/100 g, while an
        # earlier Paddle pass misread "calabaza 24%" as 24 g fat. Fat alone
        # would contribute 216 kcal, so that support cannot be nutritional.
        self.assertIsNone(candidate_payload(self._row(calories=48.0, support_fat=24.0)))

    def test_rejects_impossible_carbohydrate_support(self):
        row = self._row(calories=82.0, support_fat=1.0)
        row["replay"]["nutrition"] = {"calories": 82.0, "protein_g": 18.0, "fat_g": 1.0}
        row["replay"]["attempt_ensembles"][0]["nutrition"] = {
            "calories": 82.0,
            "protein_g": 18.0,
            "fat_g": 1.0,
        }
        row["replay"]["attempt_ensembles"][0]["reasons"] = ["MISSING_CORE:carbohydrate_g"]
        for engine in row["attempts"][0]["engines"].values():
            engine["nutrition"] = {"carbohydrate_g": 100.0}
        self.assertIsNone(candidate_payload(row))

    def test_rejects_tesseract_only_support(self):
        row = self._row()
        del row["attempts"][0]["engines"]["paddleocr"]
        self.assertIsNone(candidate_payload(row))

    def test_rejects_hard_conflict(self):
        row = self._row()
        row["replay"]["attempt_ensembles"][0]["reasons"].append("OCR_FIELD_CONFLICT:fat_g")
        self.assertIsNone(candidate_payload(row))


if __name__ == "__main__":
    unittest.main()
