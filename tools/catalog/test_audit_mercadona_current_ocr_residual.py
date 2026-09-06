from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from audit_mercadona_current_ocr_residual import (
    OCR_EVIDENCE,
    audit,
    collect_processed,
    ocr_scope_profile,
    p9_photo,
    residual_profile,
)


def row(
    product_id: str,
    *,
    p9: bool,
    ingredients=None,
    legal_name=None,
    allergens=None,
    packaging=None,
    unit_size=None,
    top_category="Test",
    subcategory=None,
):
    category_path = [{"name": top_category}]
    if subcategory:
        category_path.append({"name": subcategory})
    return {
        "product_id": product_id,
        "name": f"Product {product_id}",
        "ingredients": ingredients,
        "legal_name": legal_name,
        "allergens": allergens,
        "packaging": packaging,
        "unit_size": unit_size,
        "category_path": category_path,
        "photos": ([{"perspective": "9", "zoom": f"https://example.invalid/{product_id}.jpg"}] if p9 else []),
    }


class ResidualProfileTests(unittest.TestCase):
    def test_profiles_are_conservative_first_party_routing_only(self):
        self.assertEqual(residual_profile(row("1", p9=False)), "NO_P9")
        self.assertEqual(residual_profile(row("2", p9=True, ingredients=[{"text": "x"}])), "P9_STRUCTURED_INGREDIENTS")
        self.assertEqual(residual_profile(row("3", p9=True, legal_name="food")), "P9_NO_INGREDIENTS_FOOD_SIGNAL")
        self.assertEqual(residual_profile(row("4", p9=True, allergens=["milk"])), "P9_NO_INGREDIENTS_FOOD_SIGNAL")
        self.assertEqual(residual_profile(row("5", p9=True, packaging="bag", unit_size=100)), "P9_NO_INGREDIENTS_PACKAGED_SIGNAL")
        self.assertEqual(residual_profile(row("6", p9=True)), "P9_NO_INGREDIENTS_OTHER")

    def test_p9_requires_zoom_url(self):
        value = row("1", p9=True)
        value["photos"][0]["zoom"] = None
        self.assertIsNone(p9_photo(value))


class OcrOperationalScopeTests(unittest.TestCase):
    def test_core_grocery_p9_without_structured_signal_remains_actionable(self):
        value = row(
            "1",
            p9=True,
            packaging="Bolsa",
            unit_size=100,
            top_category="Aperitivos",
        )
        self.assertEqual(ocr_scope_profile(value), "ACTIONABLE_P9_CORE_GROCERY_CATEGORY")

    def test_first_party_food_signal_in_mixed_category_remains_actionable(self):
        value = row(
            "1",
            p9=True,
            legal_name="Preparado alimenticio",
            top_category="Bebé",
        )
        self.assertEqual(ocr_scope_profile(value), "ACTIONABLE_P9_FIRST_PARTY_FOOD_SIGNAL")

    def test_packaging_alone_does_not_make_non_food_actionable(self):
        value = row(
            "1",
            p9=True,
            packaging="Caja",
            unit_size=20,
            top_category="Limpieza y hogar",
        )
        self.assertEqual(ocr_scope_profile(value), "OUT_OF_SCOPE_NON_FOOD_OR_MIXED")

    def test_bodega_is_explicitly_deferred_even_with_p9(self):
        value = row(
            "1",
            p9=True,
            packaging="Botella",
            unit_size=1,
            top_category="Bodega",
        )
        self.assertEqual(ocr_scope_profile(value), "DEFERRED_BODEGA")

    def test_non_food_subcategory_inside_food_top_level_is_excluded(self):
        value = row(
            "1",
            p9=True,
            packaging="Paquete",
            unit_size=1,
            top_category="Panadería y pastelería",
            subcategory="Velas y decoración",
        )
        self.assertEqual(ocr_scope_profile(value), "OUT_OF_SCOPE_NON_FOOD_SUBCATEGORY")

    def test_core_grocery_without_p9_is_reported_blocked_not_actionable(self):
        value = row("1", p9=False, top_category="Fruta y verdura")
        self.assertEqual(ocr_scope_profile(value), "BLOCKED_NO_P9_FOOD_ROUTE")


class ProcessedUnionTests(unittest.TestCase):
    def test_collect_processed_deduplicates_artifact_families_and_keeps_status_history_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "run-a" / "unpacked" / "first.jsonl"
            second = root / "run-b" / "unpacked" / "second.jsonl"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_text(
                "\n".join(
                    json.dumps(item)
                    for item in (
                        {"product_id": "100", "status": "REVIEW", "evidence_level": OCR_EVIDENCE},
                        {"product_id": "200", "status": "ERROR", "evidence_level": OCR_EVIDENCE},
                        {"product_id": "ignored", "status": "REVIEW", "evidence_level": "OTHER"},
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            second.write_text(
                "\n".join(
                    json.dumps(item)
                    for item in (
                        {"product_id": "100", "status": "DECLARED", "evidence_level": OCR_EVIDENCE},
                        {"product_id": "200", "status": "REVIEW", "evidence_level": OCR_EVIDENCE},
                        {"product_id": "300", "status": "ERROR", "evidence_level": OCR_EVIDENCE},
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            processed, sources, statuses = collect_processed(root)

        self.assertEqual(processed, {"100", "200", "300"})
        self.assertEqual(len(sources["100"]), 2)
        self.assertEqual(len(sources["200"]), 2)
        self.assertEqual(len(sources["300"]), 1)
        self.assertEqual(statuses["MULTIPLE_HISTORICAL_STATUSES"], 2)
        self.assertEqual(statuses["ERROR"], 1)
        self.assertNotIn("ignored", processed)

    def test_audit_rejects_wrong_processed_union_before_routing(self):
        products = [row(str(i), p9=False) for i in range(4280)]
        with self.assertRaisesRegex(ValueError, "expected 3 distinct processed"):
            audit(products, {"0", "1"}, expected_processed=3)

    def test_audit_routes_only_unprocessed_p9_and_materializes_no_p9_residual(self):
        products = [row(str(i), p9=False) for i in range(4280)]
        products[7] = row("7", p9=True, ingredients=[{"text": "x"}])
        products[8] = row(
            "8",
            p9=True,
            packaging="bag",
            unit_size=100,
            top_category="Aperitivos",
        )
        residual_rows, summary = audit(products, {"7"}, expected_processed=1)
        self.assertEqual([item["product_id"] for item in residual_rows], ["8"])
        self.assertEqual(summary["p9_residual_total"], 1)
        self.assertEqual(summary["residual_profiles"]["P9_NO_INGREDIENTS_PACKAGED_SIGNAL"], 1)
        self.assertEqual(summary["ocr_actionable_p9_total"], 1)
        self.assertEqual(summary["ocr_actionable_p9_product_ids"], ["8"])
        self.assertEqual(summary["no_p9_residual_total"], 4278)
        self.assertEqual(len(summary["no_p9_residual_product_ids"]), 4278)
        self.assertEqual(len(summary["_no_p9_rows"]), 4278)
        self.assertEqual(summary["_no_p9_rows"][0]["source"], "MERCADONA_FIRST_PARTY/label image candidate")
        self.assertFalse(summary["_no_p9_rows"][0]["redistribution_allowed"])
        self.assertEqual(summary["CLASSIFIED"], 0)
        self.assertEqual(summary["MENU_ELIGIBLE"], 0)


if __name__ == "__main__":
    unittest.main()
