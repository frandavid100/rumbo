from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import mercadona_neural_ocr_wave as base


ELIGIBILITY_MODE = "explicit-photo-index-first-party"
PHOTO_SELECTION_POLICY = "EXPLICIT_FIRST_PARTY_PHOTO_INDEX"


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
        if not pid or "perspective" not in row or "image_index" not in row:
            raise ValueError("selection entries require product_id, perspective and image_index")
        try:
            image_index = int(row["image_index"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"product {pid}: image_index must be an integer") from exc
        if image_index < 0:
            raise ValueError(f"product {pid}: image_index must be non-negative")
        normalized = dict(row)
        normalized["image_index"] = image_index
        if pid in out:
            raise ValueError(f"duplicate selection for product {pid}")
        out[pid] = normalized
    return out


def _select_photo(
    row: dict[str, Any],
    selection: dict[str, dict[str, Any]],
) -> tuple[int, dict[str, Any]] | None:
    pid = str(row.get("product_id") or "")
    wanted = selection.get(pid)
    if wanted is None:
        return None
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    index = int(wanted["image_index"])
    if index >= len(photos):
        raise ValueError(f"product {pid}: selected image_index {index} out of range for {len(photos)} photos")
    photo = photos[index]
    if not isinstance(photo, dict):
        raise ValueError(f"product {pid}: selected image_index {index} is not a photo object")
    target_perspective = str(wanted["perspective"])
    actual_perspective = str(photo.get("perspective"))
    if actual_perspective != target_perspective:
        raise ValueError(
            f"product {pid}: selected image_index {index} perspective mismatch: "
            f"expected {target_perspective}, got {actual_perspective}"
        )
    if not photo.get("zoom"):
        raise ValueError(f"product {pid}: selected image_index {index} has no zoom URL")
    return index, photo


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
            wanted = selection.get(pid)
            if wanted is None:
                raise ValueError(f"unexpected product in explicit-photo wave: {pid}")
            if int(wanted["image_index"]) != int(meta["image_index"]):
                raise ValueError(f"product {pid}: result image index does not match explicit selection")
            row["perspective"] = meta["perspective"]
            row["image_index"] = meta["image_index"]
            row["eligibility_mode"] = ELIGIBILITY_MODE
            row["photo_selection"] = {
                "policy": PHOTO_SELECTION_POLICY,
                "requested_perspective": wanted["perspective"],
                "requested_image_index": wanted["image_index"],
                "actual_perspective": meta["perspective"],
                "actual_image_index": meta["image_index"],
                "reason": wanted.get("reason"),
            }
            patched.append(row)
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in patched),
            encoding="utf-8",
        )

    for path in out.glob("summary-*.json"):
        summary = _load_json(path)
        summary["eligibility_mode"] = ELIGIBILITY_MODE
        summary["photo_selection_policy"] = PHOTO_SELECTION_POLICY
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
    found: set[str] = set()
    for row in rows:
        hit = _select_photo(row, selection)
        if hit is None:
            continue
        index, photo = hit
        pid = str(row.get("product_id") or "")
        url = str(photo["zoom"])
        if url in url_metadata:
            raise ValueError(f"duplicate selected image URL across products: {url}")
        url_metadata[url] = {
            "product_id": pid,
            "image_index": index,
            "perspective": photo.get("perspective"),
        }
        found.add(pid)

    missing = sorted(set(selection) - found)
    if missing:
        raise ValueError("selection products missing from baseline: " + ",".join(missing))

    def selected_photo(row: dict[str, Any]):
        return _select_photo(row, selection)

    def selected_eligible(row: dict[str, Any], mode: str = "priority") -> bool:
        return selected_photo(row) is not None

    real_evidence = base.LabelImageEvidence

    def evidence_with_actual_photo(*args, **kwargs):
        image_url = str(kwargs.get("image_url") or "")
        meta = url_metadata.get(image_url)
        if meta is None:
            raise ValueError(f"unregistered image URL passed to evidence: {image_url}")
        kwargs["perspective"] = meta["perspective"]
        kwargs["image_index"] = meta["image_index"]
        return real_evidence(*args, **kwargs)

    base._back_photo = selected_photo
    base._eligible = selected_eligible
    base.LabelImageEvidence = evidence_with_actual_photo

    old_argv = sys.argv
    try:
        sys.argv = [old_argv[0], *remaining]
        rc = base.main()
    finally:
        sys.argv = old_argv

    _patch_outputs(Path(parsed_base.out), url_metadata, selection)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
