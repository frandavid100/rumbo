from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mercadona_review_regression_input import (
    build_live_input,
    recover_anchors,
    select_targets,
)


class MercadonaReviewRegressionInputTest(unittest.TestCase):
    def test_select_targets_ignores_canonical_excluded_derived_run(self) -> None:
        summary = {
            "latest_status_product_ids": {"REVIEW": ["p1"]},
            "declared_to_review_transition_audit": {
                "non_contradictory_review_product_ids": ["p1"]
            },
            "canonical_excluded_run_ids": [200],
            "runs": [
                {
                    "run_id": 100,
                    "new_product_ids": ["p1"],
                    "overlap_product_ids": [],
                },
                {
                    "run_id": 200,
                    "new_product_ids": [],
                    "overlap_product_ids": ["p1"],
                },
            ],
        }
        selected = select_targets(summary)
        self.assertEqual(selected["latest_raw_run_by_product"], {"p1": 100})
        self.assertTrue(selected["derived_or_replay_runs_excluded"])

    def test_recover_anchors_uses_only_expected_raw_run(self) -> None:
        selection = {
            "latest_raw_run_by_product": {"p1": 100},
        }
        valid = {
            "product_id": "p1",
            "status": "REVIEW",
            "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
            "source": "MERCADONA_FIRST_PARTY",
            "source_record_kind": "label image",
            "ean": "8412345678901",
            "image_url": "https://img.example/p1.jpg",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "100-1" / "unpacked"
            raw.mkdir(parents=True)
            (raw / "results.jsonl").write_text(json.dumps(valid) + "\n", encoding="utf-8")
            later = root / "999-2" / "unpacked"
            later.mkdir(parents=True)
            bad = dict(valid, ean="999")
            (later / "results.jsonl").write_text(json.dumps(bad) + "\n", encoding="utf-8")
            payload = recover_anchors(selection, root)
        self.assertEqual(payload["anchors"]["p1"]["ean"], "8412345678901")
        self.assertEqual(payload["anchors"]["p1"]["latest_raw_run_id"], 100)

    def test_live_input_requires_exact_ean_and_exact_perspective_9_url(self) -> None:
        anchor_doc = {
            "anchors": {
                "p1": {
                    "product_id": "p1",
                    "ean": "8412345678901",
                    "image_url": "https://img.example/p1-back.jpg",
                    "latest_raw_run_id": 100,
                },
                "p2": {
                    "product_id": "p2",
                    "ean": "8422222222222",
                    "image_url": "https://img.example/p2-back.jpg",
                    "latest_raw_run_id": 101,
                },
            }
        }
        rows = [
            {
                "product_id": "p1",
                "ean": "8412345678901",
                "ingredients": "x",
                "photos": [
                    {
                        "perspective": 9,
                        "zoom": "https://img.example/p1-back.jpg",
                    }
                ],
            },
            {
                "product_id": "p2",
                "ean": "8499999999999",
                "photos": [
                    {
                        "perspective": 9,
                        "zoom": "https://img.example/p2-back.jpg",
                    }
                ],
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "details.jsonl"
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            selected, summary = build_live_input(anchor_doc, path)
        self.assertEqual([row["product_id"] for row in selected], ["p1"])
        self.assertEqual(summary["reassigned_current_product_ids"], ["p2"])
        self.assertFalse(summary["acceptance_policy_changed"])
        self.assertFalse(summary["redistribution_allowed"])


if __name__ == "__main__":
    unittest.main()
