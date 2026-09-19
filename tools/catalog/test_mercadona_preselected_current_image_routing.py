from __future__ import annotations

import unittest

import mercadona_neural_ocr_wave as wave


class PreselectedCurrentImageRoutingTests(unittest.TestCase):
    def test_routes_only_explicitly_preselected_current_first_party_image(self):
        row = {
            "product_id": "123",
            "ingredients": "agua",
            "photos": [
                {
                    "perspective": "5",
                    "zoom": "https://prod-mercadona.imgix.net/example.jpg",
                    "_preselected_current_first_party_label_image": True,
                },
                {
                    "perspective": "1",
                    "zoom": "https://prod-mercadona.imgix.net/front.jpg",
                },
            ],
        }
        hit = wave._photo_for_mode(row, "preselected-current-first-party-image")
        self.assertIsNotNone(hit)
        assert hit is not None
        index, photo = hit
        self.assertEqual(index, 0)
        self.assertEqual(photo["perspective"], "5")
        self.assertTrue(wave._eligible(row, "preselected-current-first-party-image"))

    def test_preselected_mode_fails_closed_without_flag(self):
        row = {
            "product_id": "123",
            "photos": [
                {
                    "perspective": "5",
                    "zoom": "https://prod-mercadona.imgix.net/example.jpg",
                }
            ],
        }
        self.assertIsNone(wave._photo_for_mode(row, "preselected-current-first-party-image"))
        self.assertFalse(wave._eligible(row, "preselected-current-first-party-image"))

    def test_existing_p9_modes_still_require_perspective_9(self):
        row = {
            "product_id": "123",
            "ingredients": "agua",
            "photos": [
                {
                    "perspective": "5",
                    "zoom": "https://prod-mercadona.imgix.net/example.jpg",
                    "_preselected_current_first_party_label_image": True,
                }
            ],
        }
        self.assertFalse(wave._eligible(row, "priority"))


if __name__ == "__main__":
    unittest.main()
