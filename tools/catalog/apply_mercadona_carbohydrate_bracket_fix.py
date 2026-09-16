from __future__ import annotations

import argparse
from pathlib import Path

TEST_PATH = Path("tools/catalog/test_nutrition_label_reader_row_tokens.py")
PARSER_PATH = Path("tools/catalog/nutrition_label_reader.py")
PILOT_PATH = Path(".github/workflows/catalog-mercadona-near-safe-doctr-pilot.yml")

TEST_NAME = "test_observed_easyocr_bracketed_split_carbohydrate_label"
TEST_SENTINEL = "    def test_interleaved_carbohydrate_allows_observed_conservation_heading(self):\n"
TEST_BLOCK = '''    def test_observed_easyocr_bracketed_split_carbohydrate_label(self):
        # Observed on Mercadona 11609: EasyOCR emits stray bracket glyphs before
        # both halves of the printed `Hidratos de Carbono` row while preserving
        # the dedicated 80 g cell between them. Accept only those one-character
        # OCR punctuation glyphs; arbitrary intervening prose remains blocked.
        text = (
            'INFORMACIÓN NUTRICIONAL\\npor 100 g\\n'
            'Valor energético 1601 kJ / 378 kcal\\n'
            'Grasas 2.6 g\\n'
            '[Hidratos de\\n80 g\\n(Carbono\\n'
            'Proteínas 5.6 g\\nSal 0.01 g\\n'
        )
        r = read_nutrition_label(text, extraction_confidence=.96)
        self.assertEqual(r.status, 'DECLARED', r)
        self.assertEqual(r.nutrition['carbohydrate_g'], 80.0)

'''

OLD_DOC = '''    whole-package ordering additionally inserts the standalone `CONSERVACION`
    heading between the numeric cell and `Carbono`; no arbitrary prose is skipped.
    Observed OCR unit glyphs include g, 9, y, q and the two-character `yg`.
'''
NEW_DOC = '''    whole-package ordering additionally inserts the standalone `CONSERVACION`
    heading between the numeric cell and `Carbono`; no arbitrary prose is skipped.
    EasyOCR can also prefix either half of the split row label with a stray `[` or
    `(` glyph. Accept only those observed one-character OCR punctuation glyphs.
    Observed OCR unit glyphs include g, 9, y, q and the two-character `yg`.
'''
OLD_REGEX = '''        r"(?:^|\\n)\\s*hidratos?\\s+de\\s+([<>]?)\\s*(\\d{1,3}(?:\\.\\d{1,2})?)\\s*(?:g|9|yg|y|q)?"
        r"(?:\\s*\\n\\s*conservacion\\s*)?\\s+carbono\\b",
'''
NEW_REGEX = '''        r"(?:^|\\n)\\s*[\\[(|]?\\s*hidratos?\\s+de\\s+([<>]?)\\s*(\\d{1,3}(?:\\.\\d{1,2})?)\\s*(?:g|9|yg|y|q)?"
        r"(?:\\s*\\n\\s*conservacion)?\\s+[\\[(|]?\\s*carbono\\b",
'''


def insert_test() -> None:
    text = TEST_PATH.read_text(encoding="utf-8")
    if TEST_NAME in text:
        return
    if text.count(TEST_SENTINEL) != 1:
        raise SystemExit("row-token regression insertion sentinel changed")
    TEST_PATH.write_text(text.replace(TEST_SENTINEL, TEST_BLOCK + TEST_SENTINEL, 1), encoding="utf-8")


def apply_fix() -> None:
    text = PARSER_PATH.read_text(encoding="utf-8")
    if 'READER_VERSION = "1.4.25"' not in text:
        if text.count('READER_VERSION = "1.4.24"') != 1:
            raise SystemExit("unexpected nutrition reader version")
        text = text.replace('READER_VERSION = "1.4.24"', 'READER_VERSION = "1.4.25"', 1)
    if NEW_DOC not in text:
        if text.count(OLD_DOC) != 1:
            raise SystemExit("interleaved carbohydrate docstring sentinel changed")
        text = text.replace(OLD_DOC, NEW_DOC, 1)
    if NEW_REGEX not in text:
        if text.count(OLD_REGEX) != 1:
            raise SystemExit("interleaved carbohydrate regex sentinel changed")
        text = text.replace(OLD_REGEX, NEW_REGEX, 1)
    PARSER_PATH.write_text(text, encoding="utf-8")

    wf = PILOT_PATH.read_text(encoding="utf-8")
    if "35139148569" not in wf:
        if wf.count("35100259145") != 2:
            raise SystemExit("near-safe source audit run sentinel changed")
        wf = wf.replace("35100259145", "35139148569")
    PILOT_PATH.write_text(wf, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("insert-test", "apply"))
    args = ap.parse_args()
    if args.mode == "insert-test":
        insert_test()
    else:
        apply_fix()


if __name__ == "__main__":
    main()
