import unittest

from label_table_geometry import (
    find_explicit_basis_headers,
    parse_tesseract_tsv,
    unique_basis_header,
)


TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"


def _word(*, text: str, left: int, top: int = 20, width: int = 30, height: int = 12,
          block: int = 1, par: int = 1, line: int = 1, word: int = 1, conf: float = 95.0) -> str:
    return f"5\t1\t{block}\t{par}\t{line}\t{word}\t{left}\t{top}\t{width}\t{height}\t{conf}\t{text}\n"


class LabelTableGeometryTest(unittest.TestCase):
    def test_finds_single_token_100g_header(self):
        raw = TSV_HEADER + _word(text="100g", left=220)
        tokens = parse_tesseract_tsv(raw)
        status, header = unique_basis_header(tokens)
        self.assertEqual(status, "UNIQUE_EXPLICIT_100_BASIS_HEADER")
        self.assertIsNotNone(header)
        self.assertEqual(header.basis, "100_g")
        self.assertEqual(header.center_x, 235.0)

    def test_finds_split_100_g_only_when_visually_adjacent(self):
        raw = (
            TSV_HEADER
            + _word(text="por", left=80, word=1)
            + _word(text="100", left=150, width=28, word=2)
            + _word(text="g", left=184, width=8, word=3)
            + _word(text="ración", left=300, width=45, word=4)
        )
        status, header = unique_basis_header(parse_tesseract_tsv(raw))
        self.assertEqual(status, "UNIQUE_EXPLICIT_100_BASIS_HEADER")
        self.assertEqual(header.basis, "100_g")
        self.assertEqual(header.text, "100 g")

        far = TSV_HEADER + _word(text="100", left=100, word=1) + _word(text="g", left=400, width=8, word=2)
        status, header = unique_basis_header(parse_tesseract_tsv(far))
        self.assertEqual(status, "MISSING_EXPLICIT_100_BASIS_HEADER")
        self.assertIsNone(header)

    def test_finds_100ml_header(self):
        raw = TSV_HEADER + _word(text="100", left=100, word=1) + _word(text="ml", left=136, width=16, word=2)
        status, header = unique_basis_header(parse_tesseract_tsv(raw))
        self.assertEqual(status, "UNIQUE_EXPLICIT_100_BASIS_HEADER")
        self.assertEqual(header.basis, "100_ml")

    def test_multiple_explicit_100g_headers_fail_closed(self):
        raw = (
            TSV_HEADER
            + _word(text="100g", left=100, line=1, word=1)
            + _word(text="100", left=300, top=50, line=2, word=1)
            + _word(text="g", left=336, top=50, width=8, line=2, word=2)
        )
        tokens = parse_tesseract_tsv(raw)
        self.assertEqual(len(find_explicit_basis_headers(tokens)), 2)
        status, header = unique_basis_header(tokens)
        self.assertEqual(status, "AMBIGUOUS_EXPLICIT_100_BASIS_HEADER")
        self.assertIsNone(header)

    def test_ignores_empty_and_non_word_rows(self):
        raw = (
            TSV_HEADER
            + "4\t1\t1\t1\t1\t0\t0\t0\t500\t20\t-1\t\n"
            + _word(text="100g", left=200)
            + _word(text="", left=260, word=2)
        )
        tokens = parse_tesseract_tsv(raw)
        self.assertEqual([token.text for token in tokens], ["100g"])

    def test_malformed_word_row_raises(self):
        raw = TSV_HEADER + "5\t1\t1\t1\t1\t1\tx\t20\t30\t12\t95\t100g\n"
        with self.assertRaises(ValueError):
            parse_tesseract_tsv(raw)


if __name__ == "__main__":
    unittest.main()
