from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import mercadona_current_canary_finalize as finalize_mod


class CurrentCanaryFinalizeTests(unittest.TestCase):
    @staticmethod
    def _write_case(root: Path, *, perspective: str, identity_rule: str | None) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "ocr").mkdir(parents=True, exist_ok=True)
        meta = {
            "image_url": "https://prod-mercadona.imgix.net/current.jpg",
            "current_photo_index": 0,
            "current_photo_perspective": perspective,
            "canonical_ean": "8480000184078",
            "current_ean": "8480000184078",
            "identity_basis": "EXACT_NONEMPTY_CANONICAL_EAN_EQUALS_CURRENT_FIRST_PARTY_EAN",
            "image_selection_basis": "TEST",
            "live_detail_source_url": "https://tienda.mercadona.es/api/products/18407/",
            "live_detail_observed_at": "2026-09-22T12:00:00Z",
        }
        if identity_rule is not None:
            meta["image_identity_rule"] = identity_rule
        product = {
            "product_id": "18407",
            "_exact_current_image_meta": meta,
        }
        result = {
            "product_id": "18407",
            "status": "REVIEW",
            "image_url": "https://prod-mercadona.imgix.net/current.jpg",
            "source": "MERCADONA_FIRST_PARTY",
            "source_record_kind": "label image",
            "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
            "redistribution_allowed": False,
            "nutrition": None,
        }
        (root / "products.jsonl").write_text(json.dumps(product) + "\n", encoding="utf-8")
        (root / "ocr" / "results-00000.jsonl").write_text(json.dumps(result) + "\n", encoding="utf-8")

    def test_accepts_explicit_unique_current_non_p9_identity_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_case(
                root,
                perspective="5",
                identity_rule="EXACT_CURRENT_ONLY_NON_P9_ZOOM_WITHOUT_UNIQUE_P9",
            )
            summary = finalize_mod.finalize(root)
            self.assertEqual(summary["processed"], 1)
            self.assertEqual(
                summary["image_identity_rule"],
                "EXACT_CURRENT_ONLY_NON_P9_ZOOM_WITHOUT_UNIQUE_P9",
            )
            self.assertEqual(
                summary["image_identity_rules"],
                ["EXACT_CURRENT_ONLY_NON_P9_ZOOM_WITHOUT_UNIQUE_P9"],
            )
            row = json.loads((root / "results-merged.jsonl").read_text(encoding="utf-8").strip())
            self.assertEqual(row["perspective"], "5")
            self.assertEqual(
                row["image_identity_rule"],
                "EXACT_CURRENT_ONLY_NON_P9_ZOOM_WITHOUT_UNIQUE_P9",
            )

    def test_legacy_missing_identity_rule_remains_p9_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_case(root, perspective="5", identity_rule=None)
            with self.assertRaises(SystemExit):
                finalize_mod.finalize(root)

    def test_non_p9_identity_rule_rejects_perspective_9(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_case(
                root,
                perspective="9",
                identity_rule="EXACT_CURRENT_ONLY_NON_P9_ZOOM_WITHOUT_UNIQUE_P9",
            )
            with self.assertRaises(SystemExit):
                finalize_mod.finalize(root)


if __name__ == "__main__":
    unittest.main()
