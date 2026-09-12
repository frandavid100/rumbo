from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from extract_mercadona_ocr_identity_anchors import extract_identity_anchors


def row(product_id: str, ean: str | None, status: str = "REVIEW", **extra):
    base = {
        "product_id": product_id,
        "ean": ean,
        "status": status,
        "evidence_level": "OCR_DERIVED_FROM_MERCADONA_IMAGE",
        "source": "MERCADONA_FIRST_PARTY",
        "source_record_kind": "label image",
        "redistribution_allowed": False,
        "image_url": f"https://example.invalid/{product_id}.jpg",
        "nutrition": None,
    }
    base.update(extra)
    return base


class ExtractIdentityAnchorTests(unittest.TestCase):
    def write_run(self, root: Path, run_id: int, rows: list[dict]) -> None:
        d = root / f"{run_id}-1" / "unpacked"
        d.mkdir(parents=True)
        (d / "rows.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in rows), encoding="utf-8"
        )

    def test_earliest_raw_ean_is_anchor_and_later_reuse_is_diagnostic(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            self.write_run(root, 100, [row("42", "111")])
            self.write_run(root, 200, [row("42", "999")])
            anchors, summary = extract_identity_anchors(root)
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]["ean"], "111")
        self.assertEqual(anchors[0]["identity_conflict_run_ids"], [200])
        self.assertEqual(anchors[0]["identity_conflict_eans"], ["999"])
        self.assertEqual(summary["identity_conflict_product_ids"], ["42"])

    def test_derived_canonical_materialization_does_not_replace_anchor(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            self.write_run(root, 100, [row("7", "700")])
            self.write_run(root, 300, [row("7", "999", canonical_status_source="derived audit")])
            anchors, summary = extract_identity_anchors(root)
        self.assertEqual(anchors[0]["ean"], "700")
        self.assertEqual(summary["identity_conflict_products"], 0)

    def test_missing_earliest_ean_fails_closed(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            self.write_run(root, 100, [row("5", None)])
            self.write_run(root, 200, [row("5", "500")])
            anchors, summary = extract_identity_anchors(root)
        self.assertEqual(anchors, [])
        self.assertEqual(summary["identity_unresolved_product_ids"], ["5"])


if __name__ == "__main__":
    unittest.main()
