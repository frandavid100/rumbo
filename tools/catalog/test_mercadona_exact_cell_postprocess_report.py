import unittest

from mercadona_exact_cell_postprocess_report import postprocess_report


class ReportPostprocessTest(unittest.TestCase):
    def test_keeps_attempts_separate_and_never_marks_usable(self):
        report = {
            "product_id": "67660",
            "ean": "8480000676603",
            "attempts": [
                {
                    "variant": "full_autocontrast",
                    "psm": 11,
                    "association": {
                        "status": "PARTIAL_CORE_ROWS_DIAGNOSTIC",
                        "basis_header_status": "UNIQUE_EXPLICIT_100_BASIS_HEADER",
                        "rows": {
                            "calories": {
                                "status": "ASSOCIATED_CELL_DIAGNOSTIC",
                                "label_text": "Energético/Energia",
                                "associated_cell": {"text": "395 kcal", "center_x": 2707.0},
                            },
                        },
                    },
                },
                {
                    "variant": "crop_center",
                    "psm": 11,
                    "association": {
                        "status": "MISSING_EXPLICIT_100_BASIS_HEADER",
                        "basis_header_status": "MISSING_EXPLICIT_100_BASIS_HEADER",
                        "rows": {},
                    },
                },
            ],
        }
        result = postprocess_report(report)
        self.assertTrue(result["diagnostic_only"])
        self.assertFalse(result["canonical_reconciliation_allowed"])
        self.assertFalse(result["nutrition_usable"])
        self.assertFalse(result["missing_values_inferred"])
        self.assertEqual(result["exact_value_observations"], 1)
        self.assertEqual(len(result["attempts"]), 2)
        parsed = result["attempts"][0]["exact_cell_postprocess"]
        self.assertEqual(parsed["exact_cells"]["calories"]["parse"]["exact_value"], 395.0)
        self.assertEqual(result["attempts"][1]["exact_cell_postprocess"]["status"], "BLOCKED_BY_ASSOCIATION")


if __name__ == "__main__":
    unittest.main()
