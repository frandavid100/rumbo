import unittest

from mercadona_current_p9_replacement import select_unique_current_p9


class CurrentP9ReplacementSelectorTest(unittest.TestCase):
    def test_selects_exactly_one_nonempty_current_p9(self):
        product = {
            "photos": [
                {"perspective": 1, "zoom": "https://example.test/front.jpg"},
                {"perspective": 9, "zoom": "https://example.test/label.jpg"},
            ]
        }
        index, photo, url = select_unique_current_p9(product)
        self.assertEqual(index, 1)
        self.assertEqual(photo["perspective"], 9)
        self.assertEqual(url, "https://example.test/label.jpg")

    def test_rejects_zero_current_p9(self):
        with self.assertRaisesRegex(ValueError, "CURRENT_P9_NOT_UNIQUE:0"):
            select_unique_current_p9({"photos": [{"perspective": 1, "zoom": "x"}]})

    def test_rejects_multiple_current_p9(self):
        with self.assertRaisesRegex(ValueError, "CURRENT_P9_NOT_UNIQUE:2"):
            select_unique_current_p9(
                {
                    "photos": [
                        {"perspective": 9, "zoom": "https://example.test/a.jpg"},
                        {"perspective": 9, "zoom": "https://example.test/b.jpg"},
                    ]
                }
            )

    def test_rejects_empty_p9_url(self):
        with self.assertRaisesRegex(ValueError, "CURRENT_P9_NOT_UNIQUE:0"):
            select_unique_current_p9({"photos": [{"perspective": 9, "zoom": ""}]})

    def test_rejects_same_url_reused_by_another_photo(self):
        with self.assertRaisesRegex(ValueError, "CURRENT_P9_URL_NOT_UNIQUE:2"):
            select_unique_current_p9(
                {
                    "photos": [
                        {"perspective": 9, "zoom": "https://example.test/label.jpg"},
                        {"perspective": 2, "zoom": "https://example.test/label.jpg"},
                    ]
                }
            )


if __name__ == "__main__":
    unittest.main()
