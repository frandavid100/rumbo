from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def successful_skus(path: Path | None) -> set[str]:
    """Return SKUs that already have a successfully fetched first-party detail row."""
    if path is None or not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sku = str(row.get("sku") or "").strip()
        if sku and row.get("error") is None:
            out.add(sku)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--batches", type=int, default=64)
    p.add_argument("--previous-details", type=Path)
    p.add_argument("--github-output", type=Path)
    a = p.parse_args()

    done = successful_skus(a.previous_details)
    rows = []
    seen = set()
    total = 0
    for line in a.input.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sku = str(row.get("sku") or "").strip()
        if not sku or sku in seen:
            continue
        seen.add(sku)
        total += 1
        if sku in done:
            continue
        rows.append(row)
    rows.sort(key=lambda r: str(r.get("sku") or ""))

    count = max(1, min(int(a.batches), len(rows) or 1))
    buckets: list[list[dict]] = [[] for _ in range(count)]
    for i, row in enumerate(rows):
        buckets[i % count].append(row)

    # A fresh GitHub runner tends to get only a small SSR window before Alcampo
    # starts returning transient 202 responses. Rotate each microbatch on later
    # workflow runs so repeated first-party waves do not keep spending that window
    # on exactly the same leading SKUs. This is deterministic and does not change
    # product identity or provenance.
    run_number = int(os.environ.get("GITHUB_RUN_NUMBER") or 0)
    stride = 7
    offsets = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            offsets.append(0)
            continue
        offset = (run_number * stride) % len(bucket)
        offsets.append(offset)
        if offset:
            buckets[i] = bucket[offset:] + bucket[:offset]

    a.out.mkdir(parents=True, exist_ok=True)
    for i, bucket in enumerate(buckets):
        with (a.out / f"batch-{i:03d}.jsonl").open("w", encoding="utf-8") as h:
            for row in bucket:
                h.write(json.dumps(row, ensure_ascii=False) + "\n")

    matrix = {"include": [{"batch": f"{i:03d}"} for i in range(count)]}
    summary = {
        "products": len(rows),
        "batches": count,
        "previous_successes": len(done & seen),
        "baseline_products": total,
        "run_number": run_number,
        "rotation_stride": stride,
        "rotation_offsets_min": min(offsets) if offsets else 0,
        "rotation_offsets_max": max(offsets) if offsets else 0,
        "matrix": matrix,
    }
    (a.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if a.github_output:
        with a.github_output.open("a", encoding="utf-8") as f:
            f.write("matrix=" + json.dumps(matrix, ensure_ascii=False, separators=(",", ":")) + "\n")
            f.write("batch_count=" + str(count) + "\n")
            f.write("retry_products=" + str(len(rows)) + "\n")
            f.write("previous_successes=" + str(len(done & seen)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
