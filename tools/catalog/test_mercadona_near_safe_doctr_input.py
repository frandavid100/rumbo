import unittest

from mercadona_near_safe_doctr_input import build_live_inputs, select_near_safe_rows


VALUES = {
    "calories": 47.0,
    "fat_g": 0.7,
    "carbohydrate_g": 8.2,
    "protein_g": 1.6,
}


def diagnostic(pid: str, *, corroborated: int, blockers=None):
    return {
        "product_id": pid,
        "ean": f"84{pid}",
        "canonical_status": "REVIEW",
        "corroborated_fields": corroborated,
        "independent_engine_families": 3,
        "basis": "100_g",
        "diagnostic_candidate_values": dict(VALUES),
        "safety_blockers": list(blockers or []),
        "image_url": f"https://example.invalid/{pid}.jpg",
        "confidence": 0.95,
        "latest_raw_run_id": 123,
    }


class MercadonaNearSafeDocTRInputTest(unittest.TestCase):
    def test_three_of_four_is_prioritized_over_two_of_four_and_four_of_four_is_excluded(self):
        rows = [
            diagnostic("200", corroborated=2),
            diagnostic("300", corroborated=3),
            diagnostic("400", corroborated=4),
            diagnostic("500", corroborated=3, blockers=["conflicting_engine_values"]),
        ]
        selected, summary = select_near_safe_rows(rows, limit=8)
        self.assertEqual([row["product_id"] for row in selected], ["300", "200"])
        self.assertEqual(summary["selected_corroboration"], {"300": 3, "200": 2})
        self.assertIn("400", summary["rejected"])
        self.assertIn("NOT_TWO_OR_THREE_OF_FOUR", summary["rejected"]["400"])
        self.assertIn("SAFETY_BLOCKED", summary["rejected"]["500"])
        self.assertFalse(summary["acceptance_policy_changed"])

    def test_live_builder_requires_exact_ean_and_exact_current_image(self):
        selected = [
            diagnostic("100", corroborated=3),
            diagnostic("200", corroborated=2),
            diagnostic("300", corroborated=2),
        ]
        details = [
            {
                "product_id": "100",
                "ean": "84100",
                "ingredients": "avena",
                "photos": [
                    {"zoom": "https://example.invalid/100.jpg", "perspective": 9},
                    {"zoom": "https://example.invalid/front-100.jpg", "perspective": 1},
                ],
            },
            {
                "product_id": "200",
                "ean": "DIFFERENT",
                "photos": [{"zoom": "https://example.invalid/200.jpg", "perspective": 9}],
            },
            {
                "product_id": "300",
                "ean": "84300",
                "photos": [{"zoom": "https://example.invalid/replaced-300.jpg", "perspective": 9}],
            },
        ]
        accepted, summary = build_live_inputs(selected, details)
        self.assertEqual([row["product_id"] for row in accepted], ["100"])
        self.assertEqual(summary["reassigned_product_ids"], ["200"])
        self.assertEqual(summary["unmatched_current_first_party_photo"], ["300"])
        anchor = accepted[0]["_near_safe_anchor"]
        self.assertEqual(anchor["identity_basis"], "EXACT_CURRENT_EAN_MATCH")
        self.assertEqual(anchor["image_basis"], "EXACT_CURRENT_FIRST_PARTY_IMAGE_URL_MATCH")
        self.assertEqual(anchor["canonical_corroborated_fields"], 3)
        self.assertFalse(summary["acceptance_policy_changed"])


if __name__ == "__main__":
    unittest.main()
