from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from audit_mercadona_current_review_failure_modes import build_audit


EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"


def raw_row(product_id: str, *, attempts: list[dict] | None = None, **extra) -> dict:
    row = {
        "product_id": product_id,
        "status": "REVIEW",
        "evidence_level": EVIDENCE,
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "redistribution_allowed": False,
        "image_url": f"https://prod-mercadona.img/{product_id}.jpg",
        "attempts": attempts or [],
    }
    row.update(extra)
    return row


def ensemble_attempt(
    *,
    nutrition: dict | None,
    corroborated_fields: int,
    families: int,
    basis: str = "100_g",
    reasons: list[str] | None = None,
    ocr_text: str = "información nutricional",
) -> dict:
    return {
        "ocr_count": 10 if ocr_text else 0,
        "ocr_full_text": ocr_text,
        "ensemble": {
            "nutrition": nutrition,
            "basis": basis,
            "corroborated_fields": corroborated_fields,
            "independent_engine_families": families,
            "confidence": 0.91,
            "reasons": reasons or [],
        },
    }


class CurrentReviewFailureModesTest(unittest.TestCase):
    def write_rows(self, root: Path, run_id: int, rows: list[dict]) -> None:
        folder = root / f"{run_id}-123" / "unpacked"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "results.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )

    def test_latest_raw_live_review_audit_is_conservative(self) -> None:
        complete = {"calories": 519, "protein_g": 13, "carbohydrate_g": 35, "fat_g": 39}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # p1 has a clean, fully corroborated diagnostic shape. It must remain REVIEW.
            self.write_rows(
                root,
                100,
                [raw_row("p1", attempts=[ensemble_attempt(nutrition=complete, corroborated_fields=4, families=2)])],
            )
            # A later replay wrapper must never replace the raw live status.
            self.write_rows(
                root,
                110,
                [
                    raw_row(
                        "p1",
                        status="DECLARED",
                        nutrition=complete,
                        replay={"status": "DECLARED"},
                    )
                ],
            )

            # p2 is complete but has a hard OCR conflict and therefore is safety blocked.
            self.write_rows(
                root,
                120,
                [
                    raw_row(
                        "p2",
                        attempts=[
                            ensemble_attempt(
                                nutrition=complete,
                                corroborated_fields=4,
                                families=3,
                                reasons=["OCR_FIELD_CONFLICT:fat_g"],
                            )
                        ],
                    )
                ],
            )

            # p3 has no usable extraction. A later canonical materialization is derived evidence
            # and must not update the latest raw observation.
            self.write_rows(root, 130, [raw_row("p3")])
            self.write_rows(
                root,
                140,
                [
                    raw_row(
                        "p3",
                        status="DECLARED",
                        nutrition=complete,
                        canonical_status_source="LATEST_RAW_LIVE_OCR_WINS",
                    )
                ],
            )

            summary = {
                "latest_status_counts": {"DECLARED": 0, "REVIEW": 3},
                "latest_status_product_ids": {"REVIEW": ["p1", "p2", "p3"]},
            }
            result, files = build_audit(root, summary)

            self.assertEqual(result["latest_review_products"], 3)
            self.assertEqual(result["latest_raw_review_rows"], 3)
            self.assertEqual(result["near_safe_complete_review"], 1)
            self.assertEqual(result["fully_corroborated_but_still_review"], 1)
            self.assertEqual(result["complete_but_safety_blocked"], 1)
            self.assertEqual(result["safety_blocker_counts"]["HARD_OCR_CONFLICT"], 1)
            self.assertEqual(result["products_without_ocr_signal"], 1)

            near = files["near-safe-complete-review"]
            self.assertEqual([row["product_id"] for row in near], ["p1"])
            self.assertEqual(near[0]["canonical_status"], "REVIEW")
            self.assertIsNone(near[0]["usable_nutrition"])
            self.assertFalse(near[0]["promotion_allowed"])
            self.assertEqual(near[0]["evidence_level"], EVIDENCE)
            self.assertFalse(near[0]["redistribution_allowed"])

            blocked = files["complete-but-safety-blocked"]
            self.assertEqual([row["product_id"] for row in blocked], ["p2"])

    def test_ambiguous_multiple_columns_blocks_safe_shape(self) -> None:
        complete = {"calories": 100, "protein_g": 10, "carbohydrate_g": 10, "fat_g": 2}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_rows(
                root,
                200,
                [
                    raw_row(
                        "p4",
                        attempts=[
                            ensemble_attempt(
                                nutrition=complete,
                                corroborated_fields=4,
                                families=2,
                                reasons=["MULTIPLE_NUTRITION_COLUMNS"],
                            )
                        ],
                    )
                ],
            )
            summary = {
                "latest_status_counts": {"REVIEW": 1},
                "latest_status_product_ids": {"REVIEW": ["p4"]},
            }
            result, files = build_audit(root, summary)
            self.assertEqual(result["near_safe_complete_review"], 0)
            self.assertEqual(result["safety_blocker_counts"]["AMBIGUOUS_TABLE"], 1)
            self.assertEqual([row["product_id"] for row in files["complete-but-safety-blocked"]], ["p4"])


if __name__ == "__main__":
    unittest.main()
