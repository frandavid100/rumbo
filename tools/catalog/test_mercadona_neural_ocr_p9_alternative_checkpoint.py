from __future__ import annotations

from collections import Counter
from urllib.error import HTTPError
import json
from pathlib import Path
import tempfile
import unittest

from mercadona_neural_ocr_p9_alternative import (
    _append_checkpoint,
    _download_with_retry,
    _write_progress,
)


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

    def test_download_retries_timeout_and_429_before_success(self) -> None:
        calls: list[int] = []
        delays: list[float] = []

        def downloader(url: str, path: Path, timeout: float) -> None:
            calls.append(len(calls) + 1)
            if len(calls) == 1:
                raise TimeoutError("read timed out")
            if len(calls) == 2:
                raise HTTPError(url, 429, "Too Many Requests", {"Retry-After": "0"}, None)
            path.write_bytes(b"image")

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "image.jpg"
            _download_with_retry(
                "https://example.test/image.jpg",
                target,
                timeout=20.0,
                attempts=4,
                backoff=0.5,
                downloader=downloader,
                sleeper=delays.append,
            )
            self.assertEqual(target.read_bytes(), b"image")

        self.assertEqual(calls, [1, 2, 3])
        self.assertEqual(delays, [0.5, 1.0])

    def test_download_does_not_retry_permanent_http_error(self) -> None:
        calls: list[int] = []
        delays: list[float] = []

        def downloader(url: str, path: Path, timeout: float) -> None:
            calls.append(1)
            raise HTTPError(url, 404, "Not Found", {}, None)

        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(HTTPError):
                _download_with_retry(
                    "https://example.test/missing.jpg",
                    Path(td) / "missing.jpg",
                    timeout=20.0,
                    attempts=4,
                    backoff=0.5,
                    downloader=downloader,
                    sleeper=delays.append,
                )

        self.assertEqual(calls, [1])
        self.assertEqual(delays, [])


if __name__ == "__main__":
    unittest.main()
