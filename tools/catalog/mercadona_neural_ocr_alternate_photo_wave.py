from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import mercadona_neural_ocr_wave as base


PILOT_ELIGIBILITY_MODE = "alternate-photo-no-p9-packaged-pilot"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _selection_by_product(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(path)
    rows = payload.get("products") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("selection must contain a products list")
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("selection entries must be objects")
        pid = str(row.get("product_id") or "")
        if not pid or "perspective" not in row:
            raise ValueError("selection entries require product_id and perspective")
        if pid in out:
            raise ValueError(f"duplicate selection for product {pid}")
        out[pid] = row
    return out


def _select_photo(
    row: dict[str, Any],
    selection: dict[str, dict[str, Any]],
) -> tuple[int, dict[str, Any]] | None:
    pid = str(row.get("product_id") or "")
    wanted = selection.get(pid)
    if wanted is None:
        return None
    target = str(wanted["perspective"])
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    matches = [
        (index, photo)
        for index, photo in enumerate(photos)
        if isinstance(photo, dict)
        and str(photo.get("perspective")) == target
        and photo.get("zoom")
    ]
    if len(matches) != 1:
        raise ValueError(
            f"product {pid}: expected exactly one zoom photo for perspective {target}, got {len(matches)}"
        )
    return matches[0]


def _patch_outputs(
    out: Path,
    url_metadata: dict[str, dict[str, Any]],
    selection: dict[str, dict[str, Any]],
) -> None:
    for path in out.glob("results-*.jsonl"):
        patched = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            image_url = str(row.get("image_url") or "")
            meta = url_metadata.get(image_url)
            if meta is None:
                raise ValueError(f"result references unregistered image URL: {image_url}")
            pid = str(row.get("product_id") or "")
            if pid not in selection:
                raise ValueError(f"unexpected product in alternate-photo pilot: {pid}")
            row["perspective"] = meta["perspective"]
            row["image_index"] = meta["image_index"]
            row["eligibility_mode"] = PILOT_ELIGIBILITY_MODE
            row["photo_selection"] = {
                "policy": "EXPLICIT_NON_P9_FIRST_PARTY_PHOTO",
                "requested_perspective": selection[pid]["perspective"],
                "actual_perspective": meta["perspective"],
                "reason": selection[pid].get("reason"),
            }
            patched.append(row)
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in patched),
            encoding="utf-8",
        )

    for path in out.glob("summary-*.json"):
        summary = _load_json(path)
        summary["eligibility_mode"] = PILOT_ELIGIBILITY_MODE
        summary["photo_selection_policy"] = "EXPLICIT_NON_P9_FIRST_PARTY_PHOTO"
        summary["selection_products"] = len(selection)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--selection", required=True)
    known, remaining = ap.parse_known_args()

    base_args = argparse.ArgumentParser(add_help=False)
    base_args.add_argument("--products", required=True)
    base_args.add_argument("--out", required=True)
    parsed_base, _ = base_args.parse_known_args(remaining)

    selection = _selection_by_product(Path(known.selection))
    rows = base._load(Path(parsed_base.products))

    url_metadata: dict[str, dict[str, Any]] = {}
    for row in rows:
        hit = _select_photo(row, selection)
        if hit is None:
            continue
        index, photo = hit
        url = str(photo["zoom"])
        if url in url_metadata:
            raise ValueError(f"duplicate selected image URL across products: {url}")
        url_metadata[url] = {
            "product_id": str(row.get("product_id") or ""),
            "image_index": index,
            "perspective": photo.get("perspective"),
        }

    missing = sorted(set(selection) - {meta["product_id"] for meta in url_metadata.values()})
    if missing:
        raise ValueError("selection products or requested perspectives missing from baseline: " + ",".join(missing))

    def selected_photo(row: dict[str, Any]):
        return _select_photo(row, selection)

    def selected_eligible(row: dict[str, Any], mode: str = "priority") -> bool:
        return selected_photo(row) is not None

    real_evidence = base.LabelImageEvidence

    def evidence_with_actual_perspective(*args, **kwargs):
        image_url = str(kwargs.get("image_url") or "")
        meta = url_metadata.get(image_url)
        if meta is None:
            raise ValueError(f"unregistered image URL passed to evidence: {image_url}")
        kwargs["perspective"] = meta["perspective"]
        kwargs["image_index"] = meta["image_index"]
        return real_evidence(*args, **kwargs)

    base._back_photo = selected_photo
    base._eligible = selected_eligible
    base.LabelImageEvidence = evidence_with_actual_perspective

    old_argv = sys.argv
    try:
        sys.argv = [old_argv[0], *remaining]
        rc = base.main()
    finally:
        sys.argv = old_argv

    out = Path(parsed_base.out)
    _patch_outputs(out, url_metadata, selection)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
