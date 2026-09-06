from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mercadona_neural_ocr_alternate_photo_wave import (
    PILOT_ELIGIBILITY_MODE,
    _patch_outputs,
    _select_photo,
)


class AlternatePhotoWaveTest(unittest.TestCase):
    def setUp(self):
        self.selection = {
            "123": {"product_id": "123", "perspective": 3, "reason": "test"},
        }
        self.row = {
            "product_id": "123",
            "photos": [
                {"perspective": 2, "zoom": "https://example.invalid/p2.jpg"},
                {"perspective": 3, "zoom": "https://example.invalid/p3.jpg"},
            ],
        }

    def test_selects_only_explicit_perspective(self):
        index, photo = _select_photo(self.row, self.selection)
        self.assertEqual(index, 1)
        self.assertEqual(photo["perspective"], 3)

    def test_missing_selected_perspective_fails_closed(self):
        self.selection["123"]["perspective"] = 9
        with self.assertRaisesRegex(ValueError, "expected exactly one"):
            _select_photo(self.row, self.selection)

    def test_output_provenance_is_rewritten_to_actual_non_p9_photo(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            result = {
                "product_id": "123",
                "image_url": "https://example.invalid/p3.jpg",
                "image_index": 0,
                "perspective": 9,
                "eligibility_mode": "priority",
                "source": "MERCADONA_FIRST_PARTY",
                "source_record_kind": "label image",
                "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
                "redistribution_allowed": False,
                "status": "REVIEW",
            }
            (out / "results-00.jsonl").write_text(json.dumps(result) + "\n", encoding="utf-8")
            (out / "summary-00.json").write_text(json.dumps({"eligibility_mode": "priority"}), encoding="utf-8")
            metadata = {
                "https://example.invalid/p3.jpg": {
                    "product_id": "123",
                    "image_index": 1,
                    "perspective": 3,
                }
            }
            _patch_outputs(out, metadata, self.selection)
            patched = json.loads((out / "results-00.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(patched["perspective"], 3)
            self.assertEqual(patched["image_index"], 1)
            self.assertEqual(patched["eligibility_mode"], PILOT_ELIGIBILITY_MODE)
            self.assertFalse(patched["redistribution_allowed"])
            self.assertEqual(
                patched["evidence_level"],
                "OCR_DERIVED_FROM_MERCADONA_IMAGE",
            )
            self.assertEqual(patched["photo_selection"]["actual_perspective"], 3)


if __name__ == "__main__":
    unittest.main()
