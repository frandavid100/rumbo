from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import mercadona_ambiguous_precision_rescue as precision


class PrecisionCropDiagnosticsTest(unittest.TestCase):
    def test_trace_preserves_extraction_result_and_records_each_crop_independently(self) -> None:
        readings = [("paddleocr", "paddleocr", object())]
        errors = {"tesseract-psm6": "fixture-error"}
        ensemble = object()
        original = Mock(return_value=(readings, errors, ensemble))
        sink = []

        with patch.object(precision.base, "_reading_payload", return_value={"status": "DECLARED"}), \
             patch.object(precision.base, "_ensemble_payload", return_value={"status": "REVIEW"}):
            result = precision._trace_extract_region(
                original,
                sink,
                object(),
                Path("primary-precision-left-42.png"),
                "visual_region",
            )

        self.assertEqual(result, (readings, errors, ensemble))
        self.assertEqual(len(sink), 1)
        self.assertEqual(sink[0]["variant"], "primary-precision-left-42.png")
        self.assertEqual(sink[0]["target_kind"], "visual_region")
        self.assertEqual(sink[0]["engine_errors"], errors)
        self.assertEqual(sink[0]["engines"]["paddleocr"], {"status": "DECLARED"})
        self.assertEqual(sink[0]["ensemble"], {"status": "REVIEW"})


if __name__ == "__main__":
    unittest.main()
