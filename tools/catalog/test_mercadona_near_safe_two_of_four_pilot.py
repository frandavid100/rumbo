import json
from pathlib import Path
import tempfile
import unittest

from mercadona_near_safe_two_of_four_pilot import (
    build_deduplicated_two_of_four_candidates,
    load_previously_attempted_product_ids,
    should_run_two_of_four_variant_rescue,
)
from mercadona_near_safe_variant_rescue import _bounded_dissenting_family_rescue
from nutrition_label_reader import LabelReadResult, read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


class MercadonaNearSafeTwoOfFourPilotTest(unittest.TestCase):
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
            .60,
            ("MISSING_CORE:" + ",".join(missing),),
            "explicit partial OCR fixture",
        )

    def _fused(self, second_nutrition):
        return fuse_ocr_readings((
            ParsedOCRReading("paddleocr:visual_region", self._complete(), .98, "paddleocr"),
            ParsedOCRReading(
                "tesseract-psm6:visual_region",
                self._partial(second_nutrition),
                .95,
                "tesseract",
            ),
        ))

    def test_routes_clean_two_of_four_tuple(self):
        ensemble = self._fused({"calories": 150, "fat_g": 6.1})
        self.assertEqual(ensemble.status, "REVIEW")
        self.assertEqual(ensemble.corroborated_fields, 2)
        self.assertEqual(ensemble.independent_engine_families, 2)
        self.assertTrue(should_run_two_of_four_variant_rescue(ensemble))

    def test_does_not_expand_bounded_acceptance_to_two_of_four(self):
        readings = (
            ParsedOCRReading("paddleocr:visual_region", self._complete(), .98, "paddleocr"),
            ParsedOCRReading(
                "tesseract-psm6:visual_region",
                self._partial({"calories": 150, "fat_g": 6.1}),
                .95,
                "tesseract",
            ),
        )
        ensemble = fuse_ocr_readings(readings)
        self.assertEqual(ensemble.corroborated_fields, 2)
        self.assertIsNone(_bounded_dissenting_family_rescue(readings, ensemble))

    def test_does_not_retry_one_of_four(self):
        ensemble = self._fused({"calories": 150})
        self.assertLessEqual(ensemble.corroborated_fields, 1)
        self.assertFalse(should_run_two_of_four_variant_rescue(ensemble))

    def test_does_not_retry_cross_engine_conflict(self):
        ensemble = self._fused({"calories": 150, "fat_g": 20})
        self.assertEqual(ensemble.status, "REVIEW")
        self.assertTrue(any(r.startswith("OCR_FIELD_CONFLICT") for r in ensemble.reasons))
        self.assertFalse(should_run_two_of_four_variant_rescue(ensemble))

    def test_does_not_retry_three_of_four_stable_cohort(self):
        ensemble = self._fused({"calories": 150, "fat_g": 6.1, "carbohydrate_g": 20})
        self.assertEqual(ensemble.corroborated_fields, 3)
        self.assertFalse(should_run_two_of_four_variant_rescue(ensemble))

    def test_two_marker_text_is_not_used_as_a_parser_fixture(self):
        parsed = read_nutrition_label("""Información nutricional por 100 g
Valor energético 150 kcal
Grasas 6.1 g
""", extraction_confidence=.95)
        self.assertEqual(parsed.status, "NOT_NUTRITION_LABEL")
        self.assertIn("INSUFFICIENT_NUTRITION_MARKERS", parsed.reasons)

    def test_loads_attempted_ids_from_current_and_legacy_cut_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "wave1.json"
            second = root / "wave2.json"
            first.write_text(
                json.dumps({"selected_product_ids": ["100", 200]}),
                encoding="utf-8",
            )
            second.write_text(
                json.dumps({"selection": {"selected_product_ids": ["300", "100"]}}),
                encoding="utf-8",
            )
            self.assertEqual(
                load_previously_attempted_product_ids([first, second]),
                {"100", "200", "300"},
            )

    def test_attempted_id_loader_rejects_non_object_cut(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_previously_attempted_product_ids([path])

    def test_candidate_builder_excludes_attempted_and_keeps_exact_current_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diagnostic_path = root / "diagnostic.jsonl"
            product_path = root / "products.jsonl"
            diagnostics = []
            products = []
            for pid, confidence in (("100", .99), ("200", .95), ("300", .90)):
                diagnostics.append({
                    "product_id": pid,
                    "canonical_status": "REVIEW",
                    "corroborated_fields": 2,
                    "independent_engine_families": 2,
                    "basis": "100_g",
                    "diagnostic_candidate_values": {
                        "calories": 150,
                        "fat_g": 6.1,
                        "carbohydrate_g": 20,
                        "protein_g": 2.6,
                    },
                    "safety_blockers": [],
                    "image_url": f"https://example.invalid/{pid}.jpg",
                    "latest_raw_run_id": 42,
                    "confidence": confidence,
                })
                products.append({
                    "product_id": pid,
                    "ingredients": "x" if pid != "300" else None,
                    "photos": [{
                        "zoom": f"https://example.invalid/{pid}.jpg",
                        "perspective": 7,
                    }],
                })
            diagnostic_path.write_text(
                "".join(json.dumps(row) + "\n" for row in diagnostics),
                encoding="utf-8",
            )
            product_path.write_text(
                "".join(json.dumps(row) + "\n" for row in products),
                encoding="utf-8",
            )

            selected, summary = build_deduplicated_two_of_four_candidates(
                diagnostic_path,
                product_path,
                {"100"},
                limit=2,
            )
            self.assertEqual([row["product_id"] for row in selected], ["200", "300"])
            self.assertEqual(summary["excluded_previously_attempted_current_two_of_four"], ["100"])
            self.assertEqual(summary["selected_product_ids"], ["200", "300"])
            self.assertEqual(selected[0]["photos"][0]["perspective"], 9)
            self.assertEqual(selected[0]["_near_safe_image_meta"]["perspective"], 7)
            self.assertEqual(
                selected[0]["_near_safe_image_meta"]["image_url"],
                "https://example.invalid/200.jpg",
            )


if __name__ == "__main__":
    unittest.main()
