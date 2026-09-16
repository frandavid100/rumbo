from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from build_mercadona_review_replay_seeds import build_review_replay_seeds
from summarize_mercadona_ocr_run_union import EVIDENCE, SOURCE, SOURCE_RECORD_KIND


def _dt(day: int) -> datetime:
    return datetime(2026, 9, day, 12, 0, tzinfo=timezone.utc)


def _row(product_id: str, image: str, *, ean: str = "8410000000001", perspective=9, **extra):
    row = {
        "product_id": product_id,
        "ean": ean,
        "name": f"Product {product_id}",
        "category_id": "10",
        "category_name": "Test",
        "status": "REVIEW",
        "perspective": perspective,
        "image_url": image,
        "source": SOURCE,
        "source_record_kind": SOURCE_RECORD_KIND,
        "evidence_level": EVIDENCE,
        "redistribution_allowed": False,
    }
    row.update(extra)
    return row


def _summary(*ids: str):
    return {
        "latest_status_counts": {"REVIEW": len(ids)},
        "latest_status_product_ids": {"REVIEW": list(ids)},
    }


def _write_batch(root: Path, directory: str, rows):
    target = root / directory / "unpacked"
    target.mkdir(parents=True, exist_ok=True)
    (target / "results.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


class ReviewReplaySeedTests(unittest.TestCase):
    def test_uses_artifact_created_at_not_run_id_for_latest_raw_review(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            older = "https://prod-mercadona.imgix.net/images/older.jpg"
            newer = "https://prod-mercadona.imgix.net/images/newer.jpg"
            _write_batch(root, "20-200", [_row("1", older)])
            _write_batch(root, "10-100", [_row("1", newer)])
            chronology = {
                "20-200": (_dt(1), 20, 200),
                "10-100": (_dt(2), 10, 100),
            }

            seeds, summary = build_review_replay_seeds(root, _summary("1"), chronology)

            self.assertEqual(len(seeds), 1)
            self.assertEqual(seeds[0]["photos"][0]["zoom"], newer)
            self.assertEqual(seeds[0]["replay_seed_source"]["latest_raw_run_id"], 10)
            self.assertEqual(seeds[0]["replay_seed_source"]["latest_raw_artifact_id"], 100)
            self.assertEqual(summary["strict_p9_replay_seeds"], 1)
            self.assertNotIn("nutrition", seeds[0])

    def test_derived_newer_row_does_not_replace_raw_live_seed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = "https://prod-mercadona.imgix.net/images/raw.jpg"
            derived = "https://prod-mercadona.imgix.net/images/derived.jpg"
            _write_batch(root, "10-100", [_row("1", raw)])
            _write_batch(root, "11-110", [_row("1", derived, replay={"kind": "diagnostic"})])
            chronology = {
                "10-100": (_dt(1), 10, 100),
                "11-110": (_dt(2), 11, 110),
            }

            seeds, summary = build_review_replay_seeds(root, _summary("1"), chronology)

            self.assertEqual(len(seeds), 1)
            self.assertEqual(seeds[0]["photos"][0]["zoom"], raw)
            self.assertEqual(summary["excluded_derived_rows"]["DIAGNOSTIC_REPLAY_WRAPPER"], 1)

    def test_conflicting_latest_p9_identity_is_skipped_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_batch(
                root,
                "10-100",
                [
                    _row("1", "https://prod-mercadona.imgix.net/images/a.jpg"),
                    _row("1", "https://prod-mercadona.imgix.net/images/b.jpg"),
                ],
            )
            chronology = {"10-100": (_dt(1), 10, 100)}

            seeds, summary = build_review_replay_seeds(root, _summary("1"), chronology)

            self.assertEqual(seeds, [])
            self.assertEqual(summary["skip_counts"]["AMBIGUOUS_LATEST_P9_IDENTITY"], 1)
            self.assertEqual(summary["skip_product_ids"]["AMBIGUOUS_LATEST_P9_IDENTITY"], ["1"])

    def test_non_p9_and_non_mercadona_urls_are_not_replayable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_batch(
                root,
                "10-100",
                [
                    _row("1", "https://prod-mercadona.imgix.net/images/front.jpg", perspective=1),
                    _row("2", "https://example.com/back.jpg", perspective=9),
                ],
            )
            chronology = {"10-100": (_dt(1), 10, 100)}

            seeds, summary = build_review_replay_seeds(root, _summary("1", "2"), chronology)

            self.assertEqual(seeds, [])
            self.assertEqual(summary["skip_counts"]["NO_STRICT_P9_IDENTITY"], 2)

    def test_latest_raw_status_must_match_canonical_review(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            row = _row("1", "https://prod-mercadona.imgix.net/images/x.jpg")
            row["status"] = "DECLARED"
            _write_batch(root, "10-100", [row])
            chronology = {"10-100": (_dt(1), 10, 100)}

            with self.assertRaisesRegex(ValueError, "disagrees with canonical REVIEW"):
                build_review_replay_seeds(root, _summary("1"), chronology)


if __name__ == "__main__":
    unittest.main()
