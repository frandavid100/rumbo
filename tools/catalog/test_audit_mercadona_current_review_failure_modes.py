from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from audit_mercadona_current_review_failure_modes import build_audit
from nutrition_label_reader import LabelReadResult
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


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
    def write_rows(
        self,
        root: Path,
        run_id: int,
        rows: list[dict],
        *,
        artifact_id: int = 123,
    ) -> None:
        folder = root / f"{run_id}-{artifact_id}" / "unpacked"
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

    def test_artifact_created_at_beats_numeric_run_id_for_latest_review(self) -> None:
        """Rerun/run numbering must not disagree with canonical artifact chronology.

        Reproduces the 84638 regression: an earlier DECLARED artifact can have a
        numerically larger workflow run id than a later REVIEW artifact. The
        failure-mode audit must select the later persisted artifact, exactly like
        canonical reconciliation, instead of failing or reviving older nutrition.
        """
        complete = {"calories": 100, "protein_g": 10, "carbohydrate_g": 10, "fat_g": 2}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_rows(
                root,
                35417093808,
                [raw_row("84638", status="DECLARED", nutrition=complete)],
                artifact_id=10576537292,
            )
            self.write_rows(
                root,
                35417093754,
                [raw_row("84638", attempts=[ensemble_attempt(nutrition=None, corroborated_fields=0, families=0)])],
                artifact_id=10576348311,
            )
            summary = {
                "latest_status_counts": {"DECLARED": 0, "REVIEW": 1},
                "latest_status_product_ids": {"REVIEW": ["84638"]},
            }
            chronology = {
                "35417093808-10576537292": "2026-09-19T03:04:21Z",
                "35417093754-10576348311": "2026-09-19T03:16:03Z",
            }

            result, files = build_audit(root, summary, artifact_created_at=chronology)

            self.assertEqual(result["chronology_mode"], "GITHUB_ARTIFACT_CREATED_AT")
            self.assertEqual(result["latest_review_products"], 1)
            self.assertEqual(files["reasonless-review"][0]["latest_raw_run_id"], 35417093754)

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

    def test_three_of_four_explicit_basis_unblocked_is_retry_only(self) -> None:
        three = {"calories": 100, "protein_g": 10, "carbohydrate_g": 10, "fat_g": None}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_rows(
                root,
                300,
                [raw_row("p5", ean="123", attempts=[ensemble_attempt(nutrition=three, corroborated_fields=3, families=3)])],
            )
            self.write_rows(
                root,
                301,
                [raw_row("p6", ean="456", attempts=[ensemble_attempt(nutrition=three, corroborated_fields=3, families=2, basis="serving")])],
            )
            self.write_rows(
                root,
                302,
                [
                    raw_row(
                        "p7",
                        ean="789",
                        attempts=[
                            ensemble_attempt(
                                nutrition=three,
                                corroborated_fields=3,
                                families=2,
                                reasons=["OCR_FIELD_CONFLICT:fat_g"],
                            )
                        ],
                    )
                ],
            )
            summary = {
                "latest_status_counts": {"REVIEW": 3},
                "latest_status_product_ids": {"REVIEW": ["p5", "p6", "p7"]},
            }
            result, files = build_audit(root, summary)

            self.assertEqual(result["three_of_four_explicit_basis_unblocked_review"], 1)
            self.assertEqual(result["three_of_four_missing_field_counts"], {"fat_g": 1})
            self.assertEqual(result["three_of_four_engine_family_counts"], {"3": 1})
            candidates = files["three-of-four-explicit-basis-unblocked-review"]
            self.assertEqual([row["product_id"] for row in candidates], ["p5"])
            self.assertEqual(candidates[0]["missing_core_fields"], ["fat_g"])
            self.assertIsNone(candidates[0]["usable_nutrition"])
            self.assertFalse(candidates[0]["promotion_allowed"])
            self.assertFalse(candidates[0]["missing_values_inferred"])
            self.assertEqual(candidates[0]["diagnostic_candidate_values"]["fat_g"], None)

    def test_bounded_core_value_is_not_a_retry_candidate(self) -> None:
        """Known printed inequalities must not be retried as generic OCR omissions."""
        three = {"calories": 327, "protein_g": 4.89, "carbohydrate_g": 76, "fat_g": None}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_rows(
                root,
                303,
                [
                    raw_row(
                        "86288",
                        ean="8421691803071",
                        attempts=[
                            ensemble_attempt(
                                nutrition=three,
                                corroborated_fields=3,
                                families=3,
                                reasons=[
                                    "OCR_BOUNDED_CORE_VALUE:fat_g:easyocr,paddleocr,tesseract",
                                    "MISSING_CORE:fat_g",
                                ],
                            )
                        ],
                    )
                ],
            )
            summary = {
                "latest_status_counts": {"REVIEW": 1},
                "latest_status_product_ids": {"REVIEW": ["86288"]},
            }

            result, files = build_audit(root, summary)

            self.assertEqual(result["three_of_four_explicit_basis_unblocked_review"], 0)
            self.assertEqual(result["three_of_four_bounded_core_review"], 1)
            self.assertEqual(result["three_of_four_bounded_missing_field_counts"], {"fat_g": 1})
            self.assertEqual(result["safety_blocker_counts"]["NON_EXACT_BOUNDED_CORE"], 1)
            self.assertEqual(files["three-of-four-explicit-basis-unblocked-review"], [])
            bounded = files["three-of-four-bounded-core-review"]
            self.assertEqual([row["product_id"] for row in bounded], ["86288"])
            self.assertIn("NON_EXACT_BOUNDED_CORE", bounded[0]["safety_blockers"])
            self.assertIsNone(bounded[0]["usable_nutrition"])
            self.assertFalse(bounded[0]["promotion_allowed"])

    def test_bounded_core_value_cannot_be_promoted_by_other_ocr_families(self) -> None:
        """A printed `<1.0 g` is a bound, never an exact 1.0 g observation.

        This reproduces the current Mercadona 34605 failure mode: one OCR family
        preserves the inequality while two others can lose the `<` glyph and
        otherwise agree on a complete, energy-coherent tuple. Precision wins;
        the ensemble must keep the field in REVIEW instead of manufacturing an
        exact protein value from two correlated OCR mistakes.
        """
        partial = {"calories": 342.0, "fat_g": 1.4, "carbohydrate_g": 79.0}
        exact = {**partial, "protein_g": 1.0}
        bounded_text = """Información nutricional por 100 g
Valor energético 342 kcal
Grasas 1.4 g
Hidratos de carbono 79 g
Proteínas
<1.0 g
"""
        exact_text = bounded_text.replace("<1.0 g", "1.0 g")
        bounded = LabelReadResult(
            "REVIEW", "100_g", partial, .95,
            ("MISSING_CORE:protein_g",), bounded_text,
        )
        paddle = LabelReadResult("REVIEW", "100_g", exact, .96, tuple(), exact_text)
        tesseract = LabelReadResult("REVIEW", "100_g", exact, .94, tuple(), exact_text)

        result = fuse_ocr_readings([
            ParsedOCRReading("easyocr", bounded, engine_family="easyocr"),
            ParsedOCRReading("paddleocr", paddle, engine_family="paddleocr"),
            ParsedOCRReading("tesseract-psm6", tesseract, engine_family="tesseract"),
        ])

        self.assertEqual(result.status, "REVIEW", result)
        self.assertIsNone((result.nutrition or {}).get("protein_g"), result)
        self.assertTrue(
            any(reason.startswith("OCR_BOUNDED_CORE_VALUE:protein_g") for reason in result.reasons),
            result,
        )


if __name__ == "__main__":
    unittest.main()
