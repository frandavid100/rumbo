from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE = "CARREFOUR_FIRST_PARTY"


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            return []
        if not isinstance(row, dict):
            return []
        rows.append(row)
    return rows


def official_url(value: object) -> bool:
    url = str(value or "")
    return url.startswith("https://www.carrefour.es/") or url.startswith("https://carrefour.es/")


def admissible_manual_row(row: dict) -> bool:
    if row.get("retailer") != "CARREFOUR" or row.get("source") != SOURCE:
        return False
    if not row.get("retailer_sku") or not official_url(row.get("canonical_url")):
        return False
    direct = row.get("direct_page_observed") is True and row.get("listing_only_observed") is not True
    listing = (
        row.get("direct_page_observed") is False
        and str(row.get("capture_method") or "").startswith("OPENAI_WEB_OFFICIAL_CATEGORY")
    )
    return direct or listing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", default="fixtures")
    ap.add_argument("--fresh", default="carrefour-first-party-fresh-inventory")
    ap.add_argument("--frontier", default="carrefour-first-party-category-frontier")
    ap.add_argument("--sqlite", default="carrefour-first-party-cumulative/carrefour_first_party.sqlite")
    ap.add_argument("--work", default="carrefour-first-party-cumulative-merge-input")
    args = ap.parse_args()

    fixtures = Path(args.fixtures)
    work = Path(args.work)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    for name in (
        "carrefour_first_party_products_cumulative.jsonl",
        "carrefour_first_party_field_evidence_cumulative.jsonl",
        "carrefour_first_party_cumulative_summary.json",
    ):
        src = fixtures / name
        if src.exists():
            shutil.copy2(src, work / name)

    accepted: list[str] = []
    skipped: list[str] = []
    accepted_rows = 0
    for src in sorted(fixtures.glob("carrefour_first_party_agent_web_products_*.jsonl")):
        rows = read_jsonl(src)
        if rows and all(admissible_manual_row(row) for row in rows):
            shutil.copy2(src, work / src.name)
            accepted.append(src.name)
            accepted_rows += len(rows)
        else:
            skipped.append(src.name)

    cmd = [
        sys.executable,
        str(Path(__file__).with_name("merge_carrefour_first_party_cumulative.py")),
        "--fixtures", str(work),
        "--fresh", args.fresh,
        "--frontier", args.frontier,
        "--sqlite", args.sqlite,
    ]
    subprocess.run(cmd, check=True)

    summary_path = work / "carrefour_first_party_cumulative_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["manual_fixture_selection"] = {
        "policy": "ONLY_EXPLICIT_DIRECT_PDP_OR_OFFICIAL_CATEGORY_OBSERVATIONS",
        "accepted_files": accepted,
        "accepted_rows": accepted_rows,
        "skipped_unverified_legacy_files": skipped,
        "skipped_count": len(skipped),
        "note": "Skipped legacy files are retained in the repository but are not promoted into cumulative first-party evidence without explicit observation provenance.",
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    for name in (
        "carrefour_first_party_products_cumulative.jsonl",
        "carrefour_first_party_field_evidence_cumulative.jsonl",
        "carrefour_first_party_cumulative_summary.json",
    ):
        shutil.copy2(work / name, fixtures / name)

    print(json.dumps(summary["manual_fixture_selection"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
