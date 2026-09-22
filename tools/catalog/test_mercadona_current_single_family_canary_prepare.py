from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import mercadona_current_single_family_canary_prepare as prepare_mod


class CurrentSingleFamilyCanaryPrepareTests(unittest.TestCase):
    def _residual(self, root: Path, product_id: str = "18407") -> Path:
        path = root / "residual.jsonl"
        row = {
            "product_id": product_id,
            "name": "Example",
            "ean": "8480000184078",
            "image_url": "https://prod-mercadona.imgix.net/historical-p9.jpg",
            "canonical_status": "REVIEW",
            "basis": "100_g",
            "diagnostic_candidate_values": {
                "calories": 50,
                "fat_g": None,
                "carbohydrate_g": 0,
                "protein_g": 10.9,
            },
            "missing_core_fields": ["fat_g"],
            "safety_blockers": [],
            "independent_engine_families": 1,
            "corroborated_fields": 3,
            "latest_raw_run_id": 123,
        }
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def _live(photos: list[dict[str, str]]) -> dict[str, object]:
        return {
            "product_id": "18407",
            "ean": "8480000184078",
            "name": "Example",
            "photos": photos,
        }

    def _prepare(self, photos: list[dict[str, str]]):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            residual = self._residual(root)
            out = root / "out"
            live = self._live(photos)
            with (
                patch.object(prepare_mod, "_get_json", return_value=({"unused": True}, "https://api.example/product")),
                patch.object(prepare_mod, "normalize", return_value=live),
                patch.object(prepare_mod, "_now", return_value="2026-09-22T12:00:00Z"),
            ):
                products, summary = prepare_mod.prepare(
                    residual,
                    out,
                    limit_selected=3,
                    allow_unique_current_non_p9=True,
                )
            persisted = json.loads((out / "selection-summary.json").read_text(encoding="utf-8"))
            return products, summary, persisted

    def test_unique_non_p9_is_selected_only_when_no_unique_current_p9_exists(self):
        products, summary, persisted = self._prepare([
            {
                "perspective": "5",
                "zoom": "https://prod-mercadona.imgix.net/current-alt.jpg",
            }
        ])
        self.assertEqual(len(products), 1)
        self.assertEqual(len(products[0]["photos"]), 1)
        photo = products[0]["photos"][0]
        self.assertEqual(photo["perspective"], "5")
        self.assertTrue(photo[prepare_mod.PRESELECTED_FLAG])
        meta = products[0]["_exact_current_image_meta"]
        self.assertEqual(meta["image_url"], "https://prod-mercadona.imgix.net/current-alt.jpg")
        self.assertEqual(meta["current_photo_perspective"], "5")
        self.assertEqual(meta["image_identity_rule"], "EXACT_CURRENT_ONLY_NON_P9_ZOOM_WITHOUT_UNIQUE_P9")
        self.assertFalse(summary["image_guessing"])
        self.assertTrue(summary["allow_unique_current_non_p9"])
        self.assertEqual(persisted["selected_after_live_verification"][0]["perspective"], "5")

    def test_unique_non_p9_route_refuses_when_unique_current_p9_exists(self):
        products, summary, _ = self._prepare([
            {
                "perspective": "9",
                "zoom": "https://prod-mercadona.imgix.net/current-p9.jpg",
            },
            {
                "perspective": "5",
                "zoom": "https://prod-mercadona.imgix.net/current-alt.jpg",
            },
        ])
        self.assertEqual(products, [])
        reasons = [row["reason"] for row in summary["excluded_after_live_verification"]]
        self.assertIn("UNIQUE_CURRENT_P9_EXISTS_USE_P9_ROUTE", reasons)

    def test_unique_non_p9_route_refuses_multiple_alternatives(self):
        products, summary, _ = self._prepare([
            {
                "perspective": "4",
                "zoom": "https://prod-mercadona.imgix.net/a.jpg",
            },
            {
                "perspective": "5",
                "zoom": "https://prod-mercadona.imgix.net/b.jpg",
            },
        ])
        self.assertEqual(products, [])
        reasons = [row["reason"] for row in summary["excluded_after_live_verification"]]
        self.assertIn("UNIQUE_CURRENT_NON_P9_IMAGE_REQUIRED", reasons)

    def test_unique_non_p9_route_refuses_historical_url_reuse(self):
        products, summary, _ = self._prepare([
            {
                "perspective": "5",
                "zoom": "https://prod-mercadona.imgix.net/historical-p9.jpg",
            }
        ])
        self.assertEqual(products, [])
        reasons = [row["reason"] for row in summary["excluded_after_live_verification"]]
        self.assertIn("CURRENT_NON_P9_EQUALS_HISTORICAL_OCR_IMAGE", reasons)

    def test_mutually_exclusive_live_image_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            residual = self._residual(root)
            with self.assertRaises(ValueError):
                prepare_mod.prepare(
                    residual,
                    root / "out",
                    allow_changed_current_p9=True,
                    allow_unique_current_non_p9=True,
                )


if __name__ == "__main__":
    unittest.main()
