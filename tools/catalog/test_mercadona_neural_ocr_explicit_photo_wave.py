from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mercadona_neural_ocr_explicit_photo_wave import (
    ELIGIBILITY_MODE,
    PHOTO_SELECTION_POLICY,
    _patch_outputs,
    _select_photo,
)


class ExplicitPhotoWaveTest(unittest.TestCase):
    def setUp(self):
        self.selection = {
            "3529": {
                "product_id": "3529",
                "perspective": 10,
                "image_index": 1,
                "reason": "test duplicate-perspective disambiguation",
            }
        }
        self.row = {
            "product_id": "3529",
            "photos": [
                {"perspective": 2, "zoom": "https://example.invalid/0.jpg"},
                {"perspective": 10, "zoom": "https://example.invalid/1.jpg"},
                {"perspective": 2, "zoom": "https://example.invalid/2.jpg"},
                {"perspective": 10, "zoom": "https://example.invalid/3.jpg"},
            ],
        }

    def test_explicit_index_disambiguates_duplicate_perspective(self):
        index, photo = _select_photo(self.row, self.selection)
        self.assertEqual(index, 1)
        self.assertEqual(photo["zoom"], "https://example.invalid/1.jpg")

    def test_perspective_mismatch_fails_closed(self):
        self.selection["3529"]["perspective"] = 2
        with self.assertRaisesRegex(ValueError, "perspective mismatch"):
            _select_photo(self.row, self.selection)

    def test_out_of_range_index_fails_closed(self):
        self.selection["3529"]["image_index"] = 99
        with self.assertRaisesRegex(ValueError, "out of range"):
            _select_photo(self.row, self.selection)

    def test_output_provenance_preserves_explicit_index(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            result = {
                "product_id": "3529",
                "image_url": "https://example.invalid/1.jpg",
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
                "https://example.invalid/1.jpg": {
                    "product_id": "3529",
                    "image_index": 1,
                    "perspective": 10,
                }
            }
            _patch_outputs(out, metadata, self.selection)
            patched = json.loads((out / "results-00.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(patched["perspective"], 10)
            self.assertEqual(patched["image_index"], 1)
            self.assertEqual(patched["eligibility_mode"], ELIGIBILITY_MODE)
            self.assertEqual(patched["photo_selection"]["policy"], PHOTO_SELECTION_POLICY)
            self.assertEqual(patched["photo_selection"]["requested_image_index"], 1)
            self.assertEqual(patched["photo_selection"]["actual_image_index"], 1)
            self.assertFalse(patched["redistribution_allowed"])


if __name__ == "__main__":
    unittest.main()
