from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import mercadona_ambiguous_precision_rescue as precision


class PrecisionCropDiagnosticsTest(unittest.TestCase):
    def test_diagnostic_ratios_include_full_region_without_changing_production_defaults(self) -> None:
        self.assertEqual(
            precision.DIAGNOSTIC_PRIMARY_COLUMN_WIDTH_RATIOS,
            (0.42, 0.50, 0.56, 1.0),
        )
        self.assertEqual(
            precision.bounded.PRIMARY_COLUMN_WIDTH_RATIOS,
            (0.42, 0.50),
        )

    def test_trace_preserves_extraction_result_and_records_each_crop_independently(self) -> None:
        readings = [("paddleocr", "paddleocr", object())]
        errors = {"tesseract-psm6": "fixture-error"}
        ensemble = object()
        original = Mock(return_value=(readings, errors, ensemble))
        sink = []

        with patch.dict(os.environ, {}, clear=True), \
             patch.object(precision.base, "_reading_payload", return_value={"status": "DECLARED"}), \
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
        self.assertNotIn("independent_same_crop_probe", sink[0])

    def test_diagnostic_probe_is_observability_only(self) -> None:
        readings = [("paddleocr", "paddleocr", object())]
        errors = {}
        ensemble = object()
        original = Mock(return_value=(readings, errors, ensemble))
        sink = []
        probe = {
            "diagnostic_only": True,
            "same_crop_only": True,
            "cross_crop_value_fusion": False,
            "readings": {"diagnostic-doctr": {"status": "DECLARED"}},
            "ensembles": {"paddleocr+doctr": {"status": "DECLARED"}},
        }

        with patch.dict(
            os.environ,
            {"MERCADONA_PRECISION_DIAGNOSTICS": "diagnostics.json"},
            clear=True,
        ), patch.object(
            precision.base, "_reading_payload", return_value={"status": "REVIEW"}
        ), patch.object(
            precision.base, "_ensemble_payload", return_value={"status": "REVIEW"}
        ), patch.object(
            precision, "_diagnostic_independent_probe", return_value=probe
        ) as diagnostic_probe:
            result = precision._trace_extract_region(
                original,
                sink,
                object(),
                Path("primary-precision-left-50.png"),
                "visual_region",
            )

        self.assertEqual(result, (readings, errors, ensemble))
        self.assertIs(result[0], readings)
        self.assertIs(result[2], ensemble)
        diagnostic_probe.assert_called_once()
        self.assertEqual(sink[0]["independent_same_crop_probe"], probe)

    def test_non_precision_region_never_runs_independent_probe(self) -> None:
        original = Mock(return_value=([], {}, object()))
        sink = []
        with patch.dict(
            os.environ,
            {"MERCADONA_PRECISION_DIAGNOSTICS": "diagnostics.json"},
            clear=True,
        ), patch.object(
            precision.base, "_ensemble_payload", return_value={"status": "REVIEW"}
        ), patch.object(
            precision, "_diagnostic_independent_probe"
        ) as diagnostic_probe:
            precision._trace_extract_region(
                original,
                sink,
                object(),
                Path("visual-table-0.png"),
                "visual_region",
            )

        diagnostic_probe.assert_not_called()
        self.assertNotIn("independent_same_crop_probe", sink[0])


if __name__ == "__main__":
    unittest.main()
