from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
TEST_PATH = ROOT / "test_nutrition_label_reader.py"
READER_PATH = ROOT / "nutrition_label_reader.py"
VALIDATION_DIR = Path("/tmp/parser-validation")
SOURCE_CANARY = Path("/tmp/source-canary")

TEST1 = "test_nutrition_label_reader.NutritionLabelReaderTest.test_single_per100_heading_split_across_lines_is_not_parallel_columns"
TEST2 = "test_nutrition_label_reader.NutritionLabelReaderTest.test_observed_vator_nutricional_heading_excludes_package_net_weight"
TRUE_MULTI = "test_nutrition_label_reader.NutritionLabelReaderTest.test_parallel_per_100g_columns_are_review_not_mixed"


def run(args: list[str], *, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=ROOT, text=True, check=False)
    if expect_success and result.returncode != 0:
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(args)}")
    return result


def add_regression_tests() -> None:
    text = TEST_PATH.read_text(encoding="utf-8")
    if "test_single_per100_heading_split_across_lines_is_not_parallel_columns" in text:
        raise SystemExit("regression tests already present unexpectedly")
    marker = "    def test_kj_kcal_header_before_values_is_parsed_conservatively(self):\n"
    if text.count(marker) != 1:
        raise SystemExit("test insertion marker not unique")
    tests = '''    def test_single_per100_heading_split_across_lines_is_not_parallel_columns(self):
        # A single printed heading can be OCR-linearised as `por` on one line and
        # `100 g` on the next. The same basis token must not be counted twice as
        # though it represented two nutrition columns.
        observed = """INFORMACIÓN NUTRICIONAL
Valores medios por
100 g
Valor energético 1050 kJ/251 kcal
Grasas 12.8 g
de las cuales saturadas 4.8 g
Hidratos de carbono <0.5 g
de los cuales azúcares <0.5 g
Proteínas 33.3 g
Sal 4.28 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertNotIn("MULTIPLE_NUTRITION_COLUMNS", r.reasons)
        self.assertIn("MISSING_CORE:carbohydrate_g", r.reasons)

    def test_observed_vator_nutricional_heading_excludes_package_net_weight(self):
        # Observed PP-OCRv6 text for a Mercadona label used `Vator Nutricional
        # Medio` for the table heading while a separate package net-weight
        # `100g` appeared earlier. The package quantity must stay outside the
        # nutrition block rather than becoming a phantom second basis column.
        observed = """CECINA AHUMADA
100g
LOTE 1234
Vator Nutricional Medio por 100g
Valor energético 868 kJ/206 kcal
Grasas 7 g
de las cuales saturadas 2.4 g
Hidratos de carbono <0.8 g
de los cuales azúcares <0.5 g
Proteínas 35 g
Sal 3.8 g
"""
        r = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(r.status, "REVIEW", r)
        self.assertNotIn("MULTIPLE_NUTRITION_COLUMNS", r.reasons)
        self.assertIn("MISSING_CORE:carbohydrate_g", r.reasons)

'''
    TEST_PATH.write_text(text.replace(marker, tests + marker), encoding="utf-8")


def reproduce_regression() -> None:
    result = run([sys.executable, "-m", "unittest", "-v", TEST1, TEST2], expect_success=False)
    if result.returncode == 0:
        raise SystemExit("expected at least one regression test to fail before parser patch")
    print("Regression reproduced against pre-patch parser.")


def patch_reader() -> None:
    text = READER_PATH.read_text(encoding="utf-8")
    if text.count('READER_VERSION = "1.4.30"') != 1:
        raise SystemExit("unexpected reader version")
    text = text.replace('READER_VERSION = "1.4.30"', 'READER_VERSION = "1.4.31"')

    old_heading = '''    for pattern in (r"informacion nutricional", r"declaracion nutricional", r"valores nutricionales"):
        m = re.search(pattern, folded, flags=re.I)
'''
    new_heading = '''    # `Valor nutricional medio` is another genuine table heading used on
    # Mercadona labels. PP-OCRv6 has also emitted the narrow observed typo
    # `Vator nutricional medio`; accepting that exact heading keeps unrelated
    # package quantities outside the nutrition block without fuzzy matching.
    for pattern in (
        r"informacion nutricional",
        r"declaracion nutricional",
        r"valores nutricionales",
        r"valor nutricional(?: medio)?",
        r"vator nutricional(?: medio)?",
    ):
        m = re.search(pattern, folded, flags=re.I)
'''
    if text.count(old_heading) != 1:
        raise SystemExit("nutrition heading block no longer matches expected source")
    text = text.replace(old_heading, new_heading)

    old_func = '''def _basis_heading_count(text: str) -> int:
    """Count explicit per-100 column headings, including OCR-linearized rows.

    Two per-100 headings usually mean parallel nutrition columns (e.g. net
    weight vs drained weight, or product vs accompanying cheese). OCR can drop
    the printed `Por` and linearise those headings as consecutive standalone
    `100 g` rows, so count that exact row shape too. Incidental `100 g` prose is
    not counted unless it occupies the whole line. The parser is row-oriented
    and must review rather than silently mix parallel columns.
    """
    folded = _fold(text)
    explicit = re.findall(
        r"\\bpor\\s+100\\s*(?:g\\b|9\\b|q\\b|yg\\b|y\\b|m(?:l|i|1)\\b)",
        folded,
        flags=re.I,
    )
    standalone = re.findall(
        r"(?im)^\\s*100\\s*(?:g|9|q|yg|y|m(?:l|i|1))\\s*$",
        folded,
    )
    return len(explicit) + len(standalone)
'''
    new_func = '''def _basis_heading_count(text: str) -> int:
    """Count distinct explicit per-100 column headings.

    Two genuinely distinct per-100 headings usually mean parallel nutrition
    columns (e.g. net vs drained weight), which the row-oriented parser must
    reject. OCR can also linearise one ordinary heading as `por` followed by a
    standalone `100 g` row. In that case the explicit and standalone regexes
    describe the exact same basis token, so count its character span only once.
    """
    folded = _fold(text)
    unit = r"(?:g\\b|9\\b|q\\b|yg\\b|y\\b|m(?:l|i|1)\\b)"
    explicit = list(re.finditer(
        rf"\\bpor\\s+(?P<basis>100\\s*{unit})",
        folded,
        flags=re.I,
    ))
    standalone = list(re.finditer(
        rf"(?im)^\\s*(?P<basis>100\\s*{unit})\\s*$",
        folded,
    ))
    spans = {(m.start("basis"), m.end("basis")) for m in explicit}
    spans.update((m.start("basis"), m.end("basis")) for m in standalone)
    return len(spans)
'''
    if text.count(old_func) != 1:
        raise SystemExit("basis heading function no longer matches expected source")
    text = text.replace(old_func, new_func)
    READER_PATH.write_text(text, encoding="utf-8")


