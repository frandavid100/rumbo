import unittest

from label_table_column_association import associate_explicit_basis_column
from label_table_exact_cell_parser import parse_exact_nutrition_cell
from label_table_geometry import parse_tesseract_tsv


TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"


def _word(*, text: str, left: int, top: int, width: int, height: int = 60,
          block: int = 1, line: int = 1, word: int = 1) -> str:
    return f"5\t1\t{block}\t1\t{line}\t{word}\t{left}\t{top}\t{width}\t{height}\t95\t{text}\n"


class TableColumnAssociationRegressionTest(unittest.TestCase):
    def test_noisy_bilingual_two_column_energy_row_uses_explicit_100g_geometry(self):
        raw = (
            TSV_HEADER
            + _word(text="100", left=2619, top=646, width=100, height=77, block=3, line=1, word=1)
            + _word(text="g", left=2730, top=646, width=46, height=77, block=3, line=1, word=2)
            # Ingredient text and a percentage share the visual row to the left.
            + _word(text="soluble", left=239, top=835, width=120, block=11, line=1, word=1)
            + _word(text="(10%),", left=387, top=833, width=117, height=72, block=11, line=1, word=2)
            + _word(text="grasa", left=1247, top=849, width=133, block=11, line=1, word=3)
            + _word(text="de", left=1405, top=833, width=55, block=11, line=1, word=4)
            + _word(text="coco,", left=1484, top=849, width=106, block=11, line=1, word=5)
            + _word(text="Energético/Energia", left=1830, top=813, width=672, height=80, block=9, line=1, word=1)
            + _word(text="395", left=2549, top=812, width=142, height=62, block=9, line=1, word=2)
            + _word(text="kcal", left=2720, top=809, width=145, height=65, block=9, line=1, word=3)
            + _word(text="52", left=2967, top=812, width=83, height=63, block=10, line=1, word=1)
            + _word(text="kcal", left=3073, top=810, width=122, height=67, block=10, line=1, word=2)
        )
        association = associate_explicit_basis_column(parse_tesseract_tsv(raw))
        row = association["rows"]["calories"]
        self.assertEqual(row["status"], "ASSOCIATED_CELL_DIAGNOSTIC")
        self.assertEqual(row["label_text"], "Energético/Energia")
        self.assertEqual(row["associated_cell"]["text"], "395 kcal")
        self.assertNotEqual(row["associated_cell"]["text"], "52 kcal")
        self.assertFalse(association["nutrition_values_selected"])
        self.assertFalse(association["numeric_values_parsed"])

    def test_tall_noise_box_cannot_bridge_separate_visual_rows(self):
        raw = (
            TSV_HEADER
            + _word(text="100g", left=280, top=20, width=50, height=12, line=1)
            + _word(text="Grasas", left=20, top=80, width=48, height=12, block=2, line=1)
            + _word(text="12", left=285, top=80, width=20, height=12, block=3, line=1)
            + _word(text="g", left=309, top=80, width=8, height=12, block=3, line=1, word=2)
            # A bad OCR box overlaps both real rows geometrically but has a distant center.
            + _word(text="ruido", left=700, top=35, width=100, height=180, block=4, line=1)
            + _word(text="Proteínas", left=20, top=140, width=66, height=12, block=5, line=1)
            + _word(text="7", left=289, top=140, width=12, height=12, block=6, line=1)
            + _word(text="g", left=305, top=140, width=8, height=12, block=6, line=1, word=2)
        )
        association = associate_explicit_basis_column(parse_tesseract_tsv(raw))
        self.assertEqual(association["rows"]["fat_g"]["associated_cell"]["text"], "12 g")
        self.assertEqual(association["rows"]["protein_g"]["associated_cell"]["text"], "7 g")
        self.assertNotEqual(association["status"], "AMBIGUOUS_ROW_LABEL")


class ExactCellParserRegressionTest(unittest.TestCase):
    def test_explicit_100g_energy_cell_parses_without_serving_column_leakage(self):
        parsed = parse_exact_nutrition_cell("calories", "395 kcal")
        self.assertEqual(parsed["status"], "EXACT_VALUE", parsed)
        self.assertEqual(parsed["exact_value"], 395.0)
        serving = parse_exact_nutrition_cell("calories", "52 kcal")
        self.assertEqual(serving["status"], "EXACT_VALUE", serving)
        self.assertEqual(serving["exact_value"], 52.0)

    def test_missing_decimal_punctuation_is_never_repaired(self):
        parsed = parse_exact_nutrition_cell("carbohydrate_g", "269")
        self.assertEqual(parsed["status"], "REJECTED", parsed)
        self.assertEqual(parsed["reason"], "MISSING_OR_UNSUPPORTED_GRAM_UNIT")
        self.assertIsNone(parsed["exact_value"])
        self.assertFalse(parsed["decimal_repaired"])

    def test_observed_unit_bearing_cells_parse_exactly(self):
        fat = parse_exact_nutrition_cell("fat_g", "12g")
        protein = parse_exact_nutrition_cell("protein_g", "6,7 g")
        self.assertEqual((fat["status"], fat["exact_value"]), ("EXACT_VALUE", 12.0))
        self.assertEqual((protein["status"], protein["exact_value"]), ("EXACT_VALUE", 6.7))

    def test_bounds_extra_numbers_and_leading_zero_fail_closed(self):
        cases = (
            ("fat_g", "<0,5 g"),
            ("fat_g", "12 g 6 g"),
            ("fat_g", "01 g"),
            ("calories", "1653 kJ / 395 kcal 20%"),
            ("calories", "02 kcal"),
        )
        for field, raw in cases:
            with self.subTest(field=field, raw=raw):
                parsed = parse_exact_nutrition_cell(field, raw)
                self.assertEqual(parsed["status"], "REJECTED", parsed)
                self.assertIsNone(parsed["exact_value"], parsed)

    def test_coherent_kj_kcal_pair_is_exact_without_unit_conversion(self):
        parsed = parse_exact_nutrition_cell("calories", "1653 kJ / 395 kcal")
        self.assertEqual(parsed["status"], "EXACT_VALUE", parsed)
        self.assertEqual(parsed["exact_value"], 395.0)
        self.assertEqual(parsed["corroborating_kj"], 1653.0)
        self.assertFalse(parsed["unit_converted"])

    def test_incoherent_energy_pair_and_low_unpaired_kcal_fail_closed(self):
        bad_pair = parse_exact_nutrition_cell("calories", "1653 kJ / 52 kcal")
        low = parse_exact_nutrition_cell("calories", "2,9 kcal")
        self.assertEqual(bad_pair["reason"], "INCOHERENT_KJ_KCAL_PAIR")
        self.assertEqual(low["reason"], "LOW_KCAL_REQUIRES_COHERENT_KJ_PAIR")


if __name__ == "__main__":
    unittest.main()
