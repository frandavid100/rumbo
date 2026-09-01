from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

from mercadona_neural_ocr_p9_alternative import _append_checkpoint, _write_progress


class MercadonaAlternativeCheckpointTest(unittest.TestCase):
    def test_completed_rows_are_durable_before_final_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            results = root / "results-p2-s00.jsonl"
            progress = root / "progress-p2-s00.json"
            results.write_text("", encoding="utf-8")

            _append_checkpoint(results, {"product_id": "a", "status": "REVIEW"})
            _append_checkpoint(results, {"product_id": "b", "status": "DECLARED"})
            _write_progress(
                progress,
                required_perspective="2",
                eligible=100,
                selected=64,
                processed=2,
                status_counts=Counter({"REVIEW": 1, "DECLARED": 1}),
                skip_first=512,
                shard_index=0,
                shard_count=1,
            )

            rows = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["product_id"] for row in rows], ["a", "b"])
            payload = json.loads(progress.read_text(encoding="utf-8"))
            self.assertEqual(payload["processed"], 2)
            self.assertEqual(payload["selected"], 64)
            self.assertFalse(payload["complete"])
            self.assertFalse(payload["redistribution_allowed"])
            self.assertEqual(payload["CLASSIFIED"], 0)
            self.assertEqual(payload["MENU_ELIGIBLE"], 0)

    def test_progress_marks_complete_only_at_selected_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "progress.json"
            _write_progress(
                path,
                required_perspective="2",
                eligible=64,
                selected=64,
                processed=64,
                status_counts=Counter({"REVIEW": 64}),
                skip_first=512,
                shard_index=0,
                shard_count=1,
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(payload["complete"])
            self.assertEqual(payload["status_counts"], {"REVIEW": 64})


if __name__ == "__main__":
    unittest.main()
