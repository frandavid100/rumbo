import unittest

from label_table_column_association import associate_explicit_basis_column
from label_table_geometry import parse_tesseract_tsv


TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"


def _word(*, text: str, left: int, top: int = 20, width: int = 30, height: int = 12,
          block: int = 1, par: int = 1, line: int = 1, word: int = 1, conf: float = 95.0) -> str:
    return f"5\t1\t{block}\t{par}\t{line}\t{word}\t{left}\t{top}\t{width}\t{height}\t{conf}\t{text}\n"


def _line(*, top: int, line: int, parts: list[tuple[str, int, int]]) -> str:
    return "".join(
        _word(text=text, left=left, top=top, width=width, line=line, word=index + 1)
        for index, (text, left, width) in enumerate(parts)
    )


class TableColumnAssociationTest(unittest.TestCase):
    def test_associates_four_core_rows_without_parsing_values(self):
        raw = (
            TSV_HEADER
            + _word(text="Por100g", left=280, top=20, width=60, line=1)
            + _line(top=60, line=2, parts=[("Valor", 20, 35), ("energético", 60, 70), ("240", 286, 28), ("kcal", 318, 30)])
            + _line(top=90, line=3, parts=[("Grasas", 20, 48), ("12,2", 286, 34), ("g", 324, 8)])
            + _line(top=120, line=4, parts=[("Hidratos", 20, 60), ("de", 85, 16), ("carbono", 106, 54), ("26", 292, 22), ("g", 318, 8)])
            + _line(top=150, line=5, parts=[("Proteínas", 20, 66), ("6,7", 290, 28), ("g", 322, 8)])
        )
        association = associate_explicit_basis_column(parse_tesseract_tsv(raw))
        self.assertEqual(association["status"], "ASSOCIATED_CORE_ROWS_DIAGNOSTIC")
        self.assertEqual(association["associated_core_field_count"], 4)
        self.assertFalse(association["nutrition_values_selected"])
        self.assertFalse(association["numeric_values_parsed"])
        self.assertEqual(association["rows"]["fat_g"]["associated_cell"]["text"], "12,2 g")

    def test_kj_and_kcal_remain_one_geometry_cell(self):
        raw = (
            TSV_HEADER
            + _word(text="100g", left=280, top=20, width=50, line=1)
            + _line(top=60, line=2, parts=[
                ("Valor", 20, 35), ("energético", 60, 70),
                ("1000", 270, 34), ("kJ", 308, 18), ("/", 330, 8), ("240", 342, 28), ("kcal", 374, 30),
            ])
        )
        association = associate_explicit_basis_column(parse_tesseract_tsv(raw))
        row = association["rows"]["calories"]
        self.assertEqual(row["status"], "ASSOCIATED_CELL_DIAGNOSTIC")
        self.assertEqual(row["associated_cell"]["numeric_token_count"], 2)
        self.assertIn("240", row["associated_cell"]["text"])

    def test_nearby_second_numeric_column_fails_closed(self):
        raw = (
            TSV_HEADER
            + _word(text="100g", left=280, top=20, width=50, line=1)
            + _line(top=60, line=2, parts=[("Grasas", 20, 48), ("12", 285, 20), ("g", 309, 8), ("6", 338, 12), ("g", 354, 8)])
        )
        association = associate_explicit_basis_column(parse_tesseract_tsv(raw))
        self.assertEqual(association["status"], "AMBIGUOUS_NUMERIC_COLUMN")
        self.assertEqual(association["rows"]["fat_g"]["status"], "AMBIGUOUS_EXPLICIT_COLUMN_CELL")
        self.assertIsNone(association["rows"]["fat_g"]["associated_cell"])

    def test_far_serving_column_is_not_associated(self):
        raw = (
            TSV_HEADER
            + _word(text="100g", left=280, top=20, width=50, line=1)
            + _line(top=60, line=2, parts=[("Grasas", 20, 48), ("12", 285, 20), ("g", 309, 8), ("6", 430, 12), ("g", 446, 8)])
        )
        association = associate_explicit_basis_column(parse_tesseract_tsv(raw))
        row = association["rows"]["fat_g"]
        self.assertEqual(row["status"], "ASSOCIATED_CELL_DIAGNOSTIC")
        self.assertEqual(row["associated_cell"]["text"], "12 g")
        self.assertEqual(len(row["candidate_cells"]), 2)

    def test_visual_row_crosses_tesseract_block_boundaries(self):
        raw = (
            TSV_HEADER
            + _word(text="100g", left=280, top=20, width=50, line=1)
            + _word(text="Grasas", left=20, top=60, width=48, block=2, line=1)
            + _word(text="12", left=285, top=61, width=20, block=3, line=1)
            + _word(text="g", left=309, top=60, width=8, block=3, line=1, word=2)
        )
        association = associate_explicit_basis_column(parse_tesseract_tsv(raw))
        row = association["rows"]["fat_g"]
        self.assertEqual(row["status"], "ASSOCIATED_CELL_DIAGNOSTIC")
        self.assertEqual(row["associated_cell"]["text"], "12 g")

    def test_saturated_subrow_is_not_total_fat(self):
        raw = (
            TSV_HEADER
            + _word(text="100g", left=280, top=20, width=50, line=1)
            + _line(top=60, line=2, parts=[("Grasas", 20, 48), ("12", 285, 20), ("g", 309, 8)])
            + _line(top=90, line=3, parts=[("Grasas", 20, 48), ("saturadas", 72, 62), ("4", 289, 12), ("g", 305, 8)])
        )
        association = associate_explicit_basis_column(parse_tesseract_tsv(raw))
        row = association["rows"]["fat_g"]
        self.assertEqual(row["status"], "ASSOCIATED_CELL_DIAGNOSTIC")
        self.assertEqual(row["associated_cell"]["text"], "12 g")

    def test_duplicate_total_fat_rows_fail_closed(self):
        raw = (
            TSV_HEADER
            + _word(text="100g", left=280, top=20, width=50, line=1)
            + _line(top=60, line=2, parts=[("Grasas", 20, 48), ("12", 285, 20), ("g", 309, 8)])
            + _line(top=90, line=3, parts=[("Grasa", 20, 42), ("11", 285, 20), ("g", 309, 8)])
        )
        association = associate_explicit_basis_column(parse_tesseract_tsv(raw))
        self.assertEqual(association["status"], "AMBIGUOUS_ROW_LABEL")
        self.assertEqual(association["rows"]["fat_g"]["status"], "AMBIGUOUS_ROW_LABEL")

    def test_missing_header_never_associates_cells(self):
        raw = TSV_HEADER + _line(top=60, line=2, parts=[("Grasas", 20, 48), ("12", 285, 20), ("g", 309, 8)])
        association = associate_explicit_basis_column(parse_tesseract_tsv(raw))
        self.assertEqual(association["status"], "MISSING_EXPLICIT_100_BASIS_HEADER")
        self.assertEqual(association["rows"], {})

    def test_ambiguous_header_never_associates_cells(self):
        raw = (
            TSV_HEADER
            + _word(text="100g", left=280, top=20, width=50, line=1)
            + _word(text="100g", left=400, top=20, width=50, line=1, word=2)
        )
        association = associate_explicit_basis_column(parse_tesseract_tsv(raw))
        self.assertEqual(association["status"], "AMBIGUOUS_EXPLICIT_100_BASIS_HEADER")
        self.assertEqual(association["rows"], {})


if __name__ == "__main__":
    unittest.main()