def validate_tests() -> None:
    run([sys.executable, "-m", "unittest", "-v", TEST1, TEST2, TRUE_MULTI])
    run([
        sys.executable,
        "-m",
        "unittest",
        "-v",
        "test_nutrition_label_reader.py",
        "test_nutrition_ocr_ensemble.py",
        "test_mercadona_ocr_safety_regressions.py",
    ])


def validate_observed_sample() -> None:
    if SOURCE_CANARY.exists():
        subprocess.run(["rm", "-rf", str(SOURCE_CANARY)], check=True)
    SOURCE_CANARY.mkdir(parents=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "gh", "run", "download", "35745857558",
        "-n", "mercadona-current-unique-non-p9-safe-canary",
        "-D", str(SOURCE_CANARY),
    ], check=True)

    sys.path.insert(0, str(ROOT))
    from nutrition_label_reader import READER_VERSION, read_nutrition_label

    rows: list[dict[str, object]] = []
    for path in sorted(SOURCE_CANARY.rglob("results-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            product_id = str(row.get("product_id") or "")
            if product_id not in {"59101", "59280"}:
                continue
            texts: list[tuple[str, str]] = []
            if isinstance(row.get("ocr_text"), str):
                texts.append(("ocr_text", row["ocr_text"]))
            for key in ("engine_results", "readings", "variants"):
                value = row.get(key)
                if isinstance(value, list):
                    for i, item in enumerate(value):
                        if not isinstance(item, dict):
                            continue
                        for tkey in ("ocr_text", "text", "normalized_text"):
                            if isinstance(item.get(tkey), str):
                                texts.append((f"{key}[{i}].{tkey}", item[tkey]))
            for origin, text in texts:
                parsed = read_nutrition_label(text, extraction_confidence=.98)
                if "MULTIPLE_NUTRITION_COLUMNS" in parsed.reasons:
                    raise SystemExit(f"false multi-column blocker remains for {product_id} from {origin}")
                rows.append({
                    "product_id": product_id,
                    "origin": origin,
                    "status": parsed.status,
                    "basis": parsed.basis,
                    "reasons": list(parsed.reasons),
                    "nutrition": parsed.nutrition,
                })

    if not rows:
        samples = {
            "59101": "Vator Nutricional Medio por 100g\nValor energético 868 kJ/206 kcal\nGrasas 7g\nHidratos de carbono <0.8g\nProteínas 35g\nSal 3.8g",
            "59280": "INFORMACIÓN NUTRICIONAL\nValores medios por\n100 g\nValor energético 1050 kJ/251 kcal\nGrasas 12.8 g\nHidratos de carbono <0.5 g\nProteínas 33.3 g\nSal 4.28 g",
        }
        for product_id, text in samples.items():
            parsed = read_nutrition_label(text, extraction_confidence=.98)
            if "MULTIPLE_NUTRITION_COLUMNS" in parsed.reasons:
                raise SystemExit(f"false multi-column blocker remains for fallback {product_id}")
            rows.append({
                "product_id": product_id,
                "origin": "captured_run_35745857558_observation",
                "status": parsed.status,
                "basis": parsed.basis,
                "reasons": list(parsed.reasons),
                "nutrition": parsed.nutrition,
            })

    summary = {
        "reader_version": READER_VERSION,
        "source_run_id": 35745857558,
        "products": sorted({str(r["product_id"]) for r in rows}),
        "rows_checked": len(rows),
        "false_multiple_column_blockers": sum(
            "MULTIPLE_NUTRITION_COLUMNS" in r["reasons"] for r in rows
        ),
        "rows": rows,
    }
    (VALIDATION_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    add_regression_tests()
    reproduce_regression()
    patch_reader()
    validate_tests()
    validate_observed_sample()


if __name__ == "__main__":
    main()
