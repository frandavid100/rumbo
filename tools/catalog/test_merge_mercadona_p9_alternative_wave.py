import tempfile
from pathlib import Path
import unittest

from merge_mercadona_p9_alternative_wave import (
    discover_input_paths,
    eligible_census_mismatches,
    expected_sample_count,
    summary_window_mismatches,
)


class ExpectedSampleCountTests(unittest.TestCase):
    def test_full_window_when_enough_eligible_rows_remain(self):
        self.assertEqual(expected_sample_count(1034, 48, 16), 16)

    def test_truncates_at_end_of_perspective_stratum(self):
        self.assertEqual(expected_sample_count(51, 48, 16), 3)

    def test_returns_zero_when_stratum_is_exhausted(self):
        self.assertEqual(expected_sample_count(48, 48, 16), 0)
        self.assertEqual(expected_sample_count(12, 48, 16), 0)


class DiscoverInputPathsTests(unittest.TestCase):
    def test_finds_same_named_shard_outputs_in_separate_artifact_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shard0 = root / "part0" / "results-p2.jsonl"
            shard1 = root / "part1" / "results-p2.jsonl"
            shard0.parent.mkdir(parents=True)
            shard1.parent.mkdir(parents=True)
            shard0.write_text('{"product_id":"a"}\n', encoding="utf-8")
            shard1.write_text('{"product_id":"b"}\n', encoding="utf-8")

            self.assertEqual(
                discover_input_paths(root, "results-*.jsonl"),
                [shard0, shard1],
            )

    def test_ignores_directories_matching_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "results-dir.jsonl").mkdir()
            result = root / "nested" / "results-p2.jsonl"
            result.parent.mkdir(parents=True)
            result.write_text('{}\n', encoding="utf-8")

            self.assertEqual(discover_input_paths(root, "results-*.jsonl"), [result])


class EligibleCensusMismatchTests(unittest.TestCase):
    expected = {"1": 1034, "2": 1367, "3": 122, "10": 51}

    def test_allows_omitted_exhausted_perspectives(self):
        processed = {"1": 32, "2": 32, "3": 0, "10": 0}
        observed = {"1": 1034, "2": 1367}
        self.assertEqual(
            eligible_census_mismatches(observed, self.expected, processed), []
        )

    def test_allows_intentionally_scoped_single_perspective(self):
        expected = {"1": 1034}
        processed = {"1": 32}
        observed = {"1": 1034}
        self.assertEqual(
            eligible_census_mismatches(observed, expected, processed), []
        )

    def test_scoped_merge_rejects_out_of_scope_perspective(self):
        expected = {"1": 1034}
        processed = {"1": 32}
        observed = {"1": 1034, "2": 1367}
        self.assertEqual(
            eligible_census_mismatches(observed, expected, processed),
            ["unexpected perspective p2"],
        )

    def test_requires_every_perspective_with_work_remaining(self):
        processed = {"1": 32, "2": 32, "3": 16, "10": 0}
        observed = {"1": 1034, "2": 1367}
        self.assertEqual(
            eligible_census_mismatches(observed, self.expected, processed),
            ["missing required perspective p3"],
        )

    def test_rejects_wrong_observed_census_even_for_exhausted_perspective(self):
        processed = {"1": 32, "2": 32, "3": 0, "10": 0}
        observed = {"1": 1034, "2": 1367, "10": 50}
        self.assertEqual(
            eligible_census_mismatches(observed, self.expected, processed),
            ["p10 observed eligible 50 != expected 51"],
        )

    def test_rejects_unexpected_perspective(self):
        processed = {"1": 32, "2": 32, "3": 0, "10": 0}
        observed = {"1": 1034, "2": 1367, "4": 9}
        self.assertEqual(
            eligible_census_mismatches(observed, self.expected, processed),
            ["unexpected perspective p4"],
        )


class SummaryWindowMismatchTests(unittest.TestCase):
    def test_accepts_contiguous_parallel_subwindows(self):
        summaries = [
            {
                "required_perspective": "2",
                "skip_first": skip,
                "selected": 16,
                "processed": 16,
            }
            for skip in (576, 592, 608, 624)
        ]
        self.assertEqual(
            summary_window_mismatches(
                summaries,
                expected_processed={"2": 64},
                base_skip_first=576,
            ),
            [],
        )

    def test_rejects_gap_between_parallel_subwindows(self):
        summaries = [
            {
                "required_perspective": "2",
                "skip_first": 576,
                "selected": 16,
                "processed": 16,
            },
            {
                "required_perspective": "2",
                "skip_first": 608,
                "selected": 16,
                "processed": 16,
            },
        ]
        errors = summary_window_mismatches(
            summaries,
            expected_processed={"2": 32},
            base_skip_first=576,
        )
        self.assertTrue(any("expected skip_first 592" in error for error in errors))

    def test_rejects_selected_processed_disagreement(self):
        summaries = [
            {
                "required_perspective": "2",
                "skip_first": 576,
                "selected": 16,
                "processed": 15,
            }
        ]
        errors = summary_window_mismatches(
            summaries,
            expected_processed={"2": 16},
            base_skip_first=576,
        )
        self.assertTrue(any("selected 16 != processed 15" in error for error in errors))

    def test_allows_missing_summary_for_exhausted_perspective(self):
        self.assertEqual(
            summary_window_mismatches(
                [],
                expected_processed={"10": 0},
                base_skip_first=64,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
