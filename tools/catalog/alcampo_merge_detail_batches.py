from __future__ import annotations

import argparse
import json
from pathlib import Path


def score(row: dict) -> tuple[int, int, int]:
    status = str(row.get("nutrition_status") or "")
    return (
        2 if status == "DECLARED_VALID" else 1 if row.get("error") is None else 0,
        1 if row.get("error") is None else 0,
        int(row.get("html_bytes") or 0),
    )


def merge_file(path: Path, best: dict[str, dict]) -> int:
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sku = str(row.get("sku") or "").strip()
        if not sku:
            continue
        count += 1
        if sku not in best or score(row) > score(best[sku]):
            best[sku] = row
    return count


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--downloaded", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--expected-products", type=Path, required=True)
    p.add_argument("--previous-details", type=Path)
    a = p.parse_args()

    expected = []
    for line in a.expected_products.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sku = str(row.get("sku") or "").strip()
        if sku:
            expected.append(sku)
    expected = list(dict.fromkeys(expected))

    best: dict[str, dict] = {}
    previous_rows = merge_file(a.previous_details, best) if a.previous_details else 0
    files = sorted(a.downloaded.rglob("details.jsonl"))
    new_rows = 0
    for path in files:
        new_rows += merge_file(path, best)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as f:
        for sku in expected:
            row = best.get(sku)
            if row is not None:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    missing = [sku for sku in expected if sku not in best]
    errors = [sku for sku in expected if sku in best and best[sku].get("error") is not None]
    valid = [sku for sku in expected if sku in best and best[sku].get("nutrition_status") == "DECLARED_VALID"]
    fetched = [sku for sku in expected if sku in best and best[sku].get("error") is None]
    report = {
        "expected_products": len(expected),
        "previous_detail_rows": previous_rows,
        "detail_artifacts": len(files),
        "new_detail_rows": new_rows,
        "detail_rows": len(best),
        "fetched": len(fetched),
        "declared_valid_nutrition": len(valid),
        "fetch_errors": len(errors),
        "missing_detail_rows": len(missing),
        "missing_skus": missing[:500],
        "error_skus": errors[:500],
    }
    report_path = a.out.with_name("detail_merge_summary.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # Missing rows mean a workflow/artifact failure. Per-product fetch errors remain valid REVIEW evidence.
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
