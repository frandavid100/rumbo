from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--batches", type=int, default=64)
    p.add_argument("--github-output", type=Path)
    a = p.parse_args()

    rows = []
    seen = set()
    for line in a.input.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sku = str(row.get("sku") or "").strip()
        if not sku or sku in seen:
            continue
        seen.add(sku)
        rows.append(row)
    rows.sort(key=lambda r: str(r.get("sku") or ""))

    count = max(1, min(int(a.batches), len(rows) or 1))
    a.out.mkdir(parents=True, exist_ok=True)
    handles = [(a.out / f"batch-{i:03d}.jsonl").open("w", encoding="utf-8") for i in range(count)]
    try:
        for i, row in enumerate(rows):
            handles[i % count].write(json.dumps(row, ensure_ascii=False) + "\n")
    finally:
        for h in handles:
            h.close()

    matrix = {"include": [{"batch": f"{i:03d}"} for i in range(count)]}
    summary = {"products": len(rows), "batches": count, "matrix": matrix}
    (a.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if a.github_output:
        with a.github_output.open("a", encoding="utf-8") as f:
            f.write("matrix=" + json.dumps(matrix, ensure_ascii=False, separators=(",", ":")) + "\n")
            f.write("batch_count=" + str(count) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
