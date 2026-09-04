import unittest

from audit_mercadona_two_missing_pilot_results import audit


FIELDS = ("calories", "protein_g", "carbohydrate_g", "fat_g")


def baseline(product_id: str):
    return {
        "product_id": product_id,
        "basis": "100_g",
        "nutrition": {
            "calories": 100.0,
            "protein_g": 10.0,
            "carbohydrate_g": None,
            "fat_g": None,
        },
        "missing_core_fields": ["carbohydrate_g", "fat_g"],
    }


def declared(product_id: str):
    values = {
        "calories": 100.0,
        "protein_g": 10.0,
        "carbohydrate_g": 5.0,
        "fat_g": 4.0,
    }
    return {
        "product_id": product_id,
        "ean": f"ean-{product_id}",
        "name": f"product-{product_id}",
        "basis": "100_g",
        "perspective": "9",
        "status": "DECLARED",
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "redistribution_allowed": False,
        "nutrition": values,
        "attempts": [
            {
                "ensemble": {
                    "status": "DECLARED",
                    "independent_engine_families": 2,
                    "corroborated_fields": 4,
                    "reasons": [],
                    "fields": [
                        {
                            "name": field,
                            "corroborated": True,
                            "engine_families": ["paddleocr", "tesseract"],
                        }
                        for field in FIELDS
                    ],
                }
            }
        ],
    }


def cut(promotions):
    return {
        "closed_stratum": {"safe_promotions": len(promotions)},
        "promotions": [{"product_id": pid} for pid in promotions],
        "cumulative_after_closed_stratum": {
            "catalog_total": 4280,
            "processed": 2943,
            "DECLARED_complete": 265,
            "REVIEW": 2678,
        },
    }


class ReconciliationTests(unittest.TestCase):
    def test_already_counted_safe_reading_is_confirmation_not_new_promotion(self):
        summary, safe, novel = audit(
            [baseline("old")],
            {"candidate_universe": 1, "product_ids": ["old"]},
            [declared("old")],
            cut(["old"]),
            "cut.json",
        )
        self.assertEqual(1, len(safe))
        self.assertEqual([], novel)
        self.assertEqual(0, summary["novel_safe_promotion_products"])
        self.assertEqual(["old"], summary["already_counted_safe_promotion_product_ids"])
        self.assertEqual(265, summary["cumulative_after_pilot"]["DECLARED_complete"])
        self.assertEqual(2678, summary["cumulative_after_pilot"]["REVIEW"])
        self.assertEqual("VALIDATED", summary["safety_assessment"])

    def test_novel_safe_reading_advances_cumulative_once(self):
        summary, safe, novel = audit(
            [baseline("new")],
            {"candidate_universe": 1, "product_ids": ["new"]},
            [declared("new")],
            cut([]),
            "cut.json",
        )
        self.assertEqual(1, len(safe))
        self.assertEqual(["new"], [item["product_id"] for item in novel])
        self.assertEqual(1, summary["novel_safe_promotion_products"])
        self.assertEqual(266, summary["cumulative_after_pilot"]["DECLARED_complete"])
        self.assertEqual(2677, summary["cumulative_after_pilot"]["REVIEW"])

    def test_accounting_cut_must_balance_processed(self):
        bad = cut([])
        bad["cumulative_after_closed_stratum"]["REVIEW"] = 2677
        with self.assertRaises(ValueError):
            audit(
                [baseline("x")],
                {"candidate_universe": 1, "product_ids": ["x"]},
                [declared("x")],
                bad,
                "cut.json",
            )

    def test_preexisting_values_must_still_match_baseline(self):
        row = declared("x")
        row["nutrition"]["protein_g"] = 30.0
        summary, safe, novel = audit(
            [baseline("x")],
            {"candidate_universe": 1, "product_ids": ["x"]},
            [row],
            cut([]),
            "cut.json",
        )
        self.assertEqual([], safe)
        self.assertEqual([], novel)
        self.assertEqual("FAILED", summary["safety_assessment"])
        self.assertTrue(summary["value_conflicts"])


if __name__ == "__main__":
    unittest.main()
