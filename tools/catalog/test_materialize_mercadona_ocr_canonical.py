from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from materialize_mercadona_ocr_canonical import (
    EVIDENCE,
    SOURCE,
    build_canonical_rows,
    build_manifest,
    write_jsonl,
    write_sqlite,
)


N1 = {"calories": 100.0, "protein_g": 5.0, "carbohydrate_g": 10.0, "fat_g": 4.0}


def fixture_summary():
    return {
        "evidence_level": EVIDENCE,
        "canonical_status_products": 3,
        "latest_status_product_ids": {
            "DECLARED": ["1"],
            "REVIEW": ["2", "3"],
        },
        "latest_usable_complete": 1,
        "latest_usable_products": [
            {"product_id": "1", "latest_run_id": 20, "nutrition": N1},
        ],
        "runs": [
            {
                "run_id": 10,
                "workflow_names": ["pilot"],
                "new_product_ids": ["1", "2"],
                "overlap_product_ids": [],
            },
            {
                "run_id": 20,
                "workflow_names": ["wave"],
                "new_product_ids": ["3"],
                "overlap_product_ids": ["1", "2"],
            },
        ],
    }


class CanonicalMaterializationTests(unittest.TestCase):
    def test_review_never_carries_nutrition_and_every_usable_macro_has_strict_provenance(self):
        rows = build_canonical_rows(fixture_summary())
        by_id = {row["product_id"]: row for row in rows}

        self.assertTrue(by_id["1"]["usable_complete"])
        self.assertEqual(by_id["1"]["nutrition"], N1)
        self.assertEqual(by_id["1"]["latest_live_run_id"], 20)
        for field in ("calories", "protein_g", "carbohydrate_g", "fat_g"):
            self.assertEqual(by_id["1"]["nutrition_provenance"][field]["evidence_level"], EVIDENCE)
            self.assertEqual(by_id["1"]["nutrition_provenance"][field]["source"], SOURCE)
            self.assertFalse(by_id["1"]["nutrition_provenance"][field]["redistribution_allowed"])

        for product_id in ("2", "3"):
            self.assertFalse(by_id[product_id]["usable_complete"])
            self.assertIsNone(by_id[product_id]["nutrition"])
            self.assertIsNone(by_id[product_id]["nutrition_provenance"])

    def test_non_declared_usable_product_is_rejected(self):
        summary = fixture_summary()
        summary["latest_status_product_ids"] = {"REVIEW": ["1", "2", "3"]}
        with self.assertRaisesRegex(ValueError, "non-DECLARED"):
            build_canonical_rows(summary)

    def test_missing_chronological_locator_is_rejected(self):
        summary = fixture_summary()
        summary["runs"][-1]["new_product_ids"] = []
        with self.assertRaisesRegex(ValueError, "missing chronological run locator"):
            build_canonical_rows(summary)

    def test_jsonl_and_sqlite_have_identical_rows_and_sqlite_blocks_review_macros(self):
        rows = build_canonical_rows(fixture_summary())
        manifest = build_manifest(rows, 4280)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jsonl = root / "canonical.jsonl"
            db = root / "canonical.sqlite"
            write_jsonl(jsonl, rows)
            write_sqlite(db, rows, manifest)

            json_rows = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(json_rows), 3)
            self.assertEqual(sum(bool(row["usable_complete"]) for row in json_rows), 1)

            connection = sqlite3.connect(db)
            try:
                stored = connection.execute(
                    "SELECT product_id, status, usable_complete, calories FROM canonical_ocr ORDER BY product_id"
                ).fetchall()
                self.assertEqual(stored, [("1", "DECLARED", 1, 100.0), ("2", "REVIEW", 0, None), ("3", "REVIEW", 0, None)])
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE canonical_ocr SET calories = 1.0 WHERE product_id = '2'"
                    )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
