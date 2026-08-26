from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def score(row: dict) -> tuple[int, int, int]:
    status = str(row.get("nutrition_status") or "")
    return (
        2 if status == "DECLARED_VALID" else 1 if row.get("error") is None else 0,
        1 if row.get("error") is None else 0,
        int(row.get("html_bytes") or 0),
    )


def merge_file(path: Path | None, best: dict[str, dict]) -> int:
    if path is None or not path.exists():
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


def discover_previous_details() -> tuple[Path | None, str | None, tempfile.TemporaryDirectory | None]:
    """Read the latest successful first-party detail artifact when CI credentials allow it.

    The workflow already grants actions:read. Keeping this fallback inside the merger
    makes repeated waves monotonic even when an older workflow invocation did not pass
    --previous-details explicitly.
    """
    if not os.environ.get("GH_TOKEN") or not os.environ.get("GITHUB_REPOSITORY"):
        return None, None, None
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME") or "agent/catalog-phase1"
    try:
        listed = subprocess.run(
            [
                "gh", "run", "list", "--repo", repo,
                "--workflow", "catalog-alcampo-fast-detail-wave.yml",
                "--branch", branch, "--status", "success", "--limit", "1",
                "--json", "databaseId", "--jq", ".[0].databaseId // empty",
            ],
            check=True, capture_output=True, text=True, timeout=30,
        )
        run_id = listed.stdout.strip()
        if not run_id:
            return None, None, None
        temp = tempfile.TemporaryDirectory(prefix="alcampo-previous-detail-")
        target = Path(temp.name)
        subprocess.run(
            [
                "gh", "run", "download", run_id, "--repo", repo,
                "-n", "alcampo-fast-detail-classified-snapshot", "-D", str(target),
            ],
            check=True, capture_output=True, text=True, timeout=120,
        )
        details = target / "details.jsonl"
        if details.exists():
            return details, run_id, temp
        temp.cleanup()
    except Exception as exc:
        print(f"previous-detail discovery unavailable: {type(exc).__name__}: {exc}")
    return None, None, None


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

    previous_path = a.previous_details
    previous_run = None
    temp = None
    if previous_path is None:
        previous_path, previous_run, temp = discover_previous_details()

    best: dict[str, dict] = {}
    previous_rows = merge_file(previous_path, best)
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
        "previous_run": previous_run,
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
        "fetched_skus": fetched,
    }
    report_path = a.out.with_name("detail_merge_summary.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "fetched_skus"}, ensure_ascii=False, indent=2))
    if temp is not None:
        temp.cleanup()
    # Missing rows mean a workflow/artifact failure. Per-product fetch errors remain valid REVIEW evidence.
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
