import unittest

from merge_mercadona_p9_alternative_wave import (
    eligible_census_mismatches,
    expected_sample_count,
)


class ExpectedSampleCountTests(unittest.TestCase):
    def test_full_window_when_enough_eligible_rows_remain(self):
        self.assertEqual(expected_sample_count(1034, 48, 16), 16)

    def test_truncates_at_end_of_perspective_stratum(self):
        self.assertEqual(expected_sample_count(51, 48, 16), 3)

    def test_returns_zero_when_stratum_is_exhausted(self):
        self.assertEqual(expected_sample_count(48, 48, 16), 0)
        self.assertEqual(expected_sample_count(12, 48, 16), 0)


class EligibleCensusMismatchTests(unittest.TestCase):
    expected = {"1": 1034, "2": 1367, "3": 122, "10": 51}

    def test_allows_omitted_exhausted_perspectives(self):
        processed = {"1": 32, "2": 32, "3": 0, "10": 0}
        observed = {"1": 1034, "2": 1367}
        self.assertEqual(
            eligible_census_mismatches(observed, self.expected, processed), []
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


if __name__ == "__main__":
    unittest.main()
