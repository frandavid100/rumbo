import unittest

from label_table_exact_diagnostic import parse_associated_exact_cells


class ExactDiagnosticPostprocessTest(unittest.TestCase):
    def _association(self, *, status="PARTIAL_CORE_ROWS_DIAGNOSTIC", header_status="UNIQUE_EXPLICIT_100_BASIS_HEADER", rows=None):
        return {
            "status": status,
            "basis_header_status": header_status,
            "rows": rows or {},
        }

    def test_parses_only_geometry_associated_cells(self):
        association = self._association(rows={
            "calories": {
                "status": "ASSOCIATED_CELL_DIAGNOSTIC",
                "label_text": "Energético/Energia",
                "associated_cell": {"text": "395 kcal", "center_x": 2707.0},
            },
            "fat_g": {
                "status": "MISSING_ROW_LABEL_OR_EXPLICIT_COLUMN_CELL",
                "associated_cell": None,
            },
        })
        result = parse_associated_exact_cells(association)
        self.assertTrue(result["diagnostic_only"])
        self.assertFalse(result["canonical_reconciliation_allowed"])
        self.assertFalse(result["nutrition_usable"])
        self.assertEqual(result["exact_value_count"], 1)
        self.assertEqual(result["exact_cells"]["calories"]["parse"]["exact_value"], 395.0)
        self.assertNotIn("fat_g", result["exact_cells"])

    def test_unitless_ocr_is_retained_but_rejected(self):
        association = self._association(rows={
            "carbohydrate_g": {
                "status": "ASSOCIATED_CELL_DIAGNOSTIC",
                "label_text": "Hidratos de Carbono",
                "associated_cell": {"text": "269", "center_x": 2700.0},
            },
        })
        result = parse_associated_exact_cells(association)
        parsed = result["exact_cells"]["carbohydrate_g"]["parse"]
        self.assertEqual(parsed["status"], "REJECTED")
        self.assertEqual(parsed["reason"], "MISSING_OR_UNSUPPORTED_GRAM_UNIT")
        self.assertEqual(result["exact_value_count"], 0)
        self.assertFalse(result["missing_values_inferred"])

    def test_global_ambiguity_blocks_all_cell_parsing(self):
        association = self._association(
            status="AMBIGUOUS_NUMERIC_COLUMN",
            rows={
                "calories": {
                    "status": "ASSOCIATED_CELL_DIAGNOSTIC",
                    "label_text": "Energia",
                    "associated_cell": {"text": "395 kcal", "center_x": 2700.0},
                },
            },
        )
        result = parse_associated_exact_cells(association)
        self.assertEqual(result["status"], "BLOCKED_BY_ASSOCIATION")
        self.assertEqual(result["exact_cells"], {})
        self.assertEqual(result["exact_value_count"], 0)

    def test_missing_or_ambiguous_basis_blocks_all_cell_parsing(self):
        for header_status in ("MISSING_EXPLICIT_100_BASIS_HEADER", "AMBIGUOUS_EXPLICIT_100_BASIS_HEADER"):
            with self.subTest(header_status=header_status):
                result = parse_associated_exact_cells(self._association(
                    status=header_status,
                    header_status=header_status,
                ))
                self.assertEqual(result["status"], "BLOCKED_BY_ASSOCIATION")
                self.assertEqual(result["exact_cells"], {})


if __name__ == "__main__":
    unittest.main()
