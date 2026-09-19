from __future__ import annotations

import unittest

import mercadona_neural_ocr_wave as base
import mercadona_preselected_current_image_variant_rescue as rescue


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
        hit = rescue._preselected_photo(row)
        self.assertIsNotNone(hit)
        assert hit is not None
        index, photo = hit
        self.assertEqual(index, 0)
        self.assertEqual(photo["perspective"], "5")
        self.assertTrue(rescue._eligible(row))

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
        self.assertIsNone(rescue._preselected_photo(row))
        self.assertFalse(rescue._eligible(row))

    def test_preselected_mode_fails_closed_with_multiple_flags(self):
        row = {
            "product_id": "123",
            "photos": [
                {
                    "perspective": "5",
                    "zoom": "https://prod-mercadona.imgix.net/a.jpg",
                    "_preselected_current_first_party_label_image": True,
                },
                {
                    "perspective": "6",
                    "zoom": "https://prod-mercadona.imgix.net/b.jpg",
                    "_preselected_current_first_party_label_image": True,
                },
            ],
        }
        self.assertIsNone(rescue._preselected_photo(row))
        self.assertFalse(rescue._eligible(row))

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
        self.assertFalse(base._eligible(row, "priority"))


if __name__ == "__main__":
    unittest.main()
