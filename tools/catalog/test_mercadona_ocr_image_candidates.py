from __future__ import annotations

import unittest

from mercadona_ocr_image_candidates import (
    deterministic_shard_window,
    has_p9_zoom,
    non_p9_zoom_candidates,
    structured_ingredients_no_p9_candidate,
)


class MercadonaOCRImageCandidatesTest(unittest.TestCase):
    def test_p9_excludes_row_from_non_p9_expansion(self):
        row = {
            "ingredients": ["x"],
            "photos": [
                {"perspective": 2, "zoom": "https://example/2.jpg"},
                {"perspective": 9, "zoom": "https://example/9.jpg"},
            ],
        }
        self.assertTrue(has_p9_zoom(row))
        self.assertIsNone(structured_ingredients_no_p9_candidate(row))

    def test_requires_structured_ingredients(self):
        row = {"photos": [{"perspective": 10, "zoom": "https://example/10.jpg"}]}
        self.assertIsNone(structured_ingredients_no_p9_candidate(row))

    def test_prefers_explicit_perspective_order_without_rewriting_metadata(self):
        row = {
            "ingredients": ["x"],
            "photos": [
                {"perspective": 1, "zoom": "https://example/1.jpg"},
                {"perspective": 2, "zoom": "https://example/2.jpg"},
                {"perspective": 10, "zoom": "https://example/10.jpg"},
                {"perspective": 4, "zoom": "https://example/4.jpg"},
            ],
        }
        ordered = non_p9_zoom_candidates(row)
        self.assertEqual([10, 4, 2, 1], [photo["perspective"] for _index, photo in ordered])
        index, chosen = structured_ingredients_no_p9_candidate(row)
        self.assertEqual(2, index)
        self.assertEqual(10, chosen["perspective"])
        self.assertEqual("https://example/10.jpg", chosen["zoom"])

    def test_ignores_photos_without_zoom(self):
        row = {
            "ingredients": ["x"],
            "photos": [
                {"perspective": 10, "regular": "https://example/10.jpg"},
                {"perspective": 2, "zoom": "https://example/2.jpg"},
            ],
        }
        index, chosen = structured_ingredients_no_p9_candidate(row)
        self.assertEqual(1, index)
        self.assertEqual(2, chosen["perspective"])

    def test_shard_window_can_continue_after_a_pilot_prefix(self):
        selected = deterministic_shard_window(
            list(range(20)),
            shard_index=1,
            shard_count=4,
            skip_first=2,
            limit=2,
        )
        self.assertEqual([9, 13], selected)

    def test_shard_window_validates_bounds(self):
        with self.assertRaises(ValueError):
            deterministic_shard_window([1, 2], shard_index=2, shard_count=2)
        with self.assertRaises(ValueError):
            deterministic_shard_window([1, 2], shard_index=0, shard_count=2, skip_first=-1)


if __name__ == "__main__":
    unittest.main()
