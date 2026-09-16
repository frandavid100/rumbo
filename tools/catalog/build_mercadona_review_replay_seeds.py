from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from summarize_mercadona_ocr_run_union import (
    EVIDENCE,
    SOURCE,
    SOURCE_RECORD_KIND,
    VALID,
    canonical_exclusion_reason,
    normalize_ean,
)


def _parse_created_at(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise ValueError(f"artifact created_at lacks timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def _load_artifact_chronology(path: Path) -> dict[str, tuple[datetime, int, int]]:
    out: dict[str, tuple[datetime, int, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            raise ValueError(f"invalid artifacts.tsv row: {line!r}")
        run_id_raw, _run_name, artifact_id_raw, _artifact_name, created_at = parts[:5]
        if not run_id_raw.isdigit() or not artifact_id_raw.isdigit():
            raise ValueError(f"invalid run/artifact identity: {line!r}")
        run_id = int(run_id_raw)
        artifact_id = int(artifact_id_raw)
        key = f"{run_id}-{artifact_id}"
        value = (_parse_created_at(created_at), run_id, artifact_id)
        prior = out.get(key)
        if prior is not None and prior != value:
            raise ValueError(f"conflicting chronology for {key}: {prior!r} vs {value!r}")
        out[key] = value
    if not out:
        raise ValueError("artifacts.tsv contains no artifact chronology")
    return out


def _batch_key(path: Path, root: Path, chronology: dict[str, tuple[datetime, int, int]]) -> tuple[datetime, int, int] | None:
    rel = path.relative_to(root)
    if not rel.parts:
        return None
    return chronology.get(rel.parts[0])


def _load_rows(path: Path) -> Iterable[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _is_mercadona_image_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("https://"):
        return False
    try:
        host = (urlparse(value).hostname or "").lower()
    except ValueError:
        return False
    return host == "prod-mercadona.imgix.net" or host.endswith(".mercadona.es")


def _strict_p9_identity(row: dict[str, Any]) -> tuple[str, str] | None:
    if row.get("source") != SOURCE:
        return None
    if row.get("source_record_kind") != SOURCE_RECORD_KIND:
        return None
    if row.get("evidence_level") != EVIDENCE:
        return None
    if row.get("redistribution_allowed") is not False:
        return None
    if str(row.get("perspective") or "") != "9":
        return None
    ean = normalize_ean(row.get("ean"))
    image_url = row.get("image_url")
    if ean is None or not _is_mercadona_image_url(image_url):
        return None
    return ean, str(image_url)


def _seed_row(product_id: str, row: dict[str, Any], *, run_id: int, artifact_id: int, created_at: datetime) -> dict[str, Any]:
    identity = _strict_p9_identity(row)
    if identity is None:
        raise ValueError("_seed_row called for a row without strict perspective=9 identity")
    ean, image_url = identity
    return {
        "product_id": product_id,
        "ean": ean,
        "name": row.get("name") or product_id,
        "brand": row.get("brand"),
        "category_id": row.get("category_id"),
        "category_name": row.get("category_name"),
        "observed_at": row.get("observed_at"),
        "share_url": row.get("source_page") or row.get("share_url"),
        "photos": [
            {
                "perspective": 9,
                "zoom": image_url,
            }
        ],
        "replay_seed_source": {
            "latest_raw_run_id": run_id,
            "latest_raw_artifact_id": artifact_id,
            "latest_raw_artifact_created_at": created_at.isoformat().replace("+00:00", "Z"),
            "canonical_status": "REVIEW",
            "source": SOURCE,
            "source_record_kind": SOURCE_RECORD_KIND,
            "evidence_level": EVIDENCE,
            "redistribution_allowed": False,
            "image_persisted": False,
            "nutrition_copied": False,
        },
    }


def build_review_replay_seeds(
    root: Path,
    run_union_summary: dict[str, Any],
    chronology: dict[str, tuple[datetime, int, int]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected_ids = {
        str(value)
        for value in run_union_summary.get("latest_status_product_ids", {}).get("REVIEW", [])
    }
    expected_count = int(
        run_union_summary.get("latest_status_counts", {}).get("REVIEW", len(expected_ids))
    )
    if expected_count != len(expected_ids):
        raise ValueError(
            f"run-union REVIEW count/id mismatch: count={expected_count}, ids={len(expected_ids)}"
        )

    by_product_batch: dict[
        str,
        dict[tuple[datetime, int, int], list[dict[str, Any]]],
    ] = defaultdict(lambda: defaultdict(list))
    excluded = Counter()
    files_seen = 0
    raw_rows_seen = 0

    for path in sorted(root.rglob("*.jsonl")):
        batch = _batch_key(path, root, chronology)
        if batch is None:
            continue
        files_seen += 1
        for row in _load_rows(path):
            product_id = str(row.get("product_id") or "")
            status = str(row.get("status") or "")
            if not product_id or product_id not in expected_ids:
                continue
            if status not in VALID or row.get("evidence_level") != EVIDENCE:
                continue
            reason = canonical_exclusion_reason(row)
            if reason:
                excluded[reason] += 1
                continue
            raw_rows_seen += 1
            by_product_batch[product_id][batch].append(row)

    missing_raw = sorted(expected_ids - set(by_product_batch))
    if missing_raw:
        raise ValueError(
            f"missing raw-live evidence for {len(missing_raw)} canonical REVIEW products: {missing_raw[:10]}"
        )

    seeds: list[dict[str, Any]] = []
    skipped = Counter()
    skipped_ids: dict[str, list[str]] = defaultdict(list)

    for product_id in sorted(expected_ids):
        by_batch = by_product_batch[product_id]
        latest_batch = max(by_batch)
        created_at, run_id, artifact_id = latest_batch
        rows = by_batch[latest_batch]
        statuses = {str(row.get("status") or "") for row in rows}
        if statuses != {"REVIEW"}:
            raise ValueError(
                f"latest raw-live batch disagrees with canonical REVIEW for {product_id}: "
                f"run={run_id}, artifact={artifact_id}, statuses={sorted(statuses)}"
            )

        candidates: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            identity = _strict_p9_identity(row)
            if identity is not None:
                candidates[identity].append(row)

        if not candidates:
            skipped["NO_STRICT_P9_IDENTITY"] += 1
            skipped_ids["NO_STRICT_P9_IDENTITY"].append(product_id)
            continue
        if len(candidates) != 1:
            skipped["AMBIGUOUS_LATEST_P9_IDENTITY"] += 1
            skipped_ids["AMBIGUOUS_LATEST_P9_IDENTITY"].append(product_id)
            continue

        (_ean, _image_url), matching_rows = next(iter(candidates.items()))
        representative = sorted(
            matching_rows,
            key=lambda row: (
                str(row.get("name") or ""),
                str(row.get("category_id") or ""),
                str(row.get("category_name") or ""),
            ),
        )[0]
        seeds.append(
            _seed_row(
                product_id,
                representative,
                run_id=run_id,
                artifact_id=artifact_id,
                created_at=created_at,
            )
        )

    seeds.sort(key=lambda row: row["product_id"])
    if len({row["product_id"] for row in seeds}) != len(seeds):
        raise ValueError("duplicate product_id in replay seeds")
    if any("nutrition" in row for row in seeds):
        raise ValueError("replay seeds must never copy nutrition values")

    summary = {
        "policy": (
            "Replay seeds are derived only from the latest chronological raw-live REVIEW evidence batch for each "
            "canonical product. Only exact Mercadona first-party perspective=9 image URLs with stable EAN identity "
            "are eligible. No image bytes and no nutrition values are copied into the seed artifact."
        ),
        "source": f"{SOURCE}/{SOURCE_RECORD_KIND}",
        "evidence_level": EVIDENCE,
        "redistribution_allowed": False,
        "images_persisted": False,
        "nutrition_values_copied": False,
        "canonical_review_products": expected_count,
        "strict_p9_replay_seeds": len(seeds),
        "skipped_products": expected_count - len(seeds),
        "skip_counts": dict(sorted(skipped.items())),
        "skip_product_ids": {key: sorted(values) for key, values in sorted(skipped_ids.items())},
        "raw_artifact_files_scanned": files_seen,
        "raw_review_rows_considered": raw_rows_seen,
        "excluded_derived_rows": dict(sorted(excluded.items())),
    }
    return seeds, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--run-union-summary", required=True)
    parser.add_argument("--artifacts-tsv", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    root = Path(args.root)
    run_union_summary = json.loads(Path(args.run_union_summary).read_text(encoding="utf-8"))
    chronology = _load_artifact_chronology(Path(args.artifacts_tsv))
    seeds, summary = build_review_replay_seeds(root, run_union_summary, chronology)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "products.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in seeds),
        encoding="utf-8",
    )
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if not seeds:
        raise SystemExit("No strict perspective=9 REVIEW replay seeds were produced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
