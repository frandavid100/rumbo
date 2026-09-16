from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mercadona_incomplete_review_doctr_input import select_incomplete_review_rows


EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"


def row(product_id: str, nutrition: dict, *, corroborated: int = 3, families: int = 2, reasons=None, **extra):
    item = {
        "product_id": product_id,
        "ean": f"84{product_id}",
        "status": "REVIEW",
        "evidence_level": EVIDENCE,
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "redistribution_allowed": False,
        "image_url": f"https://prod-mercadona.img/{product_id}.jpg",
        "attempts": [
            {
                "ocr_count": 10,
                "ocr_full_text": "información nutricional",
                "ensemble": {
                    "nutrition": nutrition,
                    "basis": "100_g",
                    "corroborated_fields": corroborated,
                    "independent_engine_families": families,
                    "confidence": 0.92,
                    "reasons": list(reasons or []),
                },
            }
        ],
    }
    item.update(extra)
    return item


class MercadonaIncompleteReviewDocTRInputTest(unittest.TestCase):
    def write_rows(self, root: Path, run_id: int, rows: list[dict]) -> None:
        folder = root / f"{run_id}-123" / "unpacked"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "results.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in rows), encoding="utf-8"
        )

    def test_selects_only_clean_exact_three_core_frontier(self) -> None:
        three = {"calories": 100, "protein_g": 8, "carbohydrate_g": 12, "fat_g": None}
        complete = {"calories": 100, "protein_g": 8, "carbohydrate_g": 12, "fat_g": 2}
        two = {"calories": 100, "protein_g": 8, "carbohydrate_g": None, "fat_g": None}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_rows(root, 100, [row("p1", three)])
            self.write_rows(root, 100, [row("p2", three, reasons=["OCR_FIELD_CONFLICT:fat_g"])])
            self.write_rows(root, 100, [row("p3", complete, corroborated=3)])
            self.write_rows(root, 100, [row("p4", two, corroborated=3)])
            self.write_rows(root, 100, [row("p5", three, corroborated=2)])
            self.write_rows(root, 100, [row("p6", three, families=1)])
            summary = {
                "latest_status_counts": {"REVIEW": 6},
                "latest_status_product_ids": {"REVIEW": ["p1", "p2", "p3", "p4", "p5", "p6"]},
            }
            selected, audit = select_incomplete_review_rows(root, summary, limit=8)
            self.assertEqual([item["product_id"] for item in selected], ["p1"])
            self.assertEqual(selected[0]["missing_core_fields"], ["fat_g"])
            self.assertEqual(selected[0]["present_core_fields"], 3)
            self.assertEqual(audit["eligible_incomplete_frontier"], 1)
            self.assertFalse(audit["acceptance_policy_changed"])
            self.assertFalse(audit["cross_run_value_fusion_allowed"])
            self.assertFalse(audit["missing_values_inferred"])
            self.assertGreaterEqual(audit["rejection_counts"]["SAFETY_BLOCKED"], 1)
            self.assertGreaterEqual(audit["rejection_counts"]["NOT_EXACTLY_THREE_CORE_FIELDS"], 2)

    def test_derived_replay_does_not_replace_latest_raw_review(self) -> None:
        three = {"calories": 200, "protein_g": 10, "carbohydrate_g": 20, "fat_g": None}
        complete = {"calories": 200, "protein_g": 10, "carbohydrate_g": 20, "fat_g": 8}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_rows(root, 100, [row("p1", three)])
            derived = row(
                "p1",
                complete,
                status="DECLARED",
                replay={"status": "DECLARED"},
            )
            self.write_rows(root, 200, [derived])
            summary = {
                "latest_status_counts": {"REVIEW": 1},
                "latest_status_product_ids": {"REVIEW": ["p1"]},
            }
            selected, audit = select_incomplete_review_rows(root, summary, limit=8)
            self.assertEqual([item["product_id"] for item in selected], ["p1"])
            self.assertEqual(selected[0]["latest_raw_run_id"], 100)
            self.assertTrue(audit["excluded_derived_rows"])

    def test_order_is_deterministic_and_prefers_more_engine_families(self) -> None:
        three = {"calories": 50, "protein_g": 2, "carbohydrate_g": None, "fat_g": 1}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_rows(root, 100, [row("p2", three, families=2), row("p1", three, families=3)])
            summary = {
                "latest_status_counts": {"REVIEW": 2},
                "latest_status_product_ids": {"REVIEW": ["p1", "p2"]},
            }
            selected, _ = select_incomplete_review_rows(root, summary, limit=1)
            self.assertEqual([item["product_id"] for item in selected], ["p1"])


if __name__ == "__main__":
    unittest.main()
