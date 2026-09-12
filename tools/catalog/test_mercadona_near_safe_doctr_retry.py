import json
from pathlib import Path
import tempfile
import unittest

from mercadona_near_safe_doctr_retry import (
    build_doctr_retry_candidates,
    should_run_doctr_rescue,
)
from nutrition_label_reader import LabelReadResult, read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


class MercadonaNearSafeDocTRRetryTest(unittest.TestCase):
    def _complete(self):
        parsed = read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
Hidratos de carbono 20 g
Proteínas 2.6 g
""", extraction_confidence=.98)
        self.assertEqual(parsed.status, "DECLARED")
        return parsed

    def _partial(self, nutrition):
        missing = [
            field
            for field in ("calories", "fat_g", "carbohydrate_g", "protein_g")
            if field not in nutrition
        ]
        return LabelReadResult(
            "REVIEW",
            "100_g",
            {key: float(value) for key, value in nutrition.items()},
            .95,
            ("MISSING_CORE:" + ",".join(missing),),
            "partial fixture",
        )

    def test_routes_clean_two_of_four_review(self):
        ensemble = fuse_ocr_readings((
            ParsedOCRReading("paddle", self._complete(), .98, "paddleocr"),
            ParsedOCRReading("tess", self._partial({"calories": 150, "fat_g": 6.1}), .95, "tesseract"),
        ))
        self.assertEqual(ensemble.corroborated_fields, 2)
        self.assertTrue(should_run_doctr_rescue(ensemble))

    def test_new_doctr_family_can_complete_existing_two_of_four_without_threshold_change(self):
        ensemble = fuse_ocr_readings((
            ParsedOCRReading("paddle", self._complete(), .98, "paddleocr"),
            ParsedOCRReading("tess", self._partial({"calories": 150, "fat_g": 6.1}), .95, "tesseract"),
            ParsedOCRReading("doctr", self._complete(), .96, "doctr"),
        ))
        self.assertTrue(ensemble.declared_usable)
        self.assertEqual(ensemble.corroborated_fields, 4)
        self.assertGreaterEqual(ensemble.independent_engine_families, 3)

    def test_cross_engine_conflict_is_not_routed(self):
        ensemble = fuse_ocr_readings((
            ParsedOCRReading("paddle", self._complete(), .98, "paddleocr"),
            ParsedOCRReading("tess", self._partial({"calories": 150, "fat_g": 20}), .95, "tesseract"),
        ))
        self.assertTrue(any(reason.startswith("OCR_FIELD_CONFLICT") for reason in ensemble.reasons))
        self.assertFalse(should_run_doctr_rescue(ensemble))

    def test_retry_candidate_builder_requires_exact_ean_and_current_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diagnostic = root / "diagnostic.jsonl"
            products = root / "products.jsonl"
            diagnostics = []
            product_rows = []
            for pid in ("100", "200"):
                diagnostics.append({
                    "product_id": pid,
                    "ean": f"84{pid}",
                    "canonical_status": "REVIEW",
                    "corroborated_fields": 2,
                    "independent_engine_families": 3,
                    "basis": "100_g",
                    "diagnostic_candidate_values": {
                        "calories": 150,
                        "fat_g": 6.1,
                        "carbohydrate_g": 20,
                        "protein_g": 2.6,
                    },
                    "safety_blockers": [],
                    "image_url": f"https://example.invalid/{pid}.jpg",
                    "confidence": .95,
                })
            product_rows.extend((
                {
                    "product_id": "100",
                    "ean": "84100",
                    "ingredients": "x",
                    "photos": [{"zoom": "https://example.invalid/100.jpg", "perspective": 9}],
                },
                {
                    "product_id": "200",
                    "ean": "84200",
                    "ingredients": "x",
                    "photos": [{"zoom": "https://example.invalid/replaced.jpg", "perspective": 9}],
                },
            ))
            diagnostic.write_text("".join(json.dumps(x) + "\n" for x in diagnostics), encoding="utf-8")
            products.write_text("".join(json.dumps(x) + "\n" for x in product_rows), encoding="utf-8")

            selected, summary = build_doctr_retry_candidates(diagnostic, products)
            self.assertEqual([row["product_id"] for row in selected], ["100"])
            self.assertEqual(summary["unmatched_current_first_party_photo"], ["200"])
            meta = selected[0]["_near_safe_image_meta"]
            self.assertEqual(meta["canonical_ean"], "84100")
            self.assertEqual(meta["current_ean"], "84100")
            self.assertEqual(meta["identity_basis"], "EXACT_CURRENT_EAN_MATCH")
            self.assertEqual(summary["new_independent_ocr_family"], "doctr")
            self.assertFalse(summary["acceptance_policy_changed"])

    def test_reassigned_product_id_is_excluded_even_if_image_url_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diagnostic = root / "diagnostic.jsonl"
            products = root / "products.jsonl"
            image = "https://example.invalid/shared.jpg"
            diagnostic.write_text(json.dumps({
                "product_id": "14031",
                "ean": "8480000140318",
                "canonical_status": "REVIEW",
                "corroborated_fields": 2,
                "independent_engine_families": 3,
                "basis": "100_g",
                "diagnostic_candidate_values": {
                    "calories": 150,
                    "fat_g": 6.1,
                    "carbohydrate_g": 20,
                    "protein_g": 2.6,
                },
                "safety_blockers": [],
                "image_url": image,
            }) + "\n", encoding="utf-8")
            products.write_text(json.dumps({
                "product_id": "14031",
                "ean": "8436039788039",
                "photos": [{"zoom": image, "perspective": 9}],
            }) + "\n", encoding="utf-8")

            selected, summary = build_doctr_retry_candidates(diagnostic, products)
            self.assertEqual(selected, [])
            self.assertEqual(summary["reassigned_current_product_ids"], ["14031"])
            self.assertEqual(summary["unmatched_current_first_party_photo"], [])


if __name__ == "__main__":
    unittest.main()
