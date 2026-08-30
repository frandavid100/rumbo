import unittest

from merge_mercadona_p9_alternative_wave import expected_sample_count


class ExpectedSampleCountTests(unittest.TestCase):
    def test_full_window_when_enough_eligible_rows_remain(self):
        self.assertEqual(expected_sample_count(1034, 48, 16), 16)

    def test_truncates_at_end_of_perspective_stratum(self):
        self.assertEqual(expected_sample_count(51, 48, 16), 3)

    def test_returns_zero_when_stratum_is_exhausted(self):
        self.assertEqual(expected_sample_count(48, 48, 16), 0)
        self.assertEqual(expected_sample_count(12, 48, 16), 0)


if __name__ == "__main__":
    unittest.main()
